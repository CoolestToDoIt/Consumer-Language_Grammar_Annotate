"""Generate an invented demo language ("Velari") for showing the gloss workspace.

Velari is not a real language. It has regular suffixes so the teaching loop
visibly transfers what it learns: nouns take -um (plural) then -ek (ergative)
or -sa (locative); verbs take -ta (past), -ni (future) or -a (present). Word
order is subject, location, object, verb. The glossed lessons show each root and
each suffix, but the unglossed practice sentences use new combinations, a few
capitalized or punctuated words, and two roots the model has never been taught.
Answers for the practice sentences are written separately for the presenter.
"""
import argparse
from pathlib import Path
import random

NOUNS = {'tal': 'tree', 'mir': 'bird', 'vel': 'flower', 'kor': 'dog', 'sena': 'child', 'dun': 'river',
         'pira': 'stone', 'lom': 'house', 'faru': 'fish', 'zek': 'mountain'}
VERBS = {'vos': 'see', 'kel': 'chase', 'mar': 'find', 'tun': 'carry', 'sil': 'hear', 'bak': 'touch'}
UNTAUGHT = {'grovi': 'moon', 'hesk': 'wolf'}
NUMBER = {'': '', 'um': '-PL'}
CASE = {'': '', 'ek': '-ERG', 'sa': '-LOC'}
TENSE = {'ta': '-PST', 'ni': '-FUT', 'a': '-PRS'}


def noun(rng, roots, case, plural=None):
    root = rng.choice(sorted(roots))
    number = rng.choice(('', 'um')) if plural is None else plural
    return root+number+case, roots[root]+NUMBER[number]+CASE[case]


def sentence(rng, roots, verbs=VERBS):
    words = [noun(rng, roots, 'ek')]
    if rng.random() < .4:
        words.append(noun(rng, roots, 'sa'))
    words.append(noun(rng, roots, ''))
    verb, tense = rng.choice(sorted(verbs)), rng.choice(sorted(TENSE))
    words.append((verb+tense, verbs[verb]+TENSE[tense]))
    return [w for w, _ in words], [g for _, g in words]


def lessons(rng, count):
    rows = []
    # Isolated forms first: every root, then each suffix demonstrated on two roots.
    for root, gloss in NOUNS.items():
        rows.append(([root], [gloss]))
    for verb, gloss in VERBS.items():
        rows.append(([verb+'a'], [gloss+'-PRS']))
    for root in ('tal', 'mir'):
        for suffix, label in (('um', '-PL'), ('ek', '-ERG'), ('sa', '-LOC'), ('umek', '-PL-ERG')):
            rows.append(([root+suffix], [NOUNS[root]+label]))
    for verb in ('vos', 'kel'):
        for tense in ('ta', 'ni'):
            rows.append(([verb+tense], [VERBS[verb]+TENSE[tense]]))
    while len(rows) < count:
        rows.append(sentence(rng, NOUNS))
    return rows


def practice(rng, count, taught):
    rows = []
    while len(rows) < count:
        source, gloss = sentence(rng, {**NOUNS, **UNTAUGHT} if len(rows) % 5 == 4 else NOUNS)
        if tuple(source) in taught or not set(source)-{w for s in taught for w in s}:
            continue  # keep only sentences with at least one never-taught word form
        if len(rows) % 3 == 0:
            source[0] = source[0].capitalize()
        if len(rows) % 4 == 1:
            source[-1] += '.'
        rows.append((source, gloss))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', default='examples/velari-demo.tsv')
    parser.add_argument('--answers', default='examples/velari-demo-answers.tsv')
    parser.add_argument('--lessons', type=int, default=60)
    parser.add_argument('--practice', type=int, default=20)
    parser.add_argument('--seed', type=int, default=7)
    args = parser.parse_args(argv)
    rng = random.Random(args.seed)
    taught = lessons(rng, args.lessons)
    tests = practice(rng, args.practice, {tuple(s) for s, _ in taught})
    lines = [' '.join(s)+'\t'+' '.join(g) for s, g in taught] + [' '.join(s) for s, _ in tests]
    Path(args.output).write_text('\n'.join(lines)+'\n', encoding='utf-8')
    Path(args.answers).write_text('\n'.join(' '.join(s)+'\t'+' '.join(g) for s, g in tests)+'\n', encoding='utf-8')
    print(f'{len(taught)} glossed lessons and {len(tests)} practice sentences -> {args.output}; answers -> {args.answers}')


if __name__ == '__main__':
    main()
