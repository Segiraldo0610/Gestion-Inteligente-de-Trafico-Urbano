#!/usr/bin/env python3
"""
Réplica de base de datos (PC2).
Recibe por PULL los registros enviados por analítica (PUSH) en analitica_to_db_replica.
"""

import json
import os
import sys

import zmq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config_loader import load_config
from common.db import guardar_accion, guardar_evento, inicializar_db
from common.utils import log_componente

COMPONENTE = "bd_replica"


def main():
    config = load_config()
    host_pc2 = config["pc2"]["host"]
    puerto = config["ports"]["analitica_to_db_replica"]

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "trafico_replica.db")
    inicializar_db(db_path)
    log_componente(COMPONENTE, f"SQLite listo en {db_path}")

    ctx = zmq.Context()
    socket = ctx.socket(zmq.PULL)
    endpoint = f"tcp://{host_pc2}:{puerto}"
    socket.bind(endpoint)
    log_componente(COMPONENTE, f"PULL escuchando en {endpoint} (analítica -> réplica)")

    try:
        while True:
            raw = socket.recv_string()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                log_componente(COMPONENTE, f"JSON inválido: {raw!r}", nivel="ERROR")
                continue

            if not isinstance(data, dict):
                log_componente(COMPONENTE, f"Mensaje no es objeto: {data!r}", nivel="WARN")
                continue

            req = ["tipo_evento", "interseccion", "evento_original", "timestamp_proceso"]
            if not all(k in data for k in req):
                log_componente(COMPONENTE, f"Mensaje incompleto: {data!r}", nivel="WARN")
                continue

            tipo_evento = str(data["tipo_evento"])
            interseccion = str(data["interseccion"])
            ts = str(data["timestamp_proceso"])
            evento_orig = data["evento_original"]
            if not isinstance(evento_orig, dict):
                log_componente(COMPONENTE, "evento_original debe ser un objeto JSON.", nivel="WARN")
                continue

            sensor_id = str(evento_orig.get("sensor_id", "desconocido"))
            datos_json = json.dumps(data, ensure_ascii=False)

            id_ev = guardar_evento(
                db_path=db_path,
                tipo_evento=tipo_evento,
                sensor_id=sensor_id,
                interseccion=interseccion,
                datos_json=datos_json,
                timestamp=ts,
            )
            log_componente(
                COMPONENTE,
                f"Evento guardado id={id_ev} | tipo={tipo_evento} | {interseccion} | sensor={sensor_id}",
            )

            comando = data.get("comando")
            if isinstance(comando, dict):
                for k in ("interseccion", "estado", "duracion", "motivo"):
                    if k not in comando:
                        log_componente(COMPONENTE, f"Comando incompleto: {comando!r}", nivel="WARN")
                        break
                else:
                    id_ac = guardar_accion(
                        db_path=db_path,
                        interseccion=str(comando["interseccion"]),
                        estado=str(comando["estado"]),
                        duracion=int(comando["duracion"]),
                        motivo=str(comando["motivo"]),
                        timestamp=ts,
                    )
                    log_componente(
                        COMPONENTE,
                        (
                            f"Acción guardada id={id_ac} | {comando['interseccion']} -> "
                            f"{comando['estado']} ({comando['duracion']}s) | {comando['motivo']}"
                        ),
                    )
            else:
                log_componente(COMPONENTE, "Sin bloque 'comando' en el mensaje.", nivel="WARN")

    except KeyboardInterrupt:
        log_componente(COMPONENTE, "Interrumpido por teclado (Ctrl+C).", nivel="WARN")
    finally:
        socket.close(linger=0)
        ctx.term()


if __name__ == "__main__":
    main()
