#!/usr/bin/env python3
"""
Sensor de cámara (PC1).
Simula una cámara de tráfico en cada intersección.
Mide volumen de vehículos y velocidad promedio.
Publica eventos via ZMQ PUSH hacia el broker.
"""

import json
import os
import random
import sys
import time

import zmq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config_loader import load_config
from common.models import EventoCamara
from common.utils import generar_intersecciones_3x3, generar_timestamp_iso, log_componente

COMPONENTE = "sensor_camara"
INTERVALO_SEGUNDOS = 2.0

# Parámetros de simulación por estado de tráfico
PERFILES = {
    "normal":     {"volumen": (5, 20),  "velocidad": (35.0, 60.0)},
    "congestion": {"volumen": (25, 55), "velocidad": (8.0, 25.0)},
    "pico":       {"volumen": (20, 35), "velocidad": (18.0, 35.0)},
}


def _generar_evento(sensor_id: str, interseccion: str) -> EventoCamara:
    """Genera un evento con datos simulados realistas."""
    perfil = random.choices(
        list(PERFILES.values()),
        weights=[0.60, 0.25, 0.15],
        k=1,
    )[0]
    volumen = random.randint(*perfil["volumen"])
    velocidad = round(random.uniform(*perfil["velocidad"]), 1)
    return EventoCamara(
        sensor_id=sensor_id,
        interseccion=interseccion,
        volumen=volumen,
        velocidad_promedio=velocidad,
        timestamp=generar_timestamp_iso(),
    )


def main():
    config = load_config()
    host_pc1 = config["pc1"]["host"]
    puerto = config["ports"]["sensor_to_broker"]

    intersecciones = generar_intersecciones_3x3()

    ctx = zmq.Context()
    socket = ctx.socket(zmq.PUB)
    endpoint = f"tcp://{host_pc1}:{puerto}"
    socket.connect(endpoint)

    # Pequeña pausa para que el broker levante primero
    time.sleep(0.5)

    log_componente(COMPONENTE, f"PUSH conectado a {endpoint} | {len(intersecciones)} intersecciones")

    try:
        while True:
            for interseccion in intersecciones:
                sensor_id = f"cam_{interseccion.lower()}"
                evento = _generar_evento(sensor_id, interseccion)
                socket.send_multipart([b"camara", evento.to_json().encode("utf-8")])
                log_componente(
                    COMPONENTE,
                    f"{interseccion} | vol={evento.volumen} veh | vel={evento.velocidad_promedio} km/h",
                )
            time.sleep(INTERVALO_SEGUNDOS)
    except KeyboardInterrupt:
        log_componente(COMPONENTE, "Detenido manualmente.", nivel="WARN")
    finally:
        socket.close(linger=0)
        ctx.term()


if __name__ == "__main__":
    main()

