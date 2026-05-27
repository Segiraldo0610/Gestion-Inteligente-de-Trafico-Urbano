#!/bin/bash
# Elimina las bases de datos SQLite para empezar desde cero.
# Ejecutar antes de una demo limpia.

cd "$(dirname "$0")/.."

echo "[INFO] Limpiando bases de datos..."

find . -name "*.db" -not -path "./.git/*" | while read f; do
    rm -f "$f"
    echo "  Eliminado: $f"
done

echo "[OK] Bases de datos eliminadas. El sistema las recreará al arrancar."
