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
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise ValueError('Source database does not exist')
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    src, dst = connect(str(source)), connect(str(destination))
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def restore(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_file() or source.resolve() == destination.resolve():
        raise ValueError('Invalid restore source')
    destination.parent.mkdir(parents=True, exist_ok=True)
    src = connect(str(source))
    try:
        if src.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or src.execute('PRAGMA user_version').fetchone()[0] not in (1, 2):
            raise ValueError('Invalid backup schema')
        with (destination.parent / 'init.lock').open('a') as init_lock, (destination.parent / 'refresh.lock').open('a') as refresh:
            fcntl.flock(init_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(refresh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            dst = connect(str(destination))
            try:
                src.backup(dst)
            finally:
                dst.close()
            init_database(str(destination))
    finally:
        src.close()


def main():
    parser = argparse.ArgumentParser(description='SQLite backup/restore. Stop Web and worker before restore.')
    parser.add_argument('action', choices=['backup', 'restore'])
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    data = Path(os.environ.get('FEEDASTROLABE_DATA_DIR', Path(__file__).resolve().parent.parent / 'instance'))
    database = data / 'feeds.sqlite3'
    if args.action == 'backup':
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
