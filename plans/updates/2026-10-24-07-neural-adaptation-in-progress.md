# Neural adaptation and matched online experiments — in progress

Implement the next neural/replay milestone while keeping existing corpus test scores fixed. Development-only experiments will compare frozen parameters, memory-only updates, parameter-only updates, replay, and replay plus verified memory under identical feedback schedules.

The neural model uses a bidirectional GRU encoder, attention, and an autoregressive GRU decoder. A fixed UTF-8 byte vocabulary avoids learning a character/label inventory from unreleased answers and supports both synthetic meanings and real morphology outputs. This is a deliberate byte-level variation on the roadmap's character encoder. Initial settings follow the roadmap: 64-dimensional embeddings, 128 hidden units, Adam at 0.0003, clipping at 1.0, and a replay batch of up to 15 corrected examples.

Key verification before interpreting scores: saved predictions precede feedback; delayed labels apply only on arrival; frozen probes do not mutate weights, optimizer, memory, or RNG; resumed updates match uninterrupted CPU updates; duplicate corrections are idempotent; revisions rebuild from the original initialization and authoritative labels.

The existing symbolic model remains the preferred system unless development evidence shows a neural benefit. A negative result is useful and will be reported. No corpus test-set tuning or cross-language-pretraining claim is authorized by these experiments.
