Aquí tienes el código completamente corregido. He limpiado la documentación, los docstrings y los mensajes de log para que reflejen **exactamente** lo que hace el script a nivel de red (`PUB/SUB`) y coincida al 100% con la **Figura 1** de tu arquitectura.

```python
#!/usr/bin/env python3
"""
Sensor de espira inductiva (PC1).
Simula una espira embebida en el pavimento que cuenta vehículos
que cruzan un tramo durante un intervalo fijo.
Publica eventos via ZMQ PUB (Tópico: "espira") hacia el broker.
"""

import os
import random
import sys
import time

import zmq

# Modifica el path de Python para poder importar módulos desde la carpeta raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config_loader import load_config
from common.models import EventoEspira
from common.utils import generar_intersecciones_3x3, generar_timestamp_iso, log_componente

COMPONENTE = "sensor_espira"
INTERVALO_SEGUNDOS = 3.0     # Frecuencia de publicación (cada cuánto despierta)
VENTANA_CONTEO_SEG = 30      # Ventana de tiempo virtual que simula la espira

# Tasa de vehículos por segundo según nivel de tráfico
TASAS = {
    "fluido":   (0.3, 1.2),
    "moderado": (1.2, 2.0),
    "denso":    (2.0, 3.5),
}


def _generar_evento(sensor_id: str, interseccion: str) -> EventoEspira:
    """
    Simula la detección física de la espira magnética en el asfalto.
    Calcula cuántos vehículos cruzaron por el sensor en la última ventana temporal.
    """
    pesos = [0.55, 0.30, 0.15] # Probabilidad: 55% fluido, 30% moderado, 15% denso

    # Elige el nivel de tráfico actual basándose en las probabilidades
    nivel = random.choices(list(TASAS.keys()), weights=pesos, k=1)[0]
    
    # Extrae una tasa aleatoria continua (float) dentro del rango del nivel seleccionado
    tasa = random.uniform(*TASAS[nivel])
    
    # Multiplica la tasa (vehículos/seg) por el tiempo de la ventana (30s) y lo redondea a entero.
    # El max(1, ...) asegura que al menos se registre 1 vehículo para evitar reportes vacíos.
    vehiculos = max(1, int(round(tasa * VENTANA_CONTEO_SEG)))

    # Captura las marcas de tiempo de inicio y fin con un pequeño retraso artificial
    ts_inicio = generar_timestamp_iso()
    time.sleep(0.01)  
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
    # 1. CARGA DE CONFIGURACIÓN Y RED
    config = load_config()
    host_pc1 = config["pc1"]["host"]
    puerto = config["ports"]["sensor_to_broker"]

    # Obtiene el mapeo de calles de la red vial (I1 a I9)
    intersecciones = generar_intersecciones_3x3()

    # 2. CONFIGURACIÓN DEL SOCKET ZERO MQ (Patrón PUB/SUB)
    ctx = zmq.Context()
    socket = ctx.socket(zmq.PUB)  # Configurado correctamente como PUB según la Figura 1
    endpoint = f"tcp://{host_pc1}:{puerto}"
    socket.connect(endpoint)

    # Pausa de cortesía obligatoria para evitar la pérdida inicial de mensajes en ZMQ
    time.sleep(0.5)

    log_componente(
        COMPONENTE, 
        f"PUB conectado a {endpoint} | Tópico='espira' | ventana={VENTANA_CONTEO_SEG}s"
    )

    # 3. BUCLE PRINCIPAL DE TRANSMISIÓN
    try:
        while True:
            for interseccion in intersecciones:
                sensor_id = f"espira_{interseccion.lower()}"
                evento = _generar_evento(sensor_id, interseccion)
                
                # Envío Multipart: [Tópico en bytes, Cuerpo del JSON en bytes]
                socket.send_multipart([b"espira", evento.to_json().encode("utf-8")])
                
                # Calcula la tasa exacta real registrada para el log informativo
                tasa_real = round(evento.vehiculos_contados / evento.intervalo_segundos, 2)
                log_componente(
                    COMPONENTE,
                    f"{interseccion} | veh={evento.vehiculos_contados} en {evento.intervalo_segundos}s"
                    f" | tasa={tasa_real} veh/s",
                )
            # Espera antes de la siguiente ronda de telemetría
            time.sleep(INTERVALO_SEGUNDOS)
            
    # 4. CONTROL DE CIERRE LIMPIO
    except KeyboardInterrupt:
        log_componente(COMPONENTE, "Detenido manualmente.", nivel="WARN")
    finally:
        # Cierra el socket y destruye el contexto para liberar buffers del sistema operativo
        socket.close(linger=0)
        ctx.term()


if __name__ == "__main__":
    main()

```
