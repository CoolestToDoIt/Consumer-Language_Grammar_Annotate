"""Loopback-only local browser interface for language projects."""
import base64
import binascii
from http import HTTPStatus
import io
import json
from pathlib import Path
import tempfile
import zipfile

from .project import (LanguageProject, list_projects, project_path,
                      AnnotationRevisionConflict, ProjectWriteConflict)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Decipher Lab</title>
<style>
body{font:16px system-ui,sans-serif;max-width:1040px;margin:2rem auto;padding:0 1rem;color:#202124;background:#fafafa}
header{margin-bottom:1.5rem}h1{margin-bottom:.2rem}h2{margin-top:0}
section,.sentence,.welcome{background:white;border:1px solid #dadce0;border-radius:10px;padding:1.1rem;margin:1rem 0}
form,.toolbar{display:flex;flex-wrap:wrap;gap:.65rem;align-items:center}
input,select,button{font:inherit;padding:.55rem .7rem}button{cursor:pointer;border:1px solid #777;border-radius:6px;background:#fff}
button.primary{background:#174ea6;color:white;border-color:#174ea6}
button:disabled{opacity:.5;cursor:not-allowed}
input[type=text],input:not([type]){min-width:12rem}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.6rem}
.step{padding:.75rem;background:#f4f7fc;border-radius:8px}
.sentence{margin:.75rem 0}.sentence h3{overflow-wrap:anywhere}
.word-row{display:flex;flex-wrap:wrap;gap:.5rem}
.word{display:flex;flex-direction:column;gap:.35rem;padding:.65rem;border:1px solid #ddd;border-radius:8px;min-width:190px;flex:1}
.word input{width:100%;box-sizing:border-box}
.evidence{font-size:.82rem;color:#555;overflow-wrap:anywhere}
.tentative{color:#8a4b00}.known{color:#27632a}.empty{color:#666}
.preview-row{padding:.45rem 0;border-bottom:1px solid #eee}
#message{min-height:1.5rem}#queue:empty:after{content:"No sentences match this view." ;display:block;color:#666;padding:1rem 0}
.muted{color:#555}.hidden{display:none!important}
</style>
</head>
<body>
<header><h1>Decipher Lab</h1><p class="muted">Build a reviewed word-gloss corpus with suggestions you can correct. Guesses for unfamiliar forms are drafts, never verified answers.</p></header>
<section>
<div class="steps"><div class="step"><strong>1. Open a project</strong><p>Create one project per language or reopen your work.</p></div><div class="step"><strong>2. Import examples</strong><p>Preview sentences and alignment before adding them.</p></div><div class="step"><strong>3. Review drafts</strong><p>Edit suggestions, save corrections, and improve later guesses.</p></div></div>
<h2>Project</h2>
<div class="toolbar"><form id="open"><label for="projects">Your projects</label><select id="projects" aria-label="Your projects"></select><button id="open-button">Open</button></form>
<button id="new-project-toggle" type="button">Create project</button></div>
<form id="create" class="hidden"><input name="name" aria-label="Project name" placeholder="Project name" required><input name="language" aria-label="Language ID" placeholder="Language ID" required><button class="primary">Create and open</button><button id="cancel-create" type="button">Cancel</button></form>
<p id="project-summary" class="muted">Create a project or choose one to begin.</p>
</section>
<section id="import-section" class="hidden">
<h2>Import sentences</h2><p class="muted">Plain text: one sentence per line. TSV: source words, optionally followed by aligned gloss words. SIGMORPHON: source and gloss tiers. Only source and gloss are used.</p>
<form id="import"><input name="file" type="file" aria-label="Corpus file" required><select name="format" aria-label="Corpus format"><option value="auto">Detect format</option><option value="text">Plain text</option><option value="tsv">TSV</option><option value="sigmorphon">SIGMORPHON</option></select><button class="primary">Preview import</button></form>
<div id="import-preview" class="hidden"><h3>Review this import</h3><p id="preview-summary"></p><div id="preview-examples"></div><div class="toolbar"><button id="confirm-import" class="primary" type="button">Add sentences</button><button id="cancel-import" type="button">Cancel</button></div></div>
<div class="toolbar"><form id="restore"><input name="name" aria-label="Name for restored project" placeholder="Name for restored project" required><input name="file" type="file" accept=".zip" aria-label="Project backup file" required><button>Restore backup</button></form><button id="export" type="button">Download backup</button></div>
</section>
<section id="review-section" class="hidden">
<h2>Review sentences</h2><p class="muted">Unfamiliar forms receive a tentative draft based on the closest examples in this project. Review and correct every draft before it becomes verified.</p>
<div class="toolbar"><input id="search" type="search" aria-label="Filter sentences" placeholder="Filter by sentence, word, or gloss"><label><input id="show-reviewed" type="checkbox"> Show reviewed sentences</label><button id="refresh" type="button">Refresh</button></div>
<p id="queue-summary" class="muted"></p><div id="queue"></div>
</section>
<p id="message" role="status"></p>
<script>
const byId=id=>document.getElementById(id);
let activeProject=null, stagedImport=null, queueItems=[];
async function request(path,options={}){const response=await fetch(path,options);if(!response.ok){let detail;try{detail=(await response.json()).error}catch{detail=response.statusText}throw Error(detail||response.statusText)}return response}
async function json(path,method,data){return (await request(path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})).json()}
function message(text){byId('message').textContent=text}
function setProjectSections(open){byId('import-section').classList.toggle('hidden',!open);byId('review-section').classList.toggle('hidden',!open)}
async function loadProjects(preferred=null){const items=await (await request('/api/projects')).json();const select=byId('projects');select.replaceChildren();for(const item of items){const option=document.createElement('option');option.value=item.project_id;option.textContent=`${item.name} (${item.language_id})`;select.append(option)}const saved=preferred||localStorage.getItem('decipher-project');if(saved&&items.some(item=>item.project_id===saved)){select.value=saved;await openProject(saved)}else if(items.length===1){select.value=items[0].project_id;await openProject(items[0].project_id)}}
async function openProject(id){if(!id)throw Error('Create a project or choose one to open.');await json('/api/open','POST',{project_id:id});activeProject=id;localStorage.setItem('decipher-project',id);setProjectSections(true);byId('project-summary').textContent='Loading project…';await refresh();message('Project ready. Review the suggested drafts and correct them before saving.')}
function renderPreview(preview){byId('import-preview').classList.remove('hidden');byId('preview-summary').textContent=preview.duplicate?`This exact corpus is already in the project (${preview.sentence_count} sentences); it will not be imported twice.`:`${preview.sentence_count} sentences: ${preview.annotated_count} already glossed and ${preview.needs_review_count} need your review.`;const examples=byId('preview-examples');examples.replaceChildren();for(const example of preview.examples){const row=document.createElement('div');row.className='preview-row';row.textContent=example.tokens.join(' ')+'  →  '+(example.glosses?example.glosses.join(' '):'Needs gloss review');examples.append(row)}byId('confirm-import').disabled=preview.duplicate;byId('confirm-import').textContent=preview.duplicate?'Already in this project':`Add ${preview.sentence_count} sentences`}
function renderQueue(){const queue=byId('queue');queue.replaceChildren();const showReviewed=byId('show-reviewed').checked;const query=byId('search').value.trim().toLocaleLowerCase();const filtered=queueItems.filter(item=>(showReviewed||!item.annotated)&&(!query||[item.id,...item.tokens,...item.predictions.map(word=>word.gloss||'')].join(' ').toLocaleLowerCase().includes(query)));byId('queue-summary').textContent=`${filtered.length} sentence${filtered.length===1?'':'s'} to review${showReviewed?' (including reviewed)':''}. Unknown forms show a clearly labeled provisional draft when examples are available.`;for(const item of filtered){const card=document.createElement('article');card.className='sentence';const heading=document.createElement('h3');heading.textContent=item.id;card.append(heading);const row=document.createElement('div');row.className='word-row';const inputs=[];for(let i=0;i<item.tokens.length;i++){const prediction=item.predictions[i];const word=document.createElement('label');word.className='word';const source=document.createElement('strong');source.textContent=item.tokens[i];const input=document.createElement('input');input.value=prediction.gloss||'';input.placeholder=prediction.gloss?'Review or replace this gloss':'Enter a gloss to create the first teaching example';input.setAttribute('aria-label',`Gloss for ${item.tokens[i]}`);const status=document.createElement('span');if(prediction.known_form){status.className='known';status.textContent='Known form · grounded in this project'}else if(prediction.gloss!==null){status.className='tentative';status.textContent=prediction.candidates[0]?.score===0?'Weak draft guess · no spelling overlap; please correct':'Tentative draft guess · please review and correct'}else{status.className='empty';status.textContent='No grounded examples yet · add the first gloss'}const evidence=document.createElement('span');evidence.className='evidence';const candidates=prediction.candidates.map(candidate=>`${candidate.gloss} · ${candidate.kind}${candidate.provisional?' (draft)':''} · raw evidence ${Number(candidate.score).toPrecision(3)}`).join(' | ');evidence.textContent=candidates||'No model evidence yet. Your correction will establish an anchor.';word.append(source,input,status,evidence);row.append(word);inputs.push(input)}card.append(row);const save=document.createElement('button');save.className='primary';save.textContent=item.annotated?`Save revision ${item.revision+1}`:'Save reviewed glosses';save.addEventListener('click',async()=>{save.disabled=true;try{await json('/api/correct','POST',{id:item.id,glosses:inputs.map(input=>input.value.trim()),expected_revision:item.revision});message('Reviewed glosses saved; the project learned from your correction.');await refresh()}catch(error){message(error.message);save.disabled=false}});card.append(save);queue.append(card)}}
async function refresh(){if(!activeProject)throw Error('Open a project first.');const summary=await (await request('/api/project')).json();byId('project-summary').textContent=`${summary.name} · ${summary.language_id} · ${summary.sentences} sentences · ${summary.annotations} reviewed`;queueItems=await (await request('/api/queue')).json();renderQueue()}
byId('open').addEventListener('submit',async event=>{event.preventDefault();try{await openProject(byId('projects').value)}catch(error){message(error.message)}});
byId('new-project-toggle').addEventListener('click',()=>byId('create').classList.toggle('hidden'));
byId('cancel-create').addEventListener('click',()=>byId('create').classList.add('hidden'));
byId('create').addEventListener('submit',async event=>{event.preventDefault();const form=new FormData(event.currentTarget);try{const project=await json('/api/projects','POST',{name:form.get('name'),language_id:form.get('language')});byId('create').reset();byId('create').classList.add('hidden');await loadProjects(project.project_id)}catch(error){message(error.message)}});
byId('import').addEventListener('submit',async event=>{event.preventDefault();const form=new FormData(event.currentTarget);const file=form.get('file');if(!file||!file.size){message('Choose a corpus file first.');return}try{const content=await file.text();const preview=await json('/api/import/preview','POST',{name:file.name,format:form.get('format'),content});stagedImport={name:file.name,format:form.get('format'),content};renderPreview(preview);message('Check the preview before adding this corpus.')}catch(error){message(error.message)}});
byId('confirm-import').addEventListener('click',async()=>{if(!stagedImport)return;try{const result=await json('/api/import','POST',stagedImport);stagedImport=null;byId('import-preview').classList.add('hidden');byId('import').reset();message(`Added ${result.sentences} sentences. Review the draft glosses below.`);await refresh()}catch(error){message(error.message)}});
byId('cancel-import').addEventListener('click',()=>{stagedImport=null;byId('import-preview').classList.add('hidden');byId('import').reset();message('Import cancelled.')});
byId('restore').addEventListener('submit',async event=>{event.preventDefault();const form=new FormData(event.currentTarget);const file=form.get('file');try{const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let offset=0;offset<bytes.length;offset+=32768)binary+=String.fromCharCode(...bytes.subarray(offset,offset+32768));const result=await json('/api/restore','POST',{name:form.get('name'),archive:btoa(binary)});event.currentTarget.reset();await loadProjects(result.project_id)}catch(error){message(error.message)}});
byId('export').addEventListener('click',async()=>{try{const response=await request('/api/export');const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');link.href=url;link.download=response.headers.get('Content-Disposition').split('filename=')[1];document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);message('Project backup downloaded.')}catch(error){message(error.message)}});
byId('refresh').addEventListener('click',()=>refresh().catch(error=>message(error.message)));
byId('search').addEventListener('input',renderQueue);byId('show-reviewed').addEventListener('change',renderQueue);
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

    app = GlossWebApp(workspace)
    with make_server('127.0.0.1', port, app) as server:
        print(f'Decipher Lab listening at http://127.0.0.1:{server.server_port}/')
        server.serve_forever()
