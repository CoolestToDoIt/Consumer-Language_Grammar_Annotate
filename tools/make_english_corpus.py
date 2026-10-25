"""Convert Universal Dependencies English (CoNLL-U) into a gloss-workspace TSV.

Each word becomes a Leipzig-style gloss built from its UD lemma and features:
lowercase meaning, UPPERCASE grammar, joined with hyphens, e.g. birds ->
bird-PL, chased -> chase-PST, running -> run-PROG, me -> 1SG.ACC. Punctuation
is dropped. The first sentences of one file are written with glosses (treated
as already reviewed on import); sentences from a second file are written
without glosses for review.

UD English EWT is CC BY-SA 4.0 and is not bundled with this product. Download
it yourself, e.g. from https://github.com/UniversalDependencies/UD_English-EWT
(release r2.15), and keep the output beside your other local data:

    python3 tools/make_english_corpus.py \
        --glossed path/to/en_ewt-ud-train.conllu --review path/to/en_ewt-ud-dev.conllu \
        --output runs/english/english-ewt.tsv
"""
import argparse
from pathlib import Path
import unicodedata

SKIP_UPOS = {'PUNCT', 'SYM', 'X'}
PERSON_NUMBER = {'Sing': 'SG', 'Plur': 'PL'}


def read_conllu(path):
    """Yield sentences as lists of (form, lemma, upos, feats) syntactic words."""
    sentence = []
    with Path(path).open(encoding='utf-8') as handle:
        for line in handle:
            line = line.rstrip('\n')
            if not line:
                if sentence:
                    yield sentence
                sentence = []
                continue
            if line.startswith('#'):
                continue
            columns = line.split('\t')
            if len(columns) != 10 or not columns[0].isdigit():
                continue  # multiword-token ranges and empty nodes
            feats = dict(item.split('=', 1) for item in columns[5].split('|') if '=' in item)
            sentence.append((columns[1], columns[2], columns[3], feats))
    if sentence:
        yield sentence


def lexical(lemma, upos):
    # Hyphens separate morphemes in a gloss, so multiword meanings use dots.
    # Names keep their capitals, but a gloss needs a lowercase letter to count
    # as a meaning rather than a grammatical tag, so all-caps names (US) drop them.
    text = lemma.replace('-', '.').replace('=', '.')
    return text if upos == 'PROPN' and any(c.islower() for c in text) else text.lower()


def gloss(form, lemma, upos, feats):
    if upos == 'PRON' and 'Person' in feats:
        label = feats['Person'] + PERSON_NUMBER.get(feats.get('Number'), '')
        if feats.get('Poss') == 'Yes':
            label += '.POSS'
        elif feats.get('Reflex') == 'Yes':
            label += '.REFL'
        elif feats.get('Case') == 'Acc':
            label += '.ACC'
        return label
    if upos == 'PART' and lemma in ('not', "n't"):
        return 'NEG'
    if upos == 'PART' and lemma in ("'s", "'"):
        return 'POSS'
    base = lexical(lemma, upos)
    if not base or not any(c.isalnum() for c in base):
        return None
    tags = []
    if upos in ('NOUN', 'PROPN') and feats.get('Number') == 'Plur':
        tags.append('PL')
    elif upos in ('VERB', 'AUX'):
        form_type, tense = feats.get('VerbForm'), feats.get('Tense')
        if form_type == 'Fin' and tense == 'Past':
            tags.append('PST')
        elif form_type == 'Fin' and tense == 'Pres' and feats.get('Person') == '3' and feats.get('Number') == 'Sing':
            tags.append('3SG')
        elif form_type == 'Part' and tense == 'Past':
            tags.append('PTCP')
        elif form_type == 'Ger' or (form_type == 'Part' and tense == 'Pres'):
            tags.append('PROG')
    elif upos in ('ADJ', 'ADV'):
        tags.append({'Cmp': 'CMPR', 'Sup': 'SPRL'}.get(feats.get('Degree'), ''))
    return '-'.join([base, *[tag for tag in tags if tag]])


def convert(path, *, limit, min_words, max_words):
    rows = []
    for sentence in read_conllu(path):
        words, glosses = [], []
        for form, lemma, upos, feats in sentence:
            if upos in SKIP_UPOS or all(unicodedata.category(c).startswith('P') for c in form):
                continue
            label = gloss(form, lemma, upos, feats)
            if label is None or any(c.isspace() for c in form + label):
                words = None
                break
            words.append(unicodedata.normalize('NFC', form))
            glosses.append(unicodedata.normalize('NFC', label))
        if words and min_words <= len(words) <= max_words:
            rows.append((words, glosses))
            if len(rows) >= limit:
                break
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--glossed', required=True, help='CoNLL-U file whose sentences are imported with glosses')
    parser.add_argument('--review', help='CoNLL-U file whose sentences are imported without glosses')
    parser.add_argument('--output', default='runs/english/english-ewt.tsv')
    parser.add_argument('--glossed-count', type=int, default=400)
    parser.add_argument('--review-count', type=int, default=60)
    parser.add_argument('--min-words', type=int, default=4)
    parser.add_argument('--max-words', type=int, default=14)
    args = parser.parse_args(argv)
    taught = convert(args.glossed, limit=args.glossed_count, min_words=args.min_words, max_words=args.max_words)
    review = convert(args.review, limit=args.review_count, min_words=args.min_words, max_words=args.max_words) if args.review else []
    seen = {tuple(words) for words, _ in taught}
    review = [(words, glosses) for words, glosses in review if tuple(words) not in seen]
    lines = [' '.join(words) + '\t' + ' '.join(glosses) for words, glosses in taught] + [' '.join(words) for words, _ in review]
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{len(taught)} glossed and {len(review)} review sentences -> {destination}')


if __name__ == '__main__':
    main()
