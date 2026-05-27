#!/bin/bash
# PC2 — Analítica, Control de Semáforos, BD Réplica, Health Check
# Ejecutar en: estudiante@10.43.99.140

set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"

echo "============================================"
echo "  PC2 — Analítica y Control"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

if [ ! -d ".venv" ]; then
    echo "[INFO] Creando entorno virtual..."
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install pyzmq --quiet

echo "[INFO] Levantando BD réplica..."
python3 -m pc2.bd_replica &
sleep 0.5

echo "[INFO] Levantando control de semáforos..."
python3 -m pc2.control_semaforos &
sleep 0.5

echo "[INFO] Levantando health check..."
python3 -m pc2.health_check &
sleep 1

echo "[INFO] Levantando analítica (con failover)..."
python3 -m pc2.analitica &

echo ""
echo "[OK] PC2 en marcha. PIDs activos:"
jobs -l
echo ""
echo "Presiona Ctrl+C para detener todo."

trap 'echo ""; echo "[INFO] Deteniendo PC2..."; kill $(jobs -p) 2>/dev/null; exit 0' SIGINT SIGTERM
wait
