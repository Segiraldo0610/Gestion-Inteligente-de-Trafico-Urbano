#!/bin/bash
# PC1 — Sensores y Broker
# Ejecutar en: estudiante@10.43.99.126
# Orden: broker primero (bind), luego sensores (connect)

set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"

echo "============================================"
echo "  PC1 — Sensores y Broker"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

# Crear venv si no existe
if [ ! -d ".venv" ]; then
    echo "[INFO] Creando entorno virtual..."
    python3 -m venv .venv
fi
source .venv/bin/activate

# Instalar dependencias si faltan
pip install pyzmq --quiet

echo "[INFO] Levantando broker..."
python3 -m pc1.broker &
PID_BROKER=$!

sleep 1   # Dar tiempo al broker para hacer bind

echo "[INFO] Levantando sensores..."
python3 -m pc1.sensor_camara &
python3 -m pc1.sensor_espira &
python3 -m pc1.sensor_gps &

echo ""
echo "[OK] PC1 en marcha. PIDs activos:"
jobs -l
echo ""
echo "Presiona Ctrl+C para detener todo."

# Esperar y limpiar al salir
trap 'echo ""; echo "[INFO] Deteniendo PC1..."; kill $(jobs -p) 2>/dev/null; exit 0' SIGINT SIGTERM
wait
