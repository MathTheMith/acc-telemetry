#!/bin/bash
# Backs up the site's SQLite database into backups/, keeping only the
# RETENTION most recent backups (older ones are deleted).
# Uses sqlite3's backup API (via python, already in the image) rather
# than a plain file copy, to never capture a write in progress.
set -euo pipefail

cd "$(dirname "$0")/.."

RETENTION=14
BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
FILE="$BACKUP_DIR/telemetry-${TIMESTAMP}.db"

mkdir -p "$BACKUP_DIR"

docker compose exec -T backend python -c "
import sqlite3
src = sqlite3.connect('/data/telemetry.db')
dst = sqlite3.connect('/tmp/backup.db')
src.backup(dst)
dst.close()
src.close()
"
docker compose cp backend:/tmp/backup.db "$FILE"

ls -1t "$BACKUP_DIR"/telemetry-*.db 2>/dev/null | tail -n "+$((RETENTION + 1))" | while read -r old; do
  rm -f "$old"
done

echo "Backup created: $FILE ($(du -h "$FILE" | cut -f1))"
