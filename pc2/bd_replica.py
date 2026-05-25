#!/usr/bin/env python3
"""
Réplica de base de datos (PC2).
Recibe por PULL los registros enviados por analítica (PUSH) en analitica_to_db_replica.
"""

import json
import os
import sys

import zmq  # Librería de mensajería distribuida

# Añade el directorio padre al path para importar módulos compartidos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config_loader import load_config          # Carga configuración del sistema
from common.db import guardar_accion, guardar_evento, inicializar_db  # Funciones de BD
from common.utils import log_componente               # Función de logging

COMPONENTE = "bd_replica"


def main():
    # Carga configuración (hosts y puertos)
    config = load_config()
    host_pc2 = config["pc2"]["host"]
    puerto = config["ports"]["analitica_to_db_replica"]

    # Define ruta de la base de datos SQLite local (réplica)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "trafico_replica.db")

    # Inicializa la base de datos (crea tablas si no existen)
    inicializar_db(db_path)
    log_componente(COMPONENTE, f"SQLite listo en {db_path}")

    # Configuración del socket PULL (recibe datos desde analítica)
    ctx = zmq.Context()
    socket = ctx.socket(zmq.PULL)
    endpoint = f"tcp://{host_pc2}:{puerto}"
    socket.bind(endpoint)  # Se queda escuchando en este endpoint
    log_componente(COMPONENTE, f"PULL escuchando en {endpoint} (analítica -> réplica)")

    try:
        while True:
            # Recibe mensaje como string
            raw = socket.recv_string()
            try:
                data = json.loads(raw)  # Intenta parsear JSON
            except json.JSONDecodeError:
                log_componente(COMPONENTE, f"JSON inválido: {raw!r}", nivel="ERROR")
                continue

            # Verifica que el mensaje sea un diccionario
            if not isinstance(data, dict):
                log_componente(COMPONENTE, f"Mensaje no es objeto: {data!r}", nivel="WARN")
                continue

            # Campos requeridos mínimos para procesar el evento
            req = ["tipo_evento", "interseccion", "evento_original", "timestamp_proceso"]
            if not all(k in data for k in req):
                log_componente(COMPONENTE, f"Mensaje incompleto: {data!r}", nivel="WARN")
                continue

            # Extracción de datos principales
            tipo_evento = str(data["tipo_evento"])
            interseccion = str(data["interseccion"])
            ts = str(data["timestamp_proceso"])
            evento_orig = data["evento_original"]

            # Validación del evento original
            if not isinstance(evento_orig, dict):
                log_componente(COMPONENTE, "evento_original debe ser un objeto JSON.", nivel="WARN")
                continue

            # Obtiene sensor_id (si no existe, usa "desconocido")
            sensor_id = str(evento_orig.get("sensor_id", "desconocido"))

            # Serializa todo el mensaje para almacenarlo
            datos_json = json.dumps(data, ensure_ascii=False)

            # Guarda el evento en la base de datos
            id_ev = guardar_evento(
                db_path=db_path,
                tipo_evento=tipo_evento,
                sensor_id=sensor_id,
                interseccion=interseccion,
                datos_json=datos_json,
                timestamp=ts,
            )

            # Log del evento guardado
            log_componente(
                COMPONENTE,
                f"Evento guardado id={id_ev} | tipo={tipo_evento} | {interseccion} | sensor={sensor_id}",
            )

            # Procesa el bloque de comando asociado (si existe)
            comando = data.get("comando")
            if isinstance(comando, dict):
                # Verifica campos requeridos del comando
                for k in ("interseccion", "estado", "duracion", "motivo"):
                    if k not in comando:
                        log_componente(COMPONENTE, f"Comando incompleto: {comando!r}", nivel="WARN")
                        break
                else:
                    # Guarda la acción en la base de datos
                    id_ac = guardar_accion(
                        db_path=db_path,
                        interseccion=str(comando["interseccion"]),
                        estado=str(comando["estado"]),
                        duracion=int(comando["duracion"]),
                        motivo=str(comando["motivo"]),
                        timestamp=ts,
                    )

                    # Log de la acción guardada
                    log_componente(
                        COMPONENTE,
                        (
                            f"Acción guardada id={id_ac} | {comando['interseccion']} -> "
                            f"{comando['estado']} ({comando['duracion']}s) | {comando['motivo']}"
                        ),
                    )
            else:
                # Si no hay comando, se registra advertencia
                log_componente(COMPONENTE, "Sin bloque 'comando' en el mensaje.", nivel="WARN")

    except KeyboardInterrupt:
        # Manejo de interrupción manual
        log_componente(COMPONENTE, "Interrumpido por teclado (Ctrl+C).", nivel="WARN")
    finally:
        # Cierre limpio de recursos
        socket.close(linger=0)
        ctx.term()


# Punto de entrada del script
if __name__ == "__main__":
    main()
