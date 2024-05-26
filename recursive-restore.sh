#!/bin/bash

# Directorio que contiene los archivos de respaldo
BACKUP_DIR="."

# Host y puerto de MongoDB
HOST="localhost"
PORT="27017"

# Buscar recursivamente archivos .archive en el directorio de respaldos
find "$BACKUP_DIR" -type f -name '*.archive' | while read -r ARCHIVE; do
    echo "Restaurando desde $ARCHIVE..."
    mongorestore --archive="$ARCHIVE" --host "$HOST" --port "$PORT" --excludeCollection=depth
done

echo "Restauración completa."
