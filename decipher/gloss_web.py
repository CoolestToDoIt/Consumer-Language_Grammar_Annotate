"""Loopback-only local browser interface for language projects."""
import base64
import binascii
from http import HTTPStatus
import io
import json
from pathlib import Path
import tempfile
import zipfile

from .project import LanguageProject, list_projects, project_path


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Decipher Lab</title>
<style>
body{font:16px system-ui,sans-serif;max-width:1050px;margin:2rem auto;padding:0 1rem;color:#202124}
section,.sentence{border:1px solid #dadce0;border-radius:8px;padding:1rem;margin:1rem 0}
form{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center}
input,select,button{font:inherit;padding:.45rem}
.word{display:inline-flex;flex-direction:column;gap:.25rem;margin:.5rem .7rem .5rem 0;vertical-align:top}
.word input{width:10rem}.evidence{font-size:.8rem;color:#555;max-width:14rem}
.unknown{color:#a33}.known{color:#27632a}#message{min-height:1.5rem}
</style>
</head>
<body>
<h1>Decipher Lab</h1>
<p>Local source-only gloss workspace. Candidate scores are uncalibrated evidence, not confidence percentages.</p>
<section>
<h2>Project</h2>
<form id="open"><label for="projects">Open</label><select id="projects"></select><button>Open project</button></form>
<form id="create"><input name="name" aria-label="Project name" placeholder="Project name" required><input name="language" aria-label="Language ID" placeholder="Language ID" required><button>Create project</button></form>
<p id="project-summary"></p>
</section>
<section>
<h2>Import corpus</h2>
<p>Import UTF-8 plain text (one sentence per line), TSV (source words and optional glosses), or SIGMORPHON source/gloss tiers.</p>
<form id="import"><input name="file" type="file" aria-label="Corpus file" required><select name="format" aria-label="Corpus format"><option value="auto">Detect format</option><option value="text">Plain text</option><option value="tsv">TSV</option><option value="sigmorphon">SIGMORPHON</option></select><button>Import</button></form>
<form id="restore"><input name="name" aria-label="Name for restored project" placeholder="Name for restored project" required><input name="file" type="file" accept=".zip" aria-label="Project backup file" required><button>Restore backup</button></form>
<button id="export">Download project backup</button>
</section>
<section>
<h2>Sentence review</h2>
<button id="refresh">Refresh queue</button><div id="queue"></div>
</section>
<p id="message" role="status"></p>
<script>
const byId=id=>document.getElementById(id);
async function request(path,options={}){const response=await fetch(path,options);if(!response.ok){const body=await response.json();throw Error(body.error||response.statusText)}return response}
async function json(path,method,data){return (await request(path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})).json()}
function message(text){byId('message').textContent=text}
async function loadProjects(){const items=await (await request('/api/projects')).json();const select=byId('projects');select.replaceChildren();for(const item of items){const option=document.createElement('option');option.value=item.project_id;option.textContent=`${item.name} (${item.language_id})`;select.append(option)}}
async function openProject(id){await json('/api/open','POST',{project_id:id});await refresh();message('Project opened.')}
async function refresh(){const summary=await (await request('/api/project')).json();byId('project-summary').textContent=`${summary.name} — ${summary.language_id}; ${summary.sentences} sentences; ${summary.annotations} current annotations.`;const items=await (await request('/api/queue')).json();const queue=byId('queue');queue.replaceChildren();for(const item of items){const card=document.createElement('article');card.className='sentence';const heading=document.createElement('h3');heading.textContent=item.id;card.append(heading);const row=document.createElement('div');const inputs=[];for(let i=0;i<item.tokens.length;i++){const word=document.createElement('label');word.className='word';const source=document.createElement('strong');source.textContent=item.tokens[i];const input=document.createElement('input');input.value=item.predictions[i].gloss||'';input.setAttribute('aria-label',`Gloss for ${item.tokens[i]}`);const known=document.createElement('span');known.className=item.predictions[i].known_form?'known':'unknown';known.textContent=item.predictions[i].known_form?'known form':'unknown form';const evidence=document.createElement('span');evidence.className='evidence';const candidates=item.predictions[i].candidates.map(candidate=>`${candidate.gloss} [${candidate.kind}; evidence ${candidate.score}]`).join(' · ');evidence.textContent=candidates||'No candidate evidence';word.append(source,input,known,evidence);row.append(word);inputs.push(input)}card.append(row);const save=document.createElement('button');save.textContent=item.annotated?`Save revision ${item.revision+1}`:'Teach glosses';save.addEventListener('click',async()=>{try{await json('/api/correct','POST',{id:item.id,glosses:inputs.map(input=>input.value.trim())});message('Correction saved.');await refresh()}catch(error){message(error.message)}});card.append(save);queue.append(card)}}
byId('open').addEventListener('submit',async event=>{event.preventDefault();try{await openProject(byId('projects').value)}catch(error){message(error.message)}});
byId('create').addEventListener('submit',async event=>{event.preventDefault();const form=new FormData(event.currentTarget);try{const project=await json('/api/projects','POST',{name:form.get('name'),language_id:form.get('language')});await loadProjects();await openProject(project.project_id)}catch(error){message(error.message)}});
byId('import').addEventListener('submit',async event=>{event.preventDefault();const form=new FormData(event.currentTarget);const file=form.get('file');try{const content=await file.text();const result=await json('/api/import','POST',{name:file.name,format:form.get('format'),content});message(`Imported ${result.sentences} sentences.`);await refresh()}catch(error){message(error.message)}});
byId('restore').addEventListener('submit',async event=>{event.preventDefault();const form=new FormData(event.currentTarget);const file=form.get('file');try{const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let offset=0;offset<bytes.length;offset+=32768)binary+=String.fromCharCode(...bytes.subarray(offset,offset+32768));const result=await json('/api/restore','POST',{name:form.get('name'),archive:btoa(binary)});await loadProjects();await openProject(result.project_id)}catch(error){message(error.message)}});
byId('export').addEventListener('click',async()=>{try{const response=await request('/api/export');const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');link.href=url;link.download=response.headers.get('Content-Disposition').split('filename=')[1];document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);message('Project backup downloaded.')}catch(error){message(error.message)}});
byId('refresh').addEventListener('click',()=>refresh().catch(error=>message(error.message)));
loadProjects().catch(error=>message(error.message));
</script>
</body>
</html>
"""


class GlossWebApp:
    def __init__(self, workspace):
        self.workspace = Path(workspace).expanduser().resolve()
        self.project = None

    @staticmethod
    def _response(start_response, status, body, content_type='application/json; charset=utf-8', headers=()):
        payload = body.encode('utf-8') if isinstance(body, str) else body
        start_response(f'{status.value} {status.phrase}', [
            ('Content-Type', content_type), ('Content-Length', str(len(payload))),
            ('X-Content-Type-Options', 'nosniff'), ('Cache-Control', 'no-store'), *headers,
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
        if path == '/' and method == 'GET':
            return self._response(start_response, HTTPStatus.OK, PAGE, 'text/html; charset=utf-8')
        if path.startswith('/api/'):
            host = environ.get('HTTP_HOST', '')
            if not (host.startswith('127.0.0.1:') or host.startswith('localhost:')):
                return self._json(start_response, {'error': 'Local requests only'}, HTTPStatus.FORBIDDEN)
        try:
            if path == '/api/projects' and method == 'GET':
                return self._json(start_response, list_projects(self.workspace))
            if path == '/api/projects' and method == 'POST':
                value = self._body(environ)
                name = value.get('name')
                destination = project_path(self.workspace, name)
                if destination.exists():
                    raise ValueError('A project with that name already exists')
                project = LanguageProject.create(destination, name, value.get('language_id'))
                return self._json(start_response, {
                    'project_id': project.data['project_id'],
                    'name': project.data['name'],
                    'language_id': project.data['language_id'],
                }, HTTPStatus.CREATED)
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
                    'project_id': project.data['project_id'], 'name': project.data['name'],
                    'language_id': project.data['language_id'], 'model_config': project.data['model_config'],
                    'sentences': len(project.data['sentences']), 'annotations': project.annotation_count,
                })
            if path == '/api/import' and method == 'POST':
                value = self._body(environ)
                count = self._active().add_corpus(value.get('name'), value.get('content'), value.get('format', 'auto'))
                return self._json(start_response, {'sentences': count}, HTTPStatus.CREATED)
            if path == '/api/queue' and method == 'GET':
                return self._json(start_response, self._active().queue())
            if path == '/api/correct' and method == 'POST':
                value = self._body(environ)
                changed = self._active().correct(value.get('id'), value.get('glosses'))
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
        except FileExistsError as exc:
            return self._json(start_response, {'error': str(exc)}, HTTPStatus.CONFLICT)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
            return self._json(start_response, {'error': str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            return self._json(start_response, {'error': str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)


def serve(workspace, port=8765):
    from wsgiref.simple_server import make_server

    app = GlossWebApp(workspace)
    with make_server('127.0.0.1', port, app) as server:
        print(f'Decipher Lab listening at http://127.0.0.1:{server.server_port}/')
        server.serve_forever()
