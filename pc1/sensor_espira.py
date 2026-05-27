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

# Modifica el path de Python para permitir importaciones desde la raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importaciones de configuraciones, modelos de datos y utilidades comunes del ecosistema
from common.config_loader import load_config
from common.models import EventoEspira
from common.utils import generar_intersecciones_3x3, generar_timestamp_iso, log_componente

# Configuración de tiempos del componente
COMPONENTE = "sensor_espira"
INTERVALO_SEGUNDOS = 3.0     # Frecuencia con la que el script despierta y envía datos al broker
VENTANA_CONTEO_SEG = 30      # Período de tiempo virtual que simula acumular la espira (segundos)

# Tasas estadísticas: cantidad de vehículos estimados por segundo según el estado del tráfico
TASAS = {
    "fluido":   (0.3, 1.2),  # Tráfico libre (menos autos por segundo)
    "moderado": (1.2, 2.0),  # Flujo constante
    "denso":    (2.0, 3.5),  # Embotellamiento o alta densidad vehicular
}


def _generar_evento(sensor_id: str, interseccion: str) -> EventoEspira:
    """
    Simula la detección física de la espira magnética en el asfalto.
    Calcula cuántos vehículos cruzaron por el sensor en la última ventana temporal.
    """
    # NOTA: La variable 'tasa_nombre' y la primera asignación de pesos no se usan directamente abajo, 
    # pero preparan el ecosistema probabilístico de forma idéntica a los otros sensores.
    tasa_nombre, pesos = random.choices(
        [("fluido", None), ("moderado", None), ("denso", None)],
        weights=[0.55, 0.30, 0.15], # Probabilidad: 55% fluido, 30% moderado, 15% denso
        k=1,
    )[0], [0.55, 0.30, 0.15]

    # Elige el nivel de tráfico actual basándose en las probabilidades (pesos)
    nivel = random.choices(list(TASAS.keys()), weights=pesos, k=1)[0]
    
    # Extrae una tasa aleatoria continua (float) dentro del rango del nivel seleccionado
    tasa = random.uniform(*TASAS[nivel])
    
    # MATEMÁTICA: Multiplica la tasa (vehículos/seg) por el tiempo de la ventana (30s) y lo redondea a entero.
    # El max(1, ...) asegura que al menos se registre 1 vehículo y el sensor no envíe reportes vacíos.
    vehiculos = max(1, int(round(tasa * VENTANA_CONTEO_SEG)))

    # Captura las marcas de tiempo. Simula el inicio y el fin del ciclo de sensado de forma secuencial.
    ts_inicio = generar_timestamp_iso()
    time.sleep(0.01)  # Breve retraso artificial para asegurar que ts_inicio != ts_fin
    ts_fin = generar_timestamp_iso()

    # Instancia el modelo de datos tipado con los valores simulados
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
    host_pc1 = config["pc1"]["host"]                 # IP de la máquina donde corre el broker (PC1)
    puerto = config["ports"]["sensor_to_broker"]     # Puerto PULL del Broker

    # Obtiene el mapeo de calles de la red vial (I1 a I9)
    intersecciones = generar_intersecciones_3x3()

    # 2. CONFIGURACIÓN DEL SOCKET ZERO MQ
    ctx = zmq.Context()
    socket = ctx.socket(zmq.PUSH) # Inicializa socket de empuje (PUSH)
    endpoint = f"tcp://{host_pc1}:{puerto}"
    socket.connect(endpoint) # Establece conexión hacia el pipeline del broker

    # Pausa de cortesía obligatoria para evitar la pérdida inicial de mensajes en ZMQ
    time.sleep(0.5)

    log_componente(COMPONENTE, f"PUSH conectado a {endpoint} | ventana={VENTANA_CONTEO_SEG}s")

    # 3. BUCLE INFINITO DE TRANSMISIÓN
    try:
        while True:
            # Recorre todas las intersecciones del mapa urbano
            for interseccion in intersecciones:
                # Genera el identificador único string para la espira (ej: "espira_i1")
                sensor_id = f"espira_{interseccion.lower()}"
                
                # Ejecuta la lógica para generar las métricas de vehículos acumulados
                evento = _generar_evento(sensor_id, interseccion)
                
                # Serializa a JSON y envía el string a través del socket de red
                socket.send_string(evento.to_json())
                
                # Calcula la tasa exacta real registrada (para fines informativos en el log)
                tasa_real = round(evento.vehiculos_contados / evento.intervalo_segundos, 2)
                log_componente(
                    COMPONENTE,
                    f"{interseccion} | veh={evento.vehiculos_contados} en {evento.intervalo_segundos}s"
                    f" | tasa={tasa_real} veh/s",
                )
            
            # Suspende el hilo por 3 segundos antes de iniciar la siguiente ronda de telemetría
            time.sleep(INTERVALO_SEGUNDOS)
            
    # 4. CONTROL DE CIERRE LIMPIO
    except KeyboardInterrupt:
        # Captura Ctrl+C para interrumpir el script de forma segura desde la terminal
        log_componente(COMPONENTE, "Detenido manualmente.", nivel="WARN")
    finally:
        # Cierra el socket y destruye el contexto de ZeroMQ para liberar buffers del S.O.
        socket.close(linger=0)
        ctx.term()


if __name__ == "__main__":
    main()
