"""Run a fictional pilot through the same endpoints used by the browser.

Creates a practice workspace, a completed/restored workspace, and a readable
transcript. Does not contact any external service or alter existing projects.
"""
import argparse
import base64
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from decipher.gloss_web import GlossWebApp


def run(destination):
    destination.mkdir(parents=True, exist_ok=False)
    workspace = destination / 'projects'
    app = GlossWebApp(workspace)
    active = None
    transcript = ['# Fictional pilot: Maya reviews a new field session', '',
                  'All names, words, labels, permissions, and decisions are invented. '
                  'This is a workflow demonstration, not a language-quality benchmark.', '']

    def call(path, data=None, expected=200):
        payload = json.dumps(data).encode() if data is not None else b''
        route, _, query = path.partition('?')
        env = {'REQUEST_METHOD': 'POST' if data is not None else 'GET', 'PATH_INFO': route,
               'QUERY_STRING': query, 'HTTP_HOST': '127.0.0.1:8765',
               'CONTENT_TYPE': 'application/json', 'CONTENT_LENGTH': str(len(payload)),
               'wsgi.input': io.BytesIO(payload)}
        if active:
            env['HTTP_X_PROJECT_ID'] = active
        response = {}
        raw = b''.join(app(env, lambda status, headers: response.update(status=int(status[:3]))))
        if response['status'] != expected:
            raise RuntimeError(f'{path}: expected {expected}, got {response["status"]}: {raw.decode()}')
        return raw

    def api(path, data=None, expected=200):
        return json.loads(call(path, data, expected))

    def log(title, text):
        transcript.extend([f'## {title}', '', text, ''])
        print(f'{title}: {text}')

    def show_queue(queue):
        lines = ['| Source | Actual model suggestion before review | Status |',
                 '| --- | --- | --- |']
        for item in queue:
            if not item['annotated']:
                labels = ' '.join(word['gloss'] or '[unknown]' for word in item['predictions'])
                status = 'Tentative draft' if any(word.get('provisional') for word in item['predictions']) else 'Known-form evidence; still unreviewed'
                lines.append(f'| {" ".join(item["tokens"])} | {labels} | {status} |')
        transcript.extend(lines + [''])

    sample = ROOT / 'examples' / 'pilot'
    active = api('/api/projects', {'name': '01 Maya - review practice', 'language_id': 'invented-demo'}, 201)['project_id']
    api('/api/open', {'project_id': active})
    policy = {'owner': 'Fictional Cedar Language Workshop', 'license': 'Invented training fixture; no real community corpus',
              'consent': 'Fictional scenario only; no actual consent represented',
              'provenance': 'Hand-written examples/pilot files in this repository',
              'retention': 'Disposable demonstration; remove when finished',
              'conventions': 'Whitespace words; one gloss per word; PL plural; PST past; lowercase lexical labels'}
    api('/api/governance', policy)
    log('1. Create a project and record the data policy', 'Maya, a fictional annotator, opens a separate language workspace and records provenance and annotation conventions.')
    for filename, fmt in [('01-reviewed-seed.tsv', 'tsv'), ('02-new-session.txt', 'text')]:
        data = {'name': filename, 'format': fmt, 'content': (sample / filename).read_text()}
        preview = api('/api/import/preview', data)
        count = api('/api/import', data, 201)['sentences']
        log('2. Import reviewed anchors' if fmt == 'tsv' else '3. Preview and import a new session',
            f'{filename}: preview reports {preview["sentence_count"]} sentences, {preview["annotated_count"]} supplied annotations, {preview["needs_review_count"]} needing review. Confirmed {count} sentences.')
    log('4. Inspect the suggestions', 'The following are actual model outputs from this run. Maya checks every suggestion against her fictional field notes. Scores are not accuracy probabilities.')
    show_queue(api('/api/queue'))
    # Save the pre-review state for hands-on browser practice.
    practice = call('/api/export')
    (destination / 'practice-backup.zip').write_bytes(practice)
    # Work on a separate restored copy, preserving the practice project's drafts.
    active = api('/api/restore', {'name': '02 Maya - completed session', 'archive': base64.b64encode(practice).decode()}, 201)['project_id']
    api('/api/open', {'project_id': active})
    decisions = json.loads((sample / 'reviewer-decisions.json').read_text())
    queue = api('/api/queue')
    transcript.extend(['| Source | Maya saves |', '| --- | --- |'])
    target = None
    for item in queue:
        if item['annotated']:
            continue
        source = ' '.join(item['tokens'])
        api('/api/correct', {'id': item['id'], 'glosses': decisions[source], 'expected_revision': item['revision']})
        transcript.append(f'| {source} | {" ".join(decisions[source])} |')
        if source == 'noka vel':
            target = item['id']
    transcript.append('')
    log('5. Save five reviewed sentences', 'Maya accepts or edits each draft. In particular, noka means water in her invented notes; spelling similarity cannot discover that meaning.')
    api('/api/correct', {'id': target, 'glosses': ['water', 'blossom'], 'expected_revision': 1})
    log('6. Revise an earlier decision', 'For noka vel, Maya changes water flower to water blossom. The earlier revision remains in history; this sentence now has revision 2. Other uses of vel are not silently rewritten.')
    bad = {'name': '03-misaligned-example.tsv', 'format': 'tsv', 'content': (sample / '03-misaligned-example.tsv').read_text()}
    error = api('/api/import/preview', bad, 400)
    log('7. Catch an import problem', f'The intentionally broken file is rejected before saving: {error["error"]}')
    duplicate = api('/api/import/preview', {'name': '02-new-session.txt', 'format': 'text', 'content': (sample / '02-new-session.txt').read_text()})
    if not duplicate['duplicate']:
        raise RuntimeError('Expected duplicate detection')
    log('8. Avoid a duplicate import', 'Previewing the same new-session file again marks it as already imported.')
    expected_rows = call('/api/annotations?format=jsonl')
    (destination / 'annotations.jsonl').write_bytes(expected_rows)
    (destination / 'annotations.tsv').write_bytes(call('/api/annotations?format=tsv'))
    (destination / 'revision-history.json').write_bytes(call('/api/history'))
    backup = call('/api/export')
    (destination / 'completed-backup.zip').write_bytes(backup)
    summary = api('/api/project')
    if (summary['sentences'], summary['annotations']) != (14, 14):
        raise RuntimeError('Unexpected completed counts')
    log('9. Export and stop for the day', f'{summary["sentences"]} total sentences, {summary["annotations"]} reviewed, 15 annotation revisions. Saved TSV, JSONL, revision history, and ZIP backup.')
    # Verify recovery through a fresh app instance with a completely empty workspace.
    app = GlossWebApp(destination / 'recovery-check')
    active = None
    active = api('/api/restore', {'name': 'Recovered session', 'archive': base64.b64encode(backup).decode()}, 201)['project_id']
    api('/api/open', {'project_id': active})
    if call('/api/annotations?format=jsonl') != expected_rows or api('/api/project')['governance'] != policy:
        raise RuntimeError('Recovery did not preserve annotations and governance')
    if len(api('/api/history')) != 15:
        raise RuntimeError('Recovery did not preserve revision history')
    log('10. Recover on a fresh workspace', 'Restored the completed ZIP into an empty workspace and verified identical annotation exports, project policy, and all 15 revisions.')
    transcript.extend(['## Try it yourself', '', 'Start the server with:', '', '```sh',
                       f'python3 -m decipher --workspace-dir "{workspace}"', '```', '',
                       'Open http://127.0.0.1:8765. Select **01 Maya - review practice** for five unreviewed sentences, or **02 Maya - completed session** to inspect the final labels and download history.', ''])
    (destination / 'WALKTHROUGH.md').write_text('\n'.join(transcript))
    print(f'\nTranscript and exports: {destination}\nBrowser workspace: {workspace}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('demo-run'))
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if destination.exists():
        parser.error('Choose a new output directory; existing walkthroughs are never overwritten.')
    run(destination)


if __name__ == '__main__':
    main()
