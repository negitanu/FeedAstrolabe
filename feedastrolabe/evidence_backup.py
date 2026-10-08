"""Verified private directory bundles. Call restore only with all services stopped."""
from contextlib import ExitStack,closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

from .db import connect,init_database,SCHEMA_VERSION
from . import evidence as e


def file_hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('バックアップに欠損またはリンクがあります。')
    return path


def references(db):
    if db.execute('PRAGMA quick_check').fetchone()[0]!='ok' or db.execute('PRAGMA user_version').fetchone()[0] not in range(6,SCHEMA_VERSION+1) or db.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('バックアップの DB 整合性が不正です。')
    for row in db.execute('SELECT text,text_hash FROM evidence'):
        if e.digest(row['text'].encode())!=row['text_hash']:
            raise ValueError('根拠テキストのハッシュが一致しません。')
    for row in db.execute('SELECT q.*,e.text,e.text_hash AS actual_hash FROM quotations q JOIN evidence e ON e.id=q.evidence_id'):
        if row['text_hash']!=row['actual_hash'] or row['text'][row['start']:row['end']]!=row['quote']:
            raise ValueError('引用の整合性が不正です。')
    return [{'hash':row['hash'],'size':row['size']} for row in db.execute('SELECT * FROM evidence_blobs ORDER BY hash')]


def backup_bundle(source,destination):
    source=Path(source);destination=Path(destination)
    if destination.exists() or destination.is_symlink() or destination.resolve()==source.parent.resolve():
        raise ValueError('未使用のバックアップ先を指定してください。')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with e.storage_lock(source.parent),tempfile.TemporaryDirectory(prefix='.bundle-',dir=destination.parent) as temporary:
        stage=Path(temporary);dbpath=stage/'feeds.sqlite3'
        with closing(connect(source)) as src,closing(connect(dbpath)) as dst:
            src.backup(dst)
            items=references(dst)
        with closing(connect(dbpath)) as snapshot:
            schema=snapshot.execute('PRAGMA user_version').fetchone()[0]
        dbpath.chmod(0o600)
        blobs=stage/'evidence-blobs';blobs.mkdir(mode=0o700)
        for item in items:
            data=e.read_blob(item['hash'],item['size'],source.parent)
            path=blobs/item['hash'];path.write_bytes(data);path.chmod(0o600)
        manifest={'version':1,'schema':schema,'database_hash':file_hash(dbpath),'blobs':items}
        (stage/'manifest.json').write_text(json.dumps(manifest,sort_keys=True)+'\n');(stage/'manifest.json').chmod(0o600)
        # Publish only after every referenced blob is verified.
        os.rename(stage,destination)


def validate_bundle(source):
    source=Path(source)
    if source.is_symlink() or not source.is_dir() or {p.name for p in source.iterdir()}!={'feeds.sqlite3','manifest.json','evidence-blobs'}:
        raise ValueError('バックアップ構成が不正です。')
    with regular(source/'manifest.json').open('rb') as handle:
        raw=handle.read(16*1024*1024+1)
    if len(raw)>16*1024*1024:
        raise ValueError('バックアップマニフェストが大きすぎます。')
    try:manifest=json.loads(raw)
    except Exception:raise ValueError('バックアップマニフェストが不正です。') from None
    if not isinstance(manifest,dict) or set(manifest)!={'version','schema','database_hash','blobs'} or manifest['version']!=1 or manifest['schema'] not in range(6,SCHEMA_VERSION+1) or not isinstance(manifest['blobs'],list):
        raise ValueError('未対応のバックアップ形式です。')
    database=regular(source/'feeds.sqlite3')
    if file_hash(database)!=manifest['database_hash']:
        raise ValueError('バックアップ DB のハッシュが一致しません。')
    with closing(connect(database)) as db:
        items=references(db)
        if db.execute('PRAGMA user_version').fetchone()[0]!=manifest['schema']:
            raise ValueError('バックアップ schema が一致しません。')
    if items!=manifest['blobs']:
        raise ValueError('バックアップの参照一覧が一致しません。')
    blobs=source/'evidence-blobs'
    if blobs.is_symlink() or not blobs.is_dir() or {p.name for p in blobs.iterdir()}!={item['hash'] for item in items}:
        raise ValueError('バックアップのファイル一覧が一致しません。')
    for item in items:e.read_blob(item['hash'],item['size'],source)
    return items


def restore_bundle(source,destination):
    source=Path(source);destination=Path(destination)
    if destination.is_symlink() or source.resolve()==destination.parent.resolve():
        raise ValueError('復元先が不正です。')
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.parent.chmod(0o700)
    with e.storage_lock(destination.parent),ExitStack() as locks:
        for name in ['init.lock','refresh.lock','observer.lock']:
            handle=locks.enter_context((destination.parent/name).open('a'))
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Copy validated bundle into private staging, then validate the copy against source races.
        validate_bundle(source)
        with tempfile.TemporaryDirectory(prefix='.restore-bundle-',dir=destination.parent) as temporary:
            stage=Path(temporary)/'bundle';shutil.copytree(source,stage,symlinks=True)
            validate_bundle(stage)
            staged_db=stage/'feeds.sqlite3';init_database(staged_db)
            staged_db.chmod(0o600)
            (stage/'evidence-blobs').chmod(0o700)
            for blob in (stage/'evidence-blobs').iterdir():blob.chmod(0o600)
            for suffix in ['-wal','-shm']:
                if Path(str(destination)+suffix).exists():
                    raise ValueError('稼働中または WAL 未処理の DB には復元できません。サービスを停止し checkpoint してください。')
            live_blobs=destination.parent/'evidence-blobs'
            if live_blobs.is_symlink():raise ValueError('復元先がリンクです。')
            old_blobs=Path(temporary)/'old-blobs';old_db=Path(temporary)/'old.sqlite3'
            had_db=destination.exists();had_blobs=live_blobs.exists()
            try:
                if had_db:os.rename(destination,old_db)
                if had_blobs:os.rename(live_blobs,old_blobs)
                os.rename(stage/'evidence-blobs',live_blobs)
                os.rename(staged_db,destination)
            except BaseException:
                if live_blobs.exists() and (not had_blobs or old_blobs.exists()):shutil.rmtree(live_blobs)
                if old_blobs.exists():os.rename(old_blobs,live_blobs)
                if old_db.exists():os.replace(old_db,destination)
                raise
