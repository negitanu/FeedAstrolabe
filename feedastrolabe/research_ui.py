"""Japanese server-rendered research UI; app-wide CSRF covers all POST routes."""
from contextlib import contextmanager
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from .db import get_db
from . import research as r

research_ui=Blueprint('research',__name__,url_prefix='/workspaces')


@contextmanager
def errors():
    try:
        yield
    except r.ResearchMissing as exc:
        abort(404,description=str(exc))
    except r.ResearchConflict as exc:
        abort(409,description=str(exc))
    except ValueError as exc:
        abort(400,description=str(exc))


def identifier(value):
    try:
        number=int(value)
        if not 1<=number<=2**63-1:
            raise ValueError()
        return number
    except (ValueError,TypeError):
        abort(400,description='ID は正の整数で指定してください。')


def ui_page(sql,params=(),name='page',order='id DESC'):
    value=request.args.get(name,'1')
    if not value.isdecimal() or len(value)>10 or not 1<=int(value)<=2**31-1:
        abort(400,description='ページ番号が無効です。')
    total=get_db().execute('SELECT count(*) FROM ('+sql+')',params).fetchone()[0]
    pages=max(1,(total+29)//30)
    current=min(int(value),pages)
    rows=get_db().execute(sql+' ORDER BY '+order+' LIMIT 30 OFFSET ?',list(params)+[(current-1)*30]).fetchall()
    return {'rows':rows,'current':current,'pages':pages,'total':total,'name':name}


@research_ui.get('')
def index():
    archived=request.args.get('archived','false')
    if archived not in ('true','false'):
        abort(400)
    clauses,params=['archived=?'],[int(archived=='true')]
    query=request.args.get('q','').strip()
    if len(query)>200:
        abort(400)
    if query:
        clauses.append("(title LIKE ? ESCAPE '!' OR purpose LIKE ? ESCAPE '!' OR questions LIKE ? ESCAPE '!')")
        escaped=query.replace('!','!!').replace('%','!%').replace('_','!_')
        params.extend(['%'+escaped+'%']*3)
    tag=request.args.get('tag','')
    if tag:
        tag_id=identifier(tag)
        with errors():
            r.find('tag',tag_id)
        clauses.append('EXISTS(SELECT 1 FROM workspace_tags t WHERE t.workspace_id=workspaces.id AND t.tag_id=?)')
        params.append(tag_id)
    listing=ui_page('SELECT * FROM workspaces WHERE '+' AND '.join(clauses),params)
    return render_template('workspaces.html',listing=listing,archived=archived,query=query,tag=tag,tags=r.options('tag',identifier(tag) if tag else None),tags_for=lambda row:r.tag_rows('workspace',row['id']))


@research_ui.post('')
def create():
    with errors():
        workspace_id=r.create_workspace({name:request.form.get(name,'') for name in ('title','purpose','questions','status','classification')})
    flash('調査案件を作成しました。','success')
    return redirect(url_for('research.detail',workspace_id=workspace_id))


@research_ui.get('/<int:workspace_id>')
def detail(workspace_id):
    with errors():
        workspace=r.find('workspace',workspace_id)
    tag=request.args.get('tag','')
    clauses,params=[r.WORKSPACE_ARTICLES],[workspace_id,workspace_id]
    if tag:
        with errors():
            r.find('tag',identifier(tag))
        clauses.append('EXISTS(SELECT 1 FROM article_tags t WHERE t.article_id=a.id AND t.tag_id=?)')
        params.append(identifier(tag))
    query=request.args.get('q','').strip()
    if len(query)>200:
        abort(400)
    if query:
        escaped=query.replace('!','!!').replace('%','!%').replace('_','!_')
        clauses.append("(a.title LIKE ? ESCAPE '!' OR a.search_text LIKE ? ESCAPE '!')")
        params.extend(['%'+escaped+'%']*2)
    db=get_db()
    articles=ui_page('SELECT a.*,f.title AS feed_title,EXISTS(SELECT 1 FROM workspace_articles wa WHERE wa.workspace_id=? AND wa.article_id=a.id) AS direct FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE '+' AND '.join(clauses),[workspace_id]+params,'articles_page','a.id DESC')
    feeds=ui_page('SELECT f.* FROM feeds f JOIN workspace_feeds wf ON wf.feed_id=f.id WHERE wf.workspace_id=?',[workspace_id],'feeds_page','f.id DESC')
    notes_archived=request.args.get('notes_archived','false')
    if notes_archived not in ('true','false'):
        abort(400)
    notes=ui_page('SELECT * FROM notes WHERE workspace_id=? AND archived=?',[workspace_id,int(notes_archived=='true')],'notes_page')
    return render_template('workspace.html',item=workspace,articles=articles,feeds=feeds,notes=notes,notes_archived=notes_archived,query=query,tag=tag,
                           tags=r.tag_rows('workspace',workspace_id),tag_options=r.options('tag',identifier(tag) if tag else None),
                           feed_options=db.execute('SELECT id,title FROM feeds ORDER BY id DESC LIMIT 100').fetchall())


@research_ui.post('/<int:workspace_id>/edit')
def edit(workspace_id):
    from .settings_pages import object_redirect
    with errors():
        r.update_workspace(workspace_id,{name:request.form.get(name,'') for name in ('title','purpose','questions','status','classification')})
    flash('調査案件を保存しました。','success')
    return redirect(object_redirect('workspaces', workspace_id, 'research.detail', workspace_id=workspace_id))


@research_ui.post('/<int:workspace_id>/archive')
def archive(workspace_id):
    from .settings_pages import object_redirect
    if request.form.get('archived') not in ('true','false'):
        abort(400)
    with errors():
        r.update_workspace(workspace_id,{'archived':request.form['archived']=='true'})
    flash('案件をアーカイブしました。' if request.form['archived']=='true' else '案件を再開しました。','success')
    return redirect(object_redirect('workspaces', workspace_id, 'research.detail', workspace_id=workspace_id))


@research_ui.post('/<int:workspace_id>/links/<kind>')
def link(workspace_id,kind):
    if kind not in ('feed','article','tag') or request.form.get('operation','add') not in ('add','remove'):
        abort(400)
    with errors():
        r.associate('workspace',workspace_id,kind,identifier(request.form.get('target_id')),request.form.get('operation')=='remove')
    return redirect(url_for('research.detail',workspace_id=workspace_id))


@research_ui.post('/article/<int:article_id>/link')
def article_link(article_id):
    workspace_id=identifier(request.form.get('workspace_id'))
    with errors():
        r.associate('workspace',workspace_id,'article',article_id)
    return redirect(url_for('research.detail',workspace_id=workspace_id))


@research_ui.post('/tags')
def create_tag():
    with errors():
        r.save_tag({'name':request.form.get('name','')})
    flash('共有タグを作成しました。','success')
    return redirect(url_for('settings_pages.page',section='tags') if request.form.get('return_to') == 'settings-tags' else url_for('research.index'))


@research_ui.post('/tags/<int:tag_id>')
def edit_tag(tag_id):
    with errors():
        r.save_tag({'name':request.form.get('name','')},tag_id)
    return redirect(url_for('settings_pages.page',section='tags') if request.form.get('return_to') == 'settings-tags' else url_for('research.index'))


@research_ui.post('/tags/<kind>/<int:target_id>')
def tag_link(kind,target_id):
    if kind not in ('article','note') or request.form.get('operation','add') not in ('add','remove'):
        abort(400)
    with errors():
        r.associate(kind,target_id,'tag',identifier(request.form.get('tag_id')),request.form.get('operation')=='remove')
    return redirect(url_for('research.note',note_id=target_id) if kind=='note' else url_for('index',article=target_id))


@research_ui.post('/<int:workspace_id>/notes')
def create_note(workspace_id):
    with errors():
        note_id=r.create_note(workspace_id,{name:request.form.get(name,'') for name in ('title','body','label')})
    return redirect(url_for('research.note',note_id=note_id))


def note_view(note_id,submitted=None,status=200,error=None):
    with errors():
        note=r.find('note',note_id)
        workspace=r.find('workspace',note['workspace_id'])
    history=ui_page('SELECT * FROM note_revisions WHERE note_id=?',[note_id],order='revision DESC')
    return render_template('note.html',item=note,workspace=workspace,history=history,submitted=submitted,error=error,
                           safe_body=r.render_note(note['body']),render_note=r.render_note,tags=r.tag_rows('note',note_id),
                           tag_options=get_db().execute('SELECT * FROM tags ORDER BY name LIMIT 100').fetchall()),status


@research_ui.get('/notes/<int:note_id>')
def note(note_id):
    return note_view(note_id)


@research_ui.post('/notes/<int:note_id>')
def edit_note(note_id):
    body={name:request.form.get(name,'') for name in ('title','body','label')}
    body['expected_revision']=identifier(request.form.get('expected_revision'))
    try:
        r.update_note(note_id,body)
    except r.ResearchMissing as exc:
        abort(404,description=str(exc))
    except r.ResearchConflict as exc:
        return note_view(note_id,submitted=body,status=409,error=str(exc))
    except ValueError as exc:
        return note_view(note_id,submitted=body,status=400,error=str(exc))
    flash('メモの新しい版を保存しました。','success')
    return redirect(url_for('research.note',note_id=note_id))


@research_ui.post('/notes/<int:note_id>/archive')
def archive_note(note_id):
    if request.form.get('archived') not in ('true','false'):
        abort(400)
    with errors():
        r.update_note(note_id,{'archived':request.form['archived']=='true','expected_revision':identifier(request.form.get('expected_revision'))})
    return redirect(url_for('research.note',note_id=note_id))
