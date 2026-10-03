"""Back up the isolated local SQLite database using SQLite's online backup API."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

root = Path(__file__).resolve().parents[1] / '.local'
source_path = root / 'development.sqlite3'
if not source_path.is_file():
    raise SystemExit('No local development database found.')
backup_dir = root / 'backups'
backup_dir.mkdir(exist_ok=True)
target_path = backup_dir / ('development-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
with sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True) as source:
    with sqlite3.connect(target_path) as target:
        source.backup(target)
        assert target.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
print('Backup verified: ' + str(target_path))
