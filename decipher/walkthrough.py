"""A deterministic, noninteractive presentation of actual learner behavior."""
from .generator import episode
from .teacher import Session
from .evaluate import accuracy
from .dataset import identity
from .presentation import predict_view, teach


def walkthrough(seed=7):
    for preset in ('A', 'B', 'C'):
        _, roots, _, stream, probes = episode(preset, seed)
        session = Session(roots, identity=identity(preset, seed))
        print(f'\n=== New language {preset}: fresh learner, 11 supplied root meanings ===')
        print(f'Untaught probe accuracy before lessons: {accuracy(session.learner, probes):.1%}')
        for gold in stream[:2]:
            prediction = session.predict(gold.example)
            predict_view(gold.example.source, prediction)
            teach(session, gold, probes)
            print(f'Untaught probe accuracy: {accuracy(session.learner, probes):.1%}')
    print('\nThe same first three probes are displayed before/after each correction.')
    print('Probe labels are used only by the scorer. No probe answers are taught or used to select examples.')
