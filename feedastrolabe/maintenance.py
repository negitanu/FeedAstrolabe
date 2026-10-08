"""Offline restore and consistent online SQLite backup. No credentials printed."""
import argparse
import fcntl
import os
import shutil
import sys
import tempfile
from pathlib import Path
from .db import connect, init_database


def backup(source, destination):
    from .evidence import storage_lock
    with storage_lock(Path(source).parent):
        return _backup(source, destination)


def _backup(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise ValueError('Source database does not exist')
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    src, dst = connect(str(source)), connect(str(destination))
    success=False
    try:
        if src.execute('PRAGMA user_version').fetchone()[0] >= 6 and src.execute('SELECT count(*) FROM evidence_blobs').fetchone()[0]:
            raise ValueError('Evidence-bearing databases require backup-bundle/restore-bundle.')
        src.backup(dst)
        success=True
    finally:
        src.close()
        dst.close()
        if not success:
            destination.unlink(missing_ok=True)


def restore(source, destination):
    from .evidence import storage_lock
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    with storage_lock(Path(destination).parent):
        return _restore(source, destination)


def _restore(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_file() or source.resolve() == destination.resolve():
        raise ValueError('Invalid restore source')
    destination.parent.mkdir(parents=True, exist_ok=True)
    src = connect(str(source))
    try:
        if src.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or src.execute('PRAGMA user_version').fetchone()[0] not in (1, 2, 3, 4, 5, 6):
            raise ValueError('Invalid backup schema')
        if src.execute('PRAGMA user_version').fetchone()[0] >= 6 and src.execute('SELECT count(*) FROM evidence_blobs').fetchone()[0]:
            raise ValueError('Evidence-bearing databases require restore-bundle.')
        if destination.exists():
            with connect(destination) as existing:
                if existing.execute('PRAGMA user_version').fetchone()[0]>=6 and existing.execute('SELECT count(*) FROM evidence_blobs').fetchone()[0]:
                    raise ValueError('Live evidence databases require restore-bundle.')
        with (destination.parent / 'init.lock').open('a') as init_lock, (destination.parent / 'refresh.lock').open('a') as refresh, (destination.parent / 'observer.lock').open('a') as observer:
            fcntl.flock(init_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(refresh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(observer, fcntl.LOCK_EX | fcntl.LOCK_NB)
            dst = connect(str(destination))
            try:
                src.backup(dst)
            finally:
                dst.close()
            init_database(str(destination))
    finally:
        src.close()


def main():
    parser = argparse.ArgumentParser(description='SQLite backup/restore. Stop Web, worker and observer before restore.')
    parser.add_argument('action', choices=['backup', 'restore','backup-bundle','restore-bundle'])
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    data = Path(os.environ.get('FEEDASTROLABE_DATA_DIR', Path(__file__).resolve().parent.parent / 'instance'))
    database = data / 'feeds.sqlite3'
    if args.action in ('backup-bundle','restore-bundle'):
        from .evidence_backup import backup_bundle,restore_bundle
        if args.action=='backup-bundle':
            backup_bundle(database,args.file)
        else:
            restore_bundle(args.file,database)
    elif args.action == 'backup':
        backup(database, args.file)
    else:
        if str(args.file) == '-':
            data.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=data, prefix='.restore-', suffix='.sqlite3', delete=False) as handle:
                temporary = Path(handle.name)
                try:
                    shutil.copyfileobj(sys.stdin.buffer, handle)
                    handle.flush()
                    restore(temporary, database)
                finally:
                    temporary.unlink(missing_ok=True)
        else:
            restore(args.file, database)
    print(args.action + ' completed')


if __name__ == '__main__':
    main()
