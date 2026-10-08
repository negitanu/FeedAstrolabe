"""Authenticated, bounded research API. Shares the reader's bearer-key policy."""
from contextlib import contextmanager
from flask import Blueprint, abort, request, url_for
from .keys import authenticate_api
from .db import get_db
from .api import integer_arg, list_articles, feed_record
from . import research as r

research_api = Blueprint('research_api', __name__, url_prefix='/api/v1')
research_api.before_request(authenticate_api)


@contextmanager
def errors():
    try:
        yield
    except r.ResearchMissing as exc:
        abort(404, description=str(exc))
    except r.ResearchConflict as exc:
        abort(409, description=str(exc))
    except ValueError as exc:
        abort(400, description=str(exc))


def archived_clause(clauses, params, default=False):
    value = request.args.get('archived', str(default).lower())
    if value not in ('true','false'):
        abort(400, description='archived must be true or false')
    clauses.append('archived=?')
    params.append(int(value=='true'))


def page(sql, params=(), column='id', transform=r.record):
    limit = integer_arg('limit',30,maximum=100)
    before = integer_arg('before_id',None) if 'before_id' in request.args else None
    after = integer_arg('after_id',None,minimum=0) if 'after_id' in request.args else None
    if before is not None and after is not None:
        abort(400,description='Use either before_id or after_id')
    params = list(params)
    if before is not None or after is not None:
        sql += (' AND ' if ' WHERE ' in sql else ' WHERE ') + column + ('<?' if before is not None else '>?')
        params.append(before if before is not None else after)
    rows = get_db().execute(sql + f' ORDER BY {column} {"ASC" if after is not None else "DESC"} LIMIT ?', params+[limit+1]).fetchall()
    more = len(rows)>limit
    rows = rows[:limit]
    return {'data':[transform(row) for row in rows], 'has_more':more,
            'next_before_id':rows[-1][column.split('.')[-1]] if rows and after is None and more else None,
            'next_after_id':rows[-1][column.split('.')[-1]] if rows and after is not None else after}


def tagged_record(kind, row):
    result = r.record(row)
    result['tags'] = [dict(tag) for tag in r.tag_rows(kind,row['id'])]
    return result


def tag_filter(kind, clauses, params):
    if 'tag' in request.args:
        identifier = integer_arg('tag',None)
        with errors():
            r.find('tag',identifier)
        table = {'workspace':'workspace_tags','note':'note_tags'}[kind]
        clauses.append(f'EXISTS(SELECT 1 FROM {table} t WHERE t.{kind}_id={r.KINDS[kind]}.id AND t.tag_id=?)')
        params.append(identifier)


@research_api.get('/workspaces')
def workspaces():
    clauses,params = [],[]
    archived_clause(clauses,params)
    tag_filter('workspace',clauses,params)
    return page('SELECT * FROM workspaces WHERE '+' AND '.join(clauses),params,transform=lambda row:tagged_record('workspace',row))


@research_api.post('/workspaces')
def create_workspace():
    with errors():
        identifier = r.create_workspace(request.get_json())
    return workspace(identifier),201,{'Location':url_for('research_api.workspace',identifier=identifier)}


@research_api.get('/workspaces/<int:identifier>')
def workspace(identifier):
    with errors():
        result = tagged_record('workspace',r.find('workspace',identifier))
    return {'data':result}


@research_api.patch('/workspaces/<int:identifier>')
def update_workspace(identifier):
    with errors():
        r.update_workspace(identifier,request.get_json())
    return workspace(identifier)


@research_api.get('/workspaces/<int:identifier>/articles')
def workspace_articles(identifier):
    return list_articles(workspace_id=identifier)


@research_api.get('/workspaces/<int:identifier>/feeds')
def workspace_feeds(identifier):
    with errors():
        r.find('workspace',identifier)
    return page('SELECT f.* FROM feeds f JOIN workspace_feeds wf ON wf.feed_id=f.id WHERE wf.workspace_id=?',[identifier],column='f.id',transform=feed_record)


@research_api.get('/workspaces/<int:identifier>/notes')
def notes(identifier):
    with errors():
        r.find('workspace',identifier)
    clauses,params = ['workspace_id=?'],[identifier]
    archived_clause(clauses,params)
    tag_filter('note',clauses,params)
    return page('SELECT * FROM notes WHERE '+' AND '.join(clauses),params,transform=lambda row:tagged_record('note',row))


@research_api.post('/workspaces/<int:identifier>/notes')
def create_note(identifier):
    with errors():
        note_id=r.create_note(identifier,request.get_json())
    return note(note_id),201,{'Location':url_for('research_api.note',identifier=note_id)}


@research_api.get('/notes/<int:identifier>')
def note(identifier):
    with errors():
        result=tagged_record('note',r.find('note',identifier))
    return {'data':result}


@research_api.patch('/notes/<int:identifier>')
def update_note(identifier):
    with errors():
        r.update_note(identifier,request.get_json())
    return note(identifier)


@research_api.get('/notes/<int:identifier>/revisions')
def revisions(identifier):
    with errors():
        r.find('note',identifier)
    return page('SELECT * FROM note_revisions WHERE note_id=?',[identifier],column='revision')


@research_api.get('/tags')
def tags():
    return page('SELECT * FROM tags')


@research_api.post('/tags')
def create_tag():
    with errors():
        identifier=r.save_tag(request.get_json())
    return tag(identifier),201,{'Location':url_for('research_api.tag',identifier=identifier)}


@research_api.get('/tags/<int:identifier>')
def tag(identifier):
    with errors():
        result=dict(r.find('tag',identifier))
    return {'data':result}


@research_api.patch('/tags/<int:identifier>')
def update_tag(identifier):
    with errors():
        r.save_tag(request.get_json(),identifier)
    return tag(identifier)


def association(kind,target,identifier,target_id):
    if request.get_data():
        abort(400,description='Association requests must have an empty body')
    with errors():
        r.associate(kind,identifier,target,target_id,remove=request.method=='DELETE')
    return '',204


# Fixed route/SQL vocabulary, never accept client-provided table names.
for kind,target in [('workspace','feed'),('workspace','article'),('workspace','tag'),('article','tag'),('note','tag')]:
    def handler(identifier,target_id,kind=kind,target=target):
        return association(kind,target,identifier,target_id)
    research_api.add_url_rule(f'/{kind}s/<int:identifier>/{target}s/<int:target_id>',endpoint=f'{kind}_{target}_link',view_func=handler,methods=['POST','DELETE'])
