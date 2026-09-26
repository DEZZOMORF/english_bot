#!/bin/sh
set -eu
BDIR=/opt/english-bot/backups
mkdir -p "$BDIR"
OUT="englishbot-$(date +%F_%H%M).db"
docker run --rm --user 0 -v englishbot_data:/data -v "$BDIR":/backup -e OUT="$OUT" \
  english-bot:latest \
  python -c "import os,sqlite3; s=sqlite3.connect('/data/data.db'); d=sqlite3.connect('/backup/'+os.environ['OUT']); s.backup(d); d.close(); s.close()"
gzip -f "$BDIR/$OUT"
ls -1t "$BDIR"/englishbot-*.db.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
echo "$(date '+%F %T') englishbot backup OK: ${OUT}.gz ($(du -h "$BDIR/${OUT}.gz" | cut -f1))"
