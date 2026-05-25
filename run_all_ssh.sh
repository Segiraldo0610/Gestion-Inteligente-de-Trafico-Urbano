#!/bin/bash

CONFIG="config.json"

PC1_IP=$(python3 -c "import json; print(json.load(open('$CONFIG'))['pc1']['host'])")
PC2_IP=$(python3 -c "import json; print(json.load(open('$CONFIG'))['pc2']['host'])")
PC3_IP=$(python3 -c "import json; print(json.load(open('$CONFIG'))['pc3']['host'])")

USER="estudiate"
PROJECT_PATH="~/trafico_urbano"

echo "🚦 Iniciando sistema distribuido..."

# =====================================================
# PC3 - BASE DE DATOS + MONITOREO (PRIMERO)
# =====================================================
echo "🟢 Iniciando PC3 ($PC3_IP)"

ssh $USER@$PC3_IP "cd $PROJECT_PATH/pc3 && nohup python3 monitoreo.py > monitoreo.log 2>&1 &"

sleep 2

# =====================================================
# PC2 - ANALÍTICA + CONTROL + BD RÉPLICA + HEALTHCHECK
# =====================================================
echo "🟡 Iniciando PC2 ($PC2_IP)"

ssh $USER@$PC2_IP "cd $PROJECT_PATH/pc2 && nohup python3 analitica.py > analitica.log 2>&1 &"
ssh $USER@$PC2_IP "cd $PROJECT_PATH/pc2 && nohup python3 control_semaforos.py > semaforos.log 2>&1 &"
ssh $USER@$PC2_IP "cd $PROJECT_PATH/pc2 && nohup python3 bd_replica.py > replica.log 2>&1 &"
ssh $USER@$PC2_IP "cd $PROJECT_PATH/pc2 && nohup python3 healthcheck.py > health.log 2>&1 &"

sleep 2

# =====================================================
# PC1 - SENSORES + BROKER
# =====================================================
echo "🔵 Iniciando PC1 ($PC1_IP)"

ssh $USER@$PC1_IP "cd $PROJECT_PATH/pc1 && nohup python3 broker.py > broker.log 2>&1 &"

echo "✅ SISTEMA COMPLETAMENTE INICIADO"
