"""Loopback-only local browser interface for language projects."""
import base64
import binascii
from http import HTTPStatus
import io
import json
import re
from urllib.parse import parse_qs
from pathlib import Path
import tempfile
import zipfile

from .project import (LanguageProject, list_projects, project_path, UNDETERMINED_LANGUAGE, GOVERNANCE_FIELDS,
                      AnnotationRevisionConflict, ProjectWriteConflict)


# The browser interface lives beside this module so it can be edited as plain HTML.
PAGE = Path(__file__).with_name('ui.html').read_text(encoding='utf-8')


class GlossWebApp:
    def __init__(self, workspace):
        self.workspace = Path(workspace).expanduser().resolve()
        self.project = None

    @staticmethod
    def _response(start_response, status, body, content_type='application/json; charset=utf-8', headers=()):
        payload = body.encode('utf-8') if isinstance(body, str) else body
        start_response(f'{status.value} {status.phrase}', [
            ('Content-Type', content_type), ('Content-Length', str(len(payload))),
            ('X-Content-Type-Options', 'nosniff'), ('X-Frame-Options', 'DENY'),
            ('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
            ('Referrer-Policy', 'no-referrer'), ('Cache-Control', 'no-store'), *headers,
        ])
        return [payload]

    @staticmethod
    def _json(start_response, value, status=HTTPStatus.OK):
        return GlossWebApp._response(start_response, status, json.dumps(value, ensure_ascii=False, allow_nan=False))

    @staticmethod
    def _body(environ):
        try:
            length = int(environ.get('CONTENT_LENGTH') or 0)
        except ValueError as exc:
            raise ValueError('Invalid Content-Length header') from exc
        if length < 0 or length > 36 * 1024 * 1024:
            raise ValueError('Request body is too large')
        try:
            value = json.loads(environ['wsgi.input'].read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError('Request body must be valid UTF-8 JSON') from exc
        if not isinstance(value, dict):
            raise ValueError('Request body must be a JSON object')
        return value

    def _active(self):
        if self.project is None:
            raise ValueError('Open or create a project first')
        return self.project

    def __call__(self, environ, start_response):
        method = environ['REQUEST_METHOD']
        path = environ['PATH_INFO']
        host = environ.get('HTTP_HOST', '')
        if not re.fullmatch(r'(127\.0\.0\.1|localhost):[0-9]{1,5}', host):
            return self._json(start_response, {'error': 'Local requests only'}, HTTPStatus.FORBIDDEN)
        origin = environ.get('HTTP_ORIGIN')
        if (origin and origin != f'http://{host}') or environ.get('HTTP_SEC_FETCH_SITE') == 'cross-site':
            return self._json(start_response, {'error': 'Cross-origin requests are blocked'}, HTTPStatus.FORBIDDEN)
        if method == 'POST' and environ.get('CONTENT_TYPE', '').split(';')[0] != 'application/json':
            return self._json(start_response, {'error': 'Use application/json'}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        if path == '/' and method == 'GET':
            return self._response(start_response, HTTPStatus.OK, PAGE, 'text/html; charset=utf-8')
        if path.startswith('/api/'):
            host = environ.get('HTTP_HOST', '')
            if not (host.startswith('127.0.0.1:') or host.startswith('localhost:')):
                return self._json(start_response, {'error': 'Local requests only'}, HTTPStatus.FORBIDDEN)
        try:
            identifier = environ.get('HTTP_X_PROJECT_ID')
            if identifier:
                matches = [item for item in list_projects(self.workspace) if item['project_id'] == identifier]
                if len(matches) != 1:
                    raise ValueError('Select an existing project')
                self.project = LanguageProject.open(self.workspace / f'{identifier}.dproj')
            elif self.project is not None:
                self.project = LanguageProject.open(self.project.path)
            if path == '/api/demo' and method == 'POST':
                import uuid
                name = 'Demo ' + uuid.uuid4().hex[:8]
                project = LanguageProject.create(project_path(self.workspace, name), name, 'invented-demo')
                project.data['governance'] = {'owner': 'Disposable example', 'license': 'Invented workflow fixture', 'consent': 'No real language or community data', 'provenance': 'Bundled demo.tsv', 'retention': 'Delete at any time', 'conventions': 'One gloss per whitespace-delimited word'}
                project.add_corpus('demo.tsv', Path(__file__).with_name('demo.tsv').read_text(), 'tsv')
                return self._json(start_response, {'project_id': project.data['project_id']}, HTTPStatus.CREATED)
            if path == '/api/governance' and method == 'POST':
                value = self._body(environ)
                if set(value) != set(GOVERNANCE_FIELDS) or any(not isinstance(v, str) or len(v) > 4000 for v in value.values()):
                    raise ValueError('Provide all governance fields, each at most 4000 characters')
                project = self._active()
                project.data['governance'] = value
                project.save()
                return self._json(start_response, {'saved': True})
            if path == '/api/history' and method == 'GET':
                return self._json(start_response, self._active().data['annotation_history'])
            if path == '/api/delete' and method == 'POST':
                project = self._active()
                if self._body(environ).get('name') != project.data['name']:
                    raise ValueError('Type the exact project name to delete it')
                project.save()  # Respect another writer's lock before removal.
                project.path.unlink()
                self.project = None
                return self._json(start_response, {'deleted': True})
            if path == '/api/annotations' and method == 'GET':
                project = self._active()
                latest = project._latest_annotations()
                rows = [{'id': row['id'], 'tokens': row['tokens'], 'glosses': list(latest[row['id']].glosses) if row['id'] in latest else None, 'reviewed': row['id'] in latest} for row in project.data['sentences']]
                fmt = parse_qs(environ.get('QUERY_STRING', '')).get('format', ['jsonl'])[0]
                if fmt == 'tsv':
                    payload = ''.join(' '.join(row['tokens']) + '\t' + (' '.join(row['glosses']) if row['reviewed'] else '') + '\n' for row in rows)
                    content_type = 'text/tab-separated-values; charset=utf-8'
                elif fmt == 'jsonl':
                    payload = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows)
                    content_type = 'application/x-ndjson; charset=utf-8'
                else:
                    raise ValueError('Export format must be tsv or jsonl')
                return self._response(start_response, HTTPStatus.OK, payload, content_type, [('Content-Disposition', f'attachment; filename="annotations.{fmt}"')])
            if path == '/api/projects' and method == 'GET':
                return self._json(start_response, list_projects(self.workspace))
            if path == '/api/projects' and method == 'POST':
                value = self._body(environ)
                name = value.get('name')
                destination = project_path(self.workspace, name)
                if destination.exists():
                    raise ValueError('A project with that name already exists')
                code = value.get('language_id')
                project = LanguageProject.create(destination, name, code.strip() if isinstance(code, str) and code.strip() else UNDETERMINED_LANGUAGE)
                if value.get('description'):
                    project.update_language(description=value['description'])
                return self._json(start_response, project.summary(), HTTPStatus.CREATED)
            if path == '/api/language' and method == 'POST':
                value = self._body(environ)
                if set(value) - {'name', 'language_id', 'description'}:
                    raise ValueError('Language details accept name, language_id and description only')
                project = self._active()
                project.update_language(**value)
                return self._json(start_response, project.summary())
            if path == '/api/performance' and method == 'GET':
                rows = []
                for path_ in sorted(self.workspace.glob('*.dproj')):
                    project = LanguageProject.open(path_)
                    checks = project.unusual_glosses(limit=0)
                    rows.append({**project.summary(), 'performance': project.performance(),
                                 'unusual': {'count': checks['count'], 'kept': checks['kept']}})
                return self._json(start_response, rows)
            if path == '/api/checks' and method == 'GET':
                return self._json(start_response, self._active().unusual_glosses())
            if path == '/api/checks/keep' and method == 'POST':
                value = self._body(environ)
                project = self._active()
                project.keep_gloss(value.get('id'), value.get('index'), value.get('gloss'))
                return self._json(start_response, project.unusual_glosses())
            if path == '/api/knowledge' and method == 'GET':
                return self._json(start_response, self._active().knowledge())
            if path == '/api/open' and method == 'POST':
                identifier = self._body(environ).get('project_id')
                matches = [item for item in list_projects(self.workspace) if item['project_id'] == identifier]
                if len(matches) != 1:
                    raise ValueError('Select an existing project')
                self.project = LanguageProject.open(self.workspace / f'{identifier}.dproj')
                return self._json(start_response, {'opened': identifier})
            if path == '/api/project' and method == 'GET':
                project = self._active()
                return self._json(start_response, {
                    **project.summary(), 'model_config': project.data['model_config'],
                    'annotations': project.annotation_count, 'governance': project.data.get('governance', {}),
                    'corpora': project.data['corpora'],
                })
            if path == '/api/import/preview' and method == 'POST':
                value = self._body(environ)
                preview = self._active().preview_corpus(
                    value.get('name'), value.get('content'), value.get('format', 'auto'))
                return self._json(start_response, preview)
            if path == '/api/import' and method == 'POST':
                value = self._body(environ)
                count = self._active().add_corpus(value.get('name'), value.get('content'), value.get('format', 'auto'))
                return self._json(start_response, {'sentences': count}, HTTPStatus.CREATED)
            if path == '/api/queue' and method == 'GET':
                return self._json(start_response, self._active().queue())
            if path == '/api/correct' and method == 'POST':
                value = self._body(environ)
                changed = self._active().correct(value.get('id'), value.get('glosses'),
                                                 expected_revision=value.get('expected_revision'))
                return self._json(start_response, {'changed': changed})
            if path == '/api/export' and method == 'GET':
                project = self._active()
                with tempfile.TemporaryDirectory() as directory:
                    archive = project.export(Path(directory) / f'{project.data["project_id"]}.zip')
                    payload = archive.read_bytes()
                return self._response(start_response, HTTPStatus.OK, payload, 'application/zip', [
                    ('Content-Disposition', f'attachment; filename="{project.data["project_id"]}.zip"'),
                ])
            if path == '/api/restore' and method == 'POST':
                value = self._body(environ)
                name = value.get('name')
                destination = project_path(self.workspace, name)
                if destination.exists():
                    raise ValueError('A project with that name already exists')
                try:
                    archive = base64.b64decode(value.get('archive', ''), validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise ValueError('Backup must be a base64-encoded project ZIP') from exc
                if len(archive) > 27 * 1024 * 1024:
                    raise ValueError('Project backup is too large')
                project = LanguageProject.restore(io.BytesIO(archive), destination)
                project.data['project_id'] = destination.stem
                project.data['name'] = name.strip()
                project.save()
                return self._json(start_response, {'project_id': project.data['project_id']}, HTTPStatus.CREATED)
            return self._json(start_response, {'error': 'Not found'}, HTTPStatus.NOT_FOUND)
        except (FileExistsError, AnnotationRevisionConflict, ProjectWriteConflict) as exc:
            return self._json(start_response, {'error': str(exc)}, HTTPStatus.CONFLICT)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
            return self._json(start_response, {'error': str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            return self._json(start_response, {'error': str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)


def serve(workspace, port=8765):
    from wsgiref.simple_server import make_server

    from wsgiref.simple_server import WSGIRequestHandler
    class LocalRequestHandler(WSGIRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def log_message(self, format, *args):
            pass

    app = GlossWebApp(workspace)
    with make_server('127.0.0.1', port, app, handler_class=LocalRequestHandler) as server:
        print(f'Decipher Lab listening at http://127.0.0.1:{server.server_port}/')
        server.serve_forever()
