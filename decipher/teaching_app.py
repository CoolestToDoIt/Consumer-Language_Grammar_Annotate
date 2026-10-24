"""Human teaching commands using an injected language-project store."""
import argparse
import json
from pathlib import Path
import shlex

from .teaching import TeachingService


def _store(backend):
    if backend == 'fixture':
        from .teaching_fixture import FixtureProjectStore
        return FixtureProjectStore()
    try:
        from .workspace import WorkspaceStore
    except ModuleNotFoundError as exc:
        if exc.name != 'decipher.workspace':
            raise
        raise ValueError('The production workspace adapter is not installed. Use --backend fixture for the development demo; Worker A owns production persistence.') from exc
    return WorkspaceStore()


def prediction_text(record):
    lines = [f"Prediction {record['prediction_id']} for {record['example_id']} "
             f"(model {record['model_version']}, annotation revision {record['annotation_revision']})"]
    for index, (token, word) in enumerate(zip(record['tokens'], record['words']), 1):
        status = 'known' if word['known_form'] else 'tentative draft' if word.get('provisional') else 'unseen'
        lines.append(f"{index}. {token} -> {word['gloss'] or '?'} [{status} form]")
        for candidate in word['candidates']:
            evidence = {key: value for key, value in candidate.items() if key not in ('gloss', 'score', 'kind')}
            lines.append(f"   {candidate['gloss']} | {candidate['kind']} | raw score {candidate['score']:.4g} (uncalibrated)"
                         +(f" | evidence {json.dumps(evidence, ensure_ascii=False)}" if evidence else ''))
    return '\n'.join(lines)


def emit(value, structured=False):
    if structured:
        print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
    elif isinstance(value, dict) and 'prediction_id' in value and 'words' in value:
        print(prediction_text(value))
    elif isinstance(value, dict) and 'correction' in value:
        receipt = value['correction']
        print(f"{'Saved' if receipt['changed'] else 'Already verified'} {receipt['example_id']}, "
              f"revision {receipt['revision']}; model {receipt['model_version']}")
        print('Updated prediction: '+' '.join(word['gloss'] or '?' for word in value['after']['words']))
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def project_status(project):
    examples = project.examples()
    annotated = [project.annotation(example.id) for example in examples]
    return {'project_id': project.project_id, 'name': project.name, 'language': project.language,
            'model_version': project.model_version, 'sentences': len(examples),
            'verified_sentences': sum(row is not None for row in annotated),
            'verified_word_labels': sum(len(row['glosses']) for row in annotated if row is not None)}


def shell(store, path):
    project = store.open(path)
    service, current = TeachingService(project), None
    print(f"Teaching {project.name} ({project.language}). Each change is saved. Type help for commands.")
    while True:
        try:
            line = input('teach> ').strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not line:
            continue
        try:
            command = line.split(None, 1)[0]
            if command == 'submit':
                # Source text is literal language data, not shell syntax: don't
                # interpret apostrophes or punctuation as quoting commands.
                parts = line.split(None, 2)
            elif command == 'correct':
                parts = line.split()
            elif command == 'replace':
                left, separator, right = line.partition('::')
                reason = left[len('replace'):].strip()
                if not separator or not reason:
                    raise ValueError('Use replace REASON :: WORD-GLOSSES')
                parts = ['replace', reason, '::', *right.split()]
            elif command in ('search', 'export'):
                argument = line[len(command):].strip()
                if command == 'export' and len(argument) >= 2 and argument[0] == argument[-1] and argument[0] in ('\"', "'"):
                    argument = argument[1:-1]
                parts = [command, argument] if argument else [command]
            else:
                parts = shlex.split(line)
            if command in ('quit', 'exit'):
                return
            if command == 'help':
                print('submit ID SOURCE WORDS | predict ID | confirm | correct WORD-GLOSSES | '
                      'replace REASON :: WORD-GLOSSES | history ID | search TEXT | review [LIMIT] | '
                      'status | save | reload | export PATH | quit')
            elif command == 'submit' and len(parts) >= 3:
                emit(service.submit(parts[1], ' '.join(parts[2:])))
            elif command == 'predict' and len(parts) == 2:
                record = service.predict(parts[1])
                current = record['prediction_id']
                emit(record)
            elif command == 'confirm' and len(parts) == 1:
                if current is None:
                    raise ValueError('Predict a sentence before confirming it')
                emit(service.confirm(current))
                current = None
            elif command in ('correct', 'replace'):
                if current is None:
                    raise ValueError('Predict a sentence before entering a correction')
                reason = ''
                if command == 'replace':
                    if '::' not in parts or parts.index('::') < 2:
                        raise ValueError('Use replace REASON :: WORD-GLOSSES')
                    divider = parts.index('::')
                    reason, values = ' '.join(parts[1:divider]), parts[divider+1:]
                else:
                    values = parts[1:]
                emit(service.correct(current, values, replace=command == 'replace', reason=reason))
                current = None
            elif command == 'history' and len(parts) == 2:
                emit(project.history(parts[1]))
            elif command == 'search' and len(parts) > 1:
                from .review import search
                emit(search(project, ' '.join(parts[1:]), include_history=True))
            elif command == 'review' and len(parts) <= 2:
                from .review import review_queue
                emit(review_queue(project, limit=int(parts[1]) if len(parts) == 2 else 10))
            elif command == 'status' and len(parts) == 1:
                emit(project_status(project))
            elif command == 'save' and len(parts) == 1:
                project.save()
                print('Saved.')
            elif command == 'reload' and len(parts) == 1:
                project = store.open(path)
                service, current = TeachingService(project), None
                print('Reloaded saved project; predict again before answering.')
            elif command == 'export' and len(parts) == 2:
                project.export(Path(parts[1]))
                print(f'Exported to {parts[1]}')
            else:
                raise ValueError('Unknown command or arguments. Type help.')
        except (ValueError, OSError, KeyError, TypeError) as exc:
            print(f'Error: {exc}')


def main(argv=None, *, store=None):
    parser = argparse.ArgumentParser(description='Teach and review aligned word glosses in a language project')
    commands = parser.add_subparsers(dest='command', required=True)
    parsers = {}
    for name in ('init', 'submit', 'predict', 'confirm', 'correct', 'history', 'search', 'review',
                 'status', 'save', 'export', 'shell', 'calibrate'):
        sub = commands.add_parser(name)
        sub.add_argument('--project', required=True, type=Path)
        sub.add_argument('--backend', choices=('workspace', 'fixture'), default='workspace')
        sub.add_argument('--json', action='store_true')
        parsers[name] = sub
    parsers['init'].add_argument('--name', required=True)
    parsers['init'].add_argument('--language', required=True)
    parsers['init'].add_argument('--mode', choices=('memory', 'analogy', 'rules'), default='rules')
    parsers['submit'].add_argument('--id', required=True)
    parsers['submit'].add_argument('--text', required=True)
    parsers['predict'].add_argument('--id', required=True)
    for name in ('confirm', 'correct'):
        parsers[name].add_argument('--prediction', required=True)
        parsers[name].add_argument('--operation-id')
    parsers['correct'].add_argument('--glosses', nargs='+', required=True)
    parsers['correct'].add_argument('--replace', action='store_true')
    parsers['correct'].add_argument('--reason', default='')
    parsers['correct'].add_argument('--expected-revision', type=int)
    parsers['history'].add_argument('--id', required=True)
    parsers['search'].add_argument('--query', required=True)
    parsers['search'].add_argument('--history', action='store_true')
    parsers['review'].add_argument('--limit', type=int, default=10)
    parsers['review'].add_argument('--include-reviewed', action='store_true')
    parsers['review'].add_argument('--calibration', type=Path)
    parsers['export'].add_argument('--output', type=Path, required=True)
    parsers['calibrate'].add_argument('--fit', type=Path, required=True)
    parsers['calibrate'].add_argument('--validation', type=Path, required=True)
    parsers['calibrate'].add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        backend = store if store is not None else _store(args.backend)
        if args.command == 'init':
            project = backend.create(args.project, name=args.name, language=args.language, mode=args.mode)
            emit({**project_status(project), 'backend': args.backend}, args.json)
            return
        if args.command == 'shell':
            shell(backend, args.project)
            return
        project = backend.open(args.project)
        service = TeachingService(project)
        if args.command == 'submit':
            result = service.submit(args.id, args.text)
        elif args.command == 'predict':
            result = service.predict(args.id)
        elif args.command == 'confirm':
            result = service.confirm(args.prediction, operation_id=args.operation_id)
        elif args.command == 'correct':
            result = service.correct(args.prediction, args.glosses, operation_id=args.operation_id,
                                     expected_revision=args.expected_revision, replace=args.replace, reason=args.reason)
        elif args.command == 'history':
            result = project.history(args.id)
        elif args.command == 'search':
            from .review import search
            result = search(project, args.query, include_history=args.history)
        elif args.command == 'review':
            from .review import review_queue
            from .review_calibration import Calibration
            calibration = Calibration.load(args.calibration) if args.calibration else None
            result = review_queue(project, limit=args.limit, include_reviewed=args.include_reviewed, calibration=calibration)
        elif args.command == 'calibrate':
            from .review_calibration import calibrate_files
            result = calibrate_files(project, args.fit, args.validation, args.output)
        elif args.command == 'export':
            project.export(args.output)
            result = {'exported': str(args.output)}
        else:
            if args.command == 'save':
                project.save()
            result = project_status(project)
        emit(result, args.json)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f'Teaching error: {exc}\n')


if __name__ == '__main__':
    main()
