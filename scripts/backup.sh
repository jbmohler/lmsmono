#!/usr/bin/env bash
set -euo pipefail

BACKUP_BASE=/media/joel/cavern/backup/zdrive
DATE=$(date +%Y.%m.%d)
DEST=$BACKUP_BASE/$DATE/lms-data-suite

mkdir -p "$DEST/finances"

echo "=== LMS Backup: $DATE ==="

echo "Dumping database..."
ssh kiwistrawberry.us /home/joel/bin/dump-lmsprod.sh > "$DEST/full-lmsprod-dump.sql"

echo "Dumping tagged contacts..."
lms dump-tagged-contacts Financial > "$DEST/contacts-financial.txt"
lms dump-tagged-contacts 'Personal Tech' > "$DEST/contacts-personal-tech.txt"

echo "Dumping financial reports by year..."
lms dumpyears "$DEST/finances"

echo "Done: $DEST"
