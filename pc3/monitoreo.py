```python id="x7q2vd"
#!/usr/bin/env python3
"""
Servicio de monitoreo (PC3).
- Atiende solicitudes externas (consultar / priorizar) vía ZeroMQ (REP).
- Consulta la base de datos principal.
- Envía heartbeats periódicos a PC2 en un hilo separado.
"""

import os
import sqlite3
import sys
import threading
import time

import zmq  # Librería de mensajería distribuida

# Añade el directorio raíz del proyecto al path para importar módulos comunes
sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from common.config_loader import load_config  # Carga configuración
from common.utils import log_componente       # Logging común

COMPONENTE = "monitoreo"

# Nombre de la base de datos principal (PC3)
DB_PRINCIPAL = "pc3_principal.db"


# =========================================================
# HEARTBEAT
# =========================================================

def enviar_heartbeat():
    """
    Envía mensajes periódicos "heartbeat" a PC2 para indicar que PC3 está activo.
    Se ejecuta en un hilo independiente.
    """

    config = load_config()

    # IP de PC2 (destino del heartbeat)
    host_pc2 = "10.43.99.109"

    # Puerto configurado para healthcheck
    puerto = config["ports"]["healthcheck"]

    # Contexto ZeroMQ
    ctx = zmq.Context()

    # Socket tipo PUSH (envío unidireccional)
    push = ctx.socket(zmq.PUSH)

    # Endpoint destino
    endpoint = f"tcp://{host_pc2}:{puerto}"

    # Conexión al receptor
    push.connect(endpoint)

    log_componente(
        COMPONENTE,
        f"Heartbeat conectado a {endpoint}"
    )

    while True:
        # Envía mensaje de latido
        push.send_string("heartbeat")

        log_componente(
            COMPONENTE,
            "Heartbeat enviado"
        )

        # Espera antes del siguiente envío
        time.sleep(3)


# =========================================================
# CONSULTAR INTERSECCIÓN
# =========================================================

def consultar_interseccion(interseccion):
    """
    Consulta la base de datos para obtener:
    - Número de eventos registrados
    - Última acción del semáforo en la intersección
    """

    # Conexión a SQLite
    conn = sqlite3.connect(DB_PRINCIPAL)
    cursor = conn.cursor()

    # Cuenta eventos en la intersección
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM eventos
        WHERE interseccion = ?
        """,
        (interseccion,)
    )
    total_eventos = cursor.fetchone()[0]

    # Obtiene la última acción registrada
    cursor.execute(
        """
        SELECT estado, motivo, timestamp
        FROM acciones_semaforo
        WHERE interseccion = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (interseccion,)
    )
    accion = cursor.fetchone()

    # Cierra conexión
    conn.close()

    # Si hay datos de acción, construye respuesta detallada
    if accion:
        estado, motivo, timestamp = accion

        return (
            f"Intersección: {interseccion}\n"
            f"Estado actual: {estado}\n"
            f"Motivo: {motivo}\n"
            f"Última actualización: {timestamp}\n"
            f"Eventos registrados: {total_eventos}"
        )

    # Si no hay datos
    return f"No hay información para {interseccion}"


# =========================================================
# PRIORIDAD MANUAL
# =========================================================

def prioridad_manual(interseccion):
    """
    Simula el envío de una solicitud de prioridad manual.
    (En esta versión solo devuelve un mensaje)
    """

    return f"[PRIORIDAD] Solicitud enviada para {interseccion}"


# =========================================================
# MAIN
# =========================================================

def main():
    # Carga configuración del sistema
    config = load_config()

    # =====================================================
    # LANZA THREAD DE HEARTBEAT
    # =====================================================

    threading.Thread(
        target=enviar_heartbeat,
        daemon=True  # Se cierra automáticamente al terminar el programa
    ).start()

    # Puerto donde escucha solicitudes de monitoreo
    puerto = config["ports"]["monitoreo_to_analitica"]

    # Contexto ZeroMQ
    ctx = zmq.Context()

    # Socket tipo REP (responde a solicitudes)
    rep = ctx.socket(zmq.REP)

    # Escucha en todas las interfaces
    endpoint = f"tcp://*:{puerto}"

    # Bind del socket
    rep.bind(endpoint)

    log_componente(
        COMPONENTE,
        f"Servicio de monitoreo iniciado en {endpoint}"
    )

    try:
        while True:
            # Recibe mensaje del cliente
            mensaje = rep.recv_string()

            log_componente(
                COMPONENTE,
                f"Solicitud recibida: {mensaje}"
            )

            # Divide el mensaje en partes (comando + argumento)
            partes = mensaje.strip().split()

            # Validación básica del comando
            if len(partes) < 2:
                rep.send_string("Comando inválido")
                continue

            comando = partes[0].lower()
            interseccion = partes[1]

            # =============================================
            # CONSULTAR
            # =============================================

            if comando == "consultar":
                respuesta = consultar_interseccion(interseccion)
                rep.send_string(respuesta)

            # =============================================
            # PRIORIDAD
            # =============================================

            elif comando == "priorizar":
                respuesta = prioridad_manual(interseccion)
                rep.send_string(respuesta)

            # =============================================
            # COMANDO DESCONOCIDO
            # =============================================

            else:
                rep.send_string("Comando no reconocido")

    except KeyboardInterrupt:
        # Permite detener el servicio manualmente
        log_componente(
            COMPONENTE,
            "Servicio detenido manualmente",
            nivel="WARN"
        )

    finally:
        # Cierre limpio de recursos
        rep.close(linger=0)
        ctx.term()


# Punto de entrada del programa
if __name__ == "__main__":
    main()
```
