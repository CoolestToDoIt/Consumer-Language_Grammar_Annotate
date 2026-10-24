import argparse
import json
from .generator import episode, PRESETS, Example, GoldExample
from .teacher import Session
from .evaluate import evaluate
from .dataset import identity
from .presentation import predict_view, teach, status


def main():
    import sys
    if sys.argv[1:2] == ['corpus']:
        from .corpus_app import main as corpus_main
        corpus_main(sys.argv[2:])
        return
    parser = argparse.ArgumentParser(description='Learn grammar from corrections and analyze annotated corpora.', epilog='Real text commands: decipher corpus --help')
    parser.add_argument('command', choices=('demo', 'evaluate', 'walkthrough', 'dataset', 'stress', 'corpus'), nargs='?', default='demo')
    parser.add_argument('--preset', choices=PRESETS, default='A')
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--delay', type=int, default=0)
    parser.add_argument('--output')
    parser.add_argument('--data-dir', default='data/demo')
    parser.add_argument('--report-dir')
    args = parser.parse_args()
    if args.delay < 0:
        parser.error('--delay must be nonnegative')
    if args.command == 'dataset':
        from .dataset import export_dataset
        metadata = export_dataset(args.data_dir, args.preset, args.seed)
        print(f"Validated and exported {metadata['fingerprint']} to {args.data_dir}")
        return
    if args.command == 'stress':
        from .stress import marker_reversal
        from pathlib import Path
        report = marker_reversal()
        output = args.output or 'reports/marker-reversal.json'
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(report, indent=2) + '\n')
        for run in report['runs']:
            print(f"{run['preset']} reversed={run['reversed']}: {run['probe_correct']}/{run['probe_count']}")
        return
    if args.command == 'walkthrough':
        from .walkthrough import walkthrough
        walkthrough(args.seed)
        return
    if args.command == 'evaluate':
        output = args.output or ('results-delayed.json' if args.delay else 'results.json')
        from pathlib import Path
        report_dir = args.report_dir or ('reports/delayed' if args.delay else 'reports/immediate')
        report = evaluate(output, args.delay, event_directory=Path(report_dir)/'events')
        from .report import write_report
        write_report(report, report_dir)
        for preset in PRESETS:
            for model in ('memory', 'analogy', 'rules'):
                runs = [r for r in report['runs'] if r['preset'] == preset and r['model'] == model]
                count = len(runs)
                root = sum(r['root_only_accuracy'] for r in runs)/count
                lesson = sum(r['support_curve'][1]['accuracy'] for r in runs)/count
                final = sum(r['curve'][-1]['accuracy'] for r in runs)/count
                print(f"{preset} {model:7} roots {root:.1%} → first lesson {lesson:.1%} → final {final:.1%}")
        print(f'Saved {output}')
        return
    preset = args.preset
    while True:
        _, roots, _, stream, probes = episode(preset, args.seed)
        session = Session(roots, identity=identity(preset, args.seed))
        print('\nDECIPHER LAB — roots are supplied; grammar must be learned.')
        print(json.dumps(roots, indent=2))
        print('Enter: next | correct | teach | predict TEXT | answer ... | roots | status | probe | save | load | new A/B/C | quit')
        current = None
        index = 0
        while True:
            try:
                command = input('decipher> ').strip()
            except (EOFError, KeyboardInterrupt):
                return
            if command == 'quit':
                return
            if command.startswith('new '):
                choice = command.split()[-1].upper()
                if choice in PRESETS:
                    preset = choice
                    break
                print('Choose A, B, or C.'); continue
            if command.startswith('predict '):
                source = command[len('predict '):].strip()
                if not source or len(source) > 500:
                    print('Enter a sentence of 1–500 characters.'); continue
                current = GoldExample(Example(f'custom-{session.step+1}', source), {})
                predict_view(source, session.predict(current.example))
            elif command.startswith('answer '):
                if current is None:
                    print('Predict a sentence first.'); continue
                from .meaning import parse_answer
                try:
                    meaning = parse_answer(command[len('answer '):], roots)
                    teach(session, GoldExample(current.example, meaning), probes, args.delay)
                except ValueError as exc:
                    print(f'Invalid answer: {exc}')
            elif command == 'roots':
                print(json.dumps(roots, indent=2))
            elif command == 'next':
                if index == len(stream):
                    print('End of stream. Start a new language.'); continue
                current = stream[index]; index += 1
                result = session.predict(current.example)
                predict_view(current.example.source, result)
            elif command in ('correct', 'teach'):
                if command == 'teach' and (current is None or current.example.id in session.processed or any(e['id'] == current.example.id for e in session.pending)):
                    if index == len(stream):
                        print('End of stream. Start a new language.'); continue
                    current = stream[index]; index += 1
                    predict_view(current.example.source, session.predict(current.example))
                if current is None:
                    print('Use next to predict an example first.'); continue
                if not current.meaning:
                    print('For a custom sentence, use answer AGENT VERB PATIENT TENSE AGENT_NUMBER PATIENT_NUMBER.'); continue
                teach(session, current, probes, args.delay)
            elif command == 'status':
                status(session)
            elif command == 'rules':
                print(json.dumps(session.learner.hypotheses, indent=2))
            elif command == 'probe':
                from .evaluate import accuracy
                untaught = [g for g in probes if g.example.source not in session.learner.memory]
                if untaught:
                    print(f'Untaught probe accuracy: {accuracy(session.learner, untaught):.1%} ({len(untaught)} sources never taught)')
                else:
                    print('All probe sources have been taught; no unseen transfer score remains.')
            elif command == 'save':
                session.save('checkpoint.json')
                session.export('events.jsonl')
                print('Saved checkpoint.json and events.jsonl')
            elif command == 'load':
                try:
                    loaded = Session.load('checkpoint.json', expected_identity=identity(preset, args.seed))
                    if loaded.learner.roots != roots:
                        print('Checkpoint belongs to another language. Select its preset and seed first.'); continue
                    session = loaded
                    index = max((i+1 for i, x in enumerate(stream) if x.example.id in session.sources), default=0)
                    last = next((event for event in reversed(session.events) if event['type'] == 'prediction'), None)
                    if last:
                        current = next((g for g in stream if g.example.id == last['id']), GoldExample(Example(last['id'], last['source']), {}))
                    else:
                        current = None
                    print('Checkpoint restored.')
                except (OSError, ValueError, KeyError) as exc:
                    print(f'Cannot load: {exc}')
            else:
                print('Use next, correct, teach, predict TEXT, answer AGENT VERB PATIENT TENSE AGENT_NUMBER PATIENT_NUMBER, roots, status, rules, probe, save, load, new A/B/C, or quit.')

if __name__ == '__main__':
    main()
