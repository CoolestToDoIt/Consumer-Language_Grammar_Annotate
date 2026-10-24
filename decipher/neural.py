"""Optional byte-level attentive seq2seq learner and incremental replay.

A fixed UTF-8 byte vocabulary exposes no future words or target labels. Each
instance owns its replay RNG; constructing or predicting does not consume the
process-wide random stream. PyTorch is imported only by this optional module.
"""
from dataclasses import asdict, dataclass
import copy
import math
from pathlib import Path
import random
import tempfile
import time

import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

PAD, BOS, EOS, VOCAB = 0, 1, 2, 259
MODES = ('frozen', 'memory', 'parameters', 'replay', 'hybrid')


@dataclass(frozen=True)
class NeuralConfig:
    embedding: int = 64
    hidden: int = 128
    learning_rate: float = .0003
    update_steps: int = 2
    replay_batch: int = 15
    reservoir_size: int = 2000
    max_source_bytes: int = 512
    max_target_bytes: int = 256
    seed: int = 7
    device: str = 'cpu'

    def __post_init__(self):
        for name in ('embedding', 'hidden', 'update_steps', 'reservoir_size', 'max_source_bytes', 'max_target_bytes'):
            if getattr(self, name) < 1:
                raise ValueError(f'{name} must be positive')
        if self.replay_batch < 0 or not math.isfinite(self.learning_rate) or self.learning_rate <= 0:
            raise ValueError('Invalid replay size or learning rate')


def device_for(requested):
    if requested == 'auto':
        return 'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
    if requested not in ('cpu', 'cuda', 'mps'):
        raise ValueError('device must be cpu, cuda, mps, or auto')
    if requested == 'mps' and not torch.backends.mps.is_available():
        raise ValueError('MPS is unavailable; choose cpu')
    if requested == 'cuda' and not torch.cuda.is_available():
        raise ValueError('CUDA is unavailable; choose cpu')
    return requested


def encode(text, limit):
    if not isinstance(text, str) or not text:
        raise ValueError('Source and target text must be nonempty strings')
    values = text.encode('utf-8')
    if len(values) > limit:
        raise ValueError(f'Text exceeds configured {limit}-byte limit; no silent truncation')
    return [byte+3 for byte in values] + [EOS]


def decode(values):
    return bytes(value-3 for value in values if value >= 3).decode('utf-8', errors='replace')


class AttentiveGRU(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.embedding = nn.Embedding(VOCAB, config.embedding, padding_idx=PAD)
        self.encoder = nn.GRU(config.embedding, config.hidden, batch_first=True, bidirectional=True)
        self.decoder = nn.GRU(config.embedding, config.hidden, batch_first=True)
        self.bridge = nn.Linear(config.hidden*2, config.hidden)
        self.keys = nn.Linear(config.hidden*2, config.hidden, bias=False)
        self.output = nn.Linear(config.hidden*3, VOCAB)

    def encode(self, source, lengths):
        embedded = self.embedding(source)
        packed = pack_padded_sequence(embedded, lengths.cpu(), batch_first=True, enforce_sorted=False)
        encoded, hidden = self.encoder(packed)
        encoded, _ = pad_packed_sequence(encoded, batch_first=True)
        initial = torch.tanh(self.bridge(torch.cat((hidden[-2], hidden[-1]), dim=-1))).unsqueeze(0)
        mask = source[:, :encoded.size(1)].eq(PAD)
        return encoded, self.keys(encoded), initial, mask

    def attend(self, states, encoded, keys, mask):
        scores = torch.bmm(states, keys.transpose(1, 2)) / math.sqrt(states.size(-1))
        scores = scores.masked_fill(mask.unsqueeze(1), float('-inf'))
        context = torch.bmm(torch.softmax(scores, dim=-1), encoded)
        return self.output(torch.cat((states, context), dim=-1))

    def forward(self, source, lengths, decoder_inputs):
        encoded, keys, initial, mask = self.encode(source, lengths)
        states, _ = self.decoder(self.embedding(decoder_inputs), initial)
        return self.attend(states, encoded, keys, mask)


class NeuralLearner:
    def __init__(self, config=None, mode='hybrid'):
        self.config = config or NeuralConfig()
        if mode not in MODES:
            raise ValueError('Unknown neural adaptation mode')
        self.mode = mode
        self.device = device_for(self.config.device)
        # Construction is deterministic and restores the caller's CPU RNG.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(self.config.seed)
            self.network = AttentiveGRU(self.config).to(self.device)
        self.initial_parameters = {key: value.detach().cpu().clone() for key, value in self.network.state_dict().items()}
        self.optimizer = torch.optim.Adam(self.network.parameters(), lr=self.config.learning_rate)
        self.rng = random.Random(self.config.seed)
        self.records = {}
        self.memory = {}
        self.reservoir = []
        self.seen = 0
        self.version = 0
        self.optimizer_steps = 0
        self.training_examples_consumed = 0
        self.last_update = {}
        self.network.eval()

    @property
    def parameter_count(self):
        return sum(p.numel() for p in self.network.parameters())

    def _batch(self, pairs):
        sources = [encode(source, self.config.max_source_bytes) for source, _ in pairs]
        targets = [encode(target, self.config.max_target_bytes) for _, target in pairs]
        source = torch.zeros((len(pairs), max(map(len, sources))), dtype=torch.long, device=self.device)
        expected = torch.zeros((len(pairs), max(map(len, targets))), dtype=torch.long, device=self.device)
        for i, values in enumerate(sources):
            source[i, :len(values)] = torch.tensor(values, device=self.device)
        for i, values in enumerate(targets):
            expected[i, :len(values)] = torch.tensor(values, device=self.device)
        decoder_input = torch.cat((torch.full((len(pairs), 1), BOS, device=self.device, dtype=torch.long), expected[:, :-1]), dim=1)
        return source, torch.tensor(list(map(len, sources))), decoder_input, expected

    def _update(self, source, target):
        losses = []
        start = time.perf_counter()
        if self.mode in ('parameters', 'replay', 'hybrid'):
            for _ in range(self.config.update_steps):
                pairs = [(source, target)]
                if self.mode in ('replay', 'hybrid'):
                    for identifier in self.rng.sample(self.reservoir, min(self.config.replay_batch, len(self.reservoir))):
                        record = self.records[identifier]
                        pairs.append((record['source'], record['target']))
                src, lengths, decoder_input, expected = self._batch(pairs)
                self.network.train()
                self.optimizer.zero_grad(set_to_none=True)
                logits = self.network(src, lengths, decoder_input)
                loss = nn.functional.cross_entropy(logits.reshape(-1, VOCAB), expected.reshape(-1), ignore_index=PAD)
                loss.backward()
                nn.utils.clip_grad_norm_(self.network.parameters(), 1.0)
                self.optimizer.step()
                self.optimizer_steps += 1
                self.training_examples_consumed += len(pairs)
                losses.append(float(loss.detach()))
            self.network.eval()
        self.seen += 1
        if len(self.reservoir) < self.config.reservoir_size:
            self.reservoir.append(self._current_id)
        else:
            index = self.rng.randrange(self.seen)
            if index < self.config.reservoir_size:
                self.reservoir[index] = self._current_id
        self.memory[source] = target
        self.last_update = {'loss': losses[-1] if losses else None, 'optimizer_steps': len(losses),
                            'seconds': time.perf_counter()-start, 'reservoir_size': len(self.reservoir)}

    def correct(self, identifier, source, target):
        if not isinstance(identifier, str) or not identifier:
            raise ValueError('Feedback needs a nonempty string ID')
        encode(source, self.config.max_source_bytes)
        encode(target, self.config.max_target_bytes)
        previous = self.records.get(identifier)
        record = {'source': source, 'target': target}
        if previous == record:
            return False
        if previous is not None and previous['source'] != source:
            raise ValueError('A feedback ID cannot change its source')
        if previous is None:
            self.records[identifier] = record
            self._current_id = identifier
            self._update(source, target)
        else:
            # Revisions rebuild deterministically from the original initialization.
            revised = dict(self.records)
            del revised[identifier]
            revised[identifier] = record
            self.network.load_state_dict(self.initial_parameters)
            self.optimizer = torch.optim.Adam(self.network.parameters(), lr=self.config.learning_rate)
            self.rng = random.Random(self.config.seed)
            self.records, self.memory, self.reservoir = {}, {}, []
            self.seen = self.optimizer_steps = self.training_examples_consumed = 0
            for key, value in revised.items():
                self.records[key] = value
                self._current_id = key
                self._update(value['source'], value['target'])
        self.version += 1
        return True

    def predict(self, source, beam_size=3, max_bytes=None, use_memory=True):
        values = encode(source, self.config.max_source_bytes)
        if beam_size < 1 or beam_size > 10:
            raise ValueError('beam_size must be between 1 and 10')
        if use_memory and self.mode in ('memory', 'hybrid') and source in self.memory:
            return {'text': self.memory[source], 'candidates': [{'text': self.memory[source], 'log_score': None}], 'recall': True, 'version': self.version}
        limit = self.config.max_target_bytes if max_bytes is None else max_bytes
        if limit < 1 or limit > self.config.max_target_bytes:
            raise ValueError('Invalid decode byte limit')
        source_tensor = torch.tensor([values], device=self.device)
        with torch.inference_mode():
            encoded, keys, initial, mask = self.network.encode(source_tensor, torch.tensor([len(values)]))
            beams = [(0.0, [], initial, BOS, False)]
            for _ in range(limit):
                expanded = []
                for score, tokens, hidden, previous, finished in beams:
                    if finished:
                        expanded.append((score, tokens, hidden, previous, finished))
                        continue
                    states, updated = self.network.decoder(self.network.embedding(torch.tensor([[previous]], device=self.device)), hidden)
                    logits = self.network.attend(states, encoded, keys, mask)[0, 0]
                    logits = logits.clone()
                    logits[PAD] = logits[BOS] = float('-inf')
                    log_probs = torch.log_softmax(logits, dim=-1)
                    scores, indices = torch.topk(log_probs, beam_size)
                    for increment, token in zip(scores.tolist(), indices.tolist()):
                        expanded.append((score+increment, tokens+[token], updated, token, token == EOS))
                beams = sorted(expanded, key=lambda b: (-(b[0]/max(1, len(b[1]))**.6), b[1]))[:beam_size]
                if all(b[-1] for b in beams):
                    break
            candidates = [{'text': decode(tokens), 'log_score': score, 'finished': finished} for score, tokens, _, _, finished in beams]
        return {'text': candidates[0]['text'], 'candidates': candidates, 'recall': False, 'version': self.version}

    def state(self):
        return {'schema_version': 1, 'config': asdict(self.config), 'mode': self.mode,
                'parameters': self.network.state_dict(), 'initial_parameters': self.initial_parameters,
                'optimizer': self.optimizer.state_dict(), 'records': copy.deepcopy(self.records),
                'memory': dict(self.memory), 'reservoir': list(self.reservoir), 'rng': self.rng.getstate(),
                'seen': self.seen, 'version': self.version, 'optimizer_steps': self.optimizer_steps,
                'training_examples_consumed': self.training_examples_consumed, 'last_update': dict(self.last_update)}

    def save(self, path):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
        try:
            torch.save(self.state(), temporary)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls, path, device='cpu'):
        state = torch.load(path, map_location='cpu', weights_only=True)
        return cls.from_state(state, device=device)

    @classmethod
    def from_state(cls, state, device='cpu'):
        if state.get('schema_version') != 1:
            raise ValueError('Unsupported neural checkpoint schema')
        config = dict(state['config'], device=device)
        learner = cls(NeuralConfig(**config), state['mode'])
        learner.network.load_state_dict(state['parameters'])
        learner.initial_parameters = state['initial_parameters']
        learner.optimizer.load_state_dict(state['optimizer'])
        for key in ('records', 'memory', 'reservoir', 'seen', 'version', 'optimizer_steps', 'training_examples_consumed', 'last_update'):
            setattr(learner, key, state[key])
        learner.rng.setstate(state['rng'])
        learner.network.eval()
        return learner
