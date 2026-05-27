#!/bin/bash
# PC3 — BD Principal, Monitoreo, Frontend Web
# Ejecutar en: estudiante@10.43.99.109

set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"

echo "============================================"
echo "  PC3 — Base de Datos y Frontend"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

if [ ! -d ".venv" ]; then
    echo "[INFO] Creando entorno virtual..."
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install pyzmq --quiet

echo "[INFO] Levantando BD principal..."
python3 -m pc3.bd_principal &
sleep 0.5

echo "[INFO] Levantando monitoreo..."
python3 -m pc3.monitoreo &
sleep 0.5

echo "[INFO] Levantando frontend web..."
python3 -m pc3.frontend &

echo ""
echo "[OK] PC3 en marcha."
echo "[OK] Dashboard disponible en: http://10.43.99.109:8080/"
echo ""
jobs -l
echo ""
echo "Presiona Ctrl+C para detener todo."

trap 'echo ""; echo "[INFO] Deteniendo PC3..."; kill $(jobs -p) 2>/dev/null; exit 0' SIGINT SIGTERM
wait
