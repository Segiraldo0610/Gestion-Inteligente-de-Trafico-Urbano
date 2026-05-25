#!/bin/bash

CONFIG="config.json"

PC1_IP=$(python3 -c "import json; print(json.load(open('$CONFIG'))['pc1']['host'])")
PC2_IP=$(python3 -c "import json; print(json.load(open('$CONFIG'))['pc2']['host'])")
PC3_IP=$(python3 -c "import json; print(json.load(open('$CONFIG'))['pc3']['host'])")

USER="student"

echo "🛑 Deteniendo sistema..."

ssh $USER@$PC1_IP "pkill -f broker.py"
ssh $USER@$PC2_IP "pkill -f analitica.py"
ssh $USER@$PC2_IP "pkill -f control_semaforos.py"
ssh $USER@$PC2_IP "pkill -f bd_replica.py"
ssh $USER@$PC2_IP "pkill -f healthcheck.py"
ssh $USER@$PC3_IP "pkill -f monitoreo.py"

echo "✅ Sistema detenido"
