"""Audience views for the offline terminal demo."""
from .generator import english


def status(session):
    learner = session.learner
    print(f'\nLESSONS {len(session.processed)}  |  PENDING {len(session.pending)}  |  VERSION {learner.version}')
    hypotheses = getattr(learner, 'hypotheses', [])
    if not hypotheses:
        print('No consistent grammar remains. Start a new language or inspect corrections.')
        return
    print(f'{len(hypotheses)} grammar hypotheses remain; equal initial weights, filtered by teacher evidence.')
    for h in hypotheses[:6]:
        rules = ', '.join(f'{marker} = {feature.lower()}' for marker, feature in sorted(h['rules'].items())) or 'markers not learned yet'
        print(f"  {h['order']} / {h['placement']}: {rules}")
    if len(hypotheses) > 6:
        print(f'  … {len(hypotheses)-6} more')


def predict_view(source, result):
    print('\nSOURCE:', source)
    print('GUESS: ', english(result['meaning']))
    if result['recall']:
        print('Verified memory recall; this is not unseen transfer.')
    elif result['meaning'] is None:
        print('Insufficient evidence to decode this form.')
    else:
        print(f"{len(result['candidates'])} distinct candidate(s); hypothesis agreement {result.get('agreement', 0):.0%} (not calibrated confidence)")
        for candidate in result['candidates'][1:]:
            print('  Alternative:', english(candidate))


def teach(session, gold, probes, delay=0):
    # Fixed first three probes: selection never depends on their answers.
    witnesses = probes[:3]
    before = [session.learner.predict(g.example.source)['meaning'] for g in witnesses]
    already = gold.example.id in session.processed or any(e['id'] == gold.example.id for e in session.pending)
    session.feedback(gold.example.id, gold.meaning, delay)
    print('\nTEACHER:', english(gold.meaning))
    if already:
        print('This answer was already applied or queued; no duplicate update.')
    elif delay:
        print(f'Queued for input step {session.step + delay}. The learner has not received this answer yet.')
    else:
        print('Correction applied. Fixed probe examples before → after:')
        for gold_probe, old in zip(witnesses, before):
            new = session.learner.predict(gold_probe.example.source)['meaning']
            kind = 'recall' if gold_probe.example.source in session.learner.memory else 'untouched'
            print(' ', gold_probe.example.source, f'[{kind}]')
            print('    ', english(old), '→', english(new))
    status(session)
