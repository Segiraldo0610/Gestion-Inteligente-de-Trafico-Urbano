#!/usr/bin/env python3
"""
Sensor de espira inductiva (PC1).
Simula una espira embebida en el pavimento que cuenta vehículos
que cruzan un tramo durante un intervalo fijo.
Publica eventos via ZMQ PUSH hacia el broker.
"""

import os
import random
import sys
import time

import zmq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config_loader import load_config
from common.models import EventoEspira
from common.utils import generar_intersecciones_3x3, generar_timestamp_iso, log_componente

COMPONENTE = "sensor_espira"
INTERVALO_SEGUNDOS = 3.0     # Cada cuánto publica
VENTANA_CONTEO_SEG = 30      # Ventana de tiempo que simula la espira

# Tasa de vehículos por segundo según nivel de tráfico
TASAS = {
    "fluido":   (0.3, 1.2),
    "moderado": (1.2, 2.0),
    "denso":    (2.0, 3.5),
}


def _generar_evento(sensor_id: str, interseccion: str) -> EventoEspira:
    tasa_nombre, pesos = random.choices(
        [("fluido", None), ("moderado", None), ("denso", None)],
        weights=[0.55, 0.30, 0.15],
        k=1,
    )[0], [0.55, 0.30, 0.15]

    nivel = random.choices(list(TASAS.keys()), weights=pesos, k=1)[0]
    tasa = random.uniform(*TASAS[nivel])
    vehiculos = max(1, int(round(tasa * VENTANA_CONTEO_SEG)))

    ts_inicio = generar_timestamp_iso()
    time.sleep(0.01)  # Pequeño delta para que los timestamps difieran
    ts_fin = generar_timestamp_iso()

    return EventoEspira(
        sensor_id=sensor_id,
        interseccion=interseccion,
        vehiculos_contados=vehiculos,
        intervalo_segundos=VENTANA_CONTEO_SEG,
        timestamp_inicio=ts_inicio,
        timestamp_fin=ts_fin,
    )


def main():
    config = load_config()
    host_pc1 = config["pc1"]["host"]
    puerto = config["ports"]["sensor_to_broker"]

    intersecciones = generar_intersecciones_3x3()

    ctx = zmq.Context()
    socket = ctx.socket(zmq.PUSH)
    endpoint = f"tcp://{host_pc1}:{puerto}"
    socket.connect(endpoint)

    time.sleep(0.5)

    log_componente(COMPONENTE, f"PUSH conectado a {endpoint} | ventana={VENTANA_CONTEO_SEG}s")

    try:
        while True:
            for interseccion in intersecciones:
                sensor_id = f"espira_{interseccion.lower()}"
                evento = _generar_evento(sensor_id, interseccion)
                socket.send_string(evento.to_json())
                tasa_real = round(evento.vehiculos_contados / evento.intervalo_segundos, 2)
                log_componente(
                    COMPONENTE,
                    f"{interseccion} | veh={evento.vehiculos_contados} en {evento.intervalo_segundos}s"
                    f" | tasa={tasa_real} veh/s",
                )
            time.sleep(INTERVALO_SEGUNDOS)
    except KeyboardInterrupt:
        log_componente(COMPONENTE, "Detenido manualmente.", nivel="WARN")
    finally:
        socket.close(linger=0)
        ctx.term()


if __name__ == "__main__":
    main()
