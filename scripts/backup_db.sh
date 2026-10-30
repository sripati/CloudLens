#!/bin/bash
# Back up the CloudLens PostgreSQL database from the running Docker stack.
# Usage: ./scripts/backup_db.sh            -> backups/cloudlens_YYYYmmdd_HHMMSS.sql.gz
#        ./scripts/backup_db.sh restore FILE
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && . ./.env; set +a
DB=${POSTGRES_DB:-cloudlens}
USER=${POSTGRES_USER:-cloudlens}
mkdir -p backups

if [ "${1:-}" = "restore" ]; then
  FILE=${2:?usage: backup_db.sh restore backups/file.sql.gz}
  gunzip -c "$FILE" | docker compose exec -T db psql -U "$USER" -d "$DB"
  echo "Restored $FILE"
  exit 0
fi

OUT=backups/cloudlens_$(date +%Y%m%d_%H%M%S).sql.gz
docker compose exec -T db pg_dump -U "$USER" -d "$DB" --no-owner | gzip > "$OUT"
# keep the 14 most recent backups
ls -1t backups/cloudlens_*.sql.gz | tail -n +15 | xargs -r rm --
echo "Backup written to $OUT"
