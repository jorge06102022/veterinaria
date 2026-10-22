#!/usr/bin/env bash
# ==============================================================================
# PetPOS Pro - Script de Respaldo y Restauración para PostgreSQL y SQLite
# ==============================================================================

set -o errexit
set -o pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

function backup_postgres() {
    if [ -z "$DATABASE_URL" ]; then
        echo "ERROR: La variable DATABASE_URL no está definida."
        exit 1
    fi
    BACKUP_FILE="${BACKUP_DIR}/petpos_pro_pg_${TIMESTAMP}.sql.gz"
    echo "==> Generando respaldo comprimido de PostgreSQL..."
    pg_dump "$DATABASE_URL" --no-owner --no-privileges | gzip > "$BACKUP_FILE"
    echo "==> Respaldo creado exitosamente: $BACKUP_FILE"
}

function restore_postgres() {
    FILE_TO_RESTORE="$1"
    if [ -z "$FILE_TO_RESTORE" ] || [ ! -f "$FILE_TO_RESTORE" ]; then
        echo "ERROR: Debe proporcionar una ruta válida a un archivo .sql o .sql.gz"
        echo "Uso: ./backup_restore.sh restore_pg <archivo>"
        exit 1
    fi
    if [ -z "$DATABASE_URL" ]; then
        echo "ERROR: La variable DATABASE_URL no está definida."
        exit 1
    fi
    echo "ADVERTENCIA: Esta operación restaurará la base de datos en: $DATABASE_URL"
    echo "Presione ENTER para continuar o CTRL+C para cancelar..."
    read -r
    
    if [[ "$FILE_TO_RESTORE" == *.gz ]]; then
        gunzip -c "$FILE_TO_RESTORE" | psql "$DATABASE_URL"
    else
        psql "$DATABASE_URL" < "$FILE_TO_RESTORE"
    fi
    echo "==> Restauración completada exitosamente."
}

function backup_sqlite() {
    BACKUP_FILE="${BACKUP_DIR}/db_sqlite_${TIMESTAMP}.json"
    echo "==> Generando volcado JSON de datos de Django (SQLite)..."
    python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 2 > "$BACKUP_FILE"
    echo "==> Respaldo creado: $BACKUP_FILE"
}

case "$1" in
    backup_pg)
        backup_postgres
        ;;
    restore_pg)
        restore_postgres "$2"
        ;;
    backup_sqlite)
        backup_sqlite
        ;;
    *)
        echo "Uso: $0 {backup_pg|restore_pg <archivo>|backup_sqlite}"
        exit 1
        ;;
esac
