#!/usr/bin/env python3

import os
import sqlite3
import sys
import threading
import time

import zmq

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from common.config_loader import load_config
from common.utils import log_componente

COMPONENTE = "monitoreo"

DB_PRINCIPAL = "pc3_principal.db"


# =========================================================
# HEARTBEAT
# =========================================================

def enviar_heartbeat():

    config = load_config()

    host_pc2 = "10.43.99.109"

    puerto = config["ports"]["healthcheck"]

    ctx = zmq.Context()

    push = ctx.socket(zmq.PUSH)

    endpoint = f"tcp://{host_pc2}:{puerto}"

    push.connect(endpoint)

    log_componente(
        COMPONENTE,
        f"Heartbeat conectado a {endpoint}"
    )

    while True:

        push.send_string("heartbeat")

        log_componente(
            COMPONENTE,
            "Heartbeat enviado"
        )

        time.sleep(3)


# =========================================================
# CONSULTAR INTERSECCIÓN
# =========================================================

def consultar_interseccion(interseccion):

    conn = sqlite3.connect(DB_PRINCIPAL)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM eventos
        WHERE interseccion = ?
        """,
        (interseccion,)
    )

    total_eventos = cursor.fetchone()[0]

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

    conn.close()

    if accion:

        estado, motivo, timestamp = accion

        return (
            f"Intersección: {interseccion}\n"
            f"Estado actual: {estado}\n"
            f"Motivo: {motivo}\n"
            f"Última actualización: {timestamp}\n"
            f"Eventos registrados: {total_eventos}"
        )

    return (
        f"No hay información para {interseccion}"
    )


# =========================================================
# PRIORIDAD MANUAL
# =========================================================

def prioridad_manual(interseccion):

    return (
        f"[PRIORIDAD] Solicitud enviada para {interseccion}"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    config = load_config()

    # =====================================================
    # THREAD HEARTBEAT
    # =====================================================

    threading.Thread(
        target=enviar_heartbeat,
        daemon=True
    ).start()

    puerto = config["ports"]["monitoreo_to_analitica"]

    ctx = zmq.Context()

    rep = ctx.socket(zmq.REP)

    endpoint = f"tcp://*:{puerto}"

    rep.bind(endpoint)

    log_componente(
        COMPONENTE,
        f"Servicio de monitoreo iniciado en {endpoint}"
    )

    try:

        while True:

            mensaje = rep.recv_string()

            log_componente(
                COMPONENTE,
                f"Solicitud recibida: {mensaje}"
            )

            partes = mensaje.strip().split()

            if len(partes) < 2:

                rep.send_string(
                    "Comando inválido"
                )

                continue

            comando = partes[0].lower()

            interseccion = partes[1]

            # =============================================
            # CONSULTAR
            # =============================================

            if comando == "consultar":

                respuesta = consultar_interseccion(
                    interseccion
                )

                rep.send_string(respuesta)

            # =============================================
            # PRIORIDAD
            # =============================================

            elif comando == "priorizar":

                respuesta = prioridad_manual(
                    interseccion
                )

                rep.send_string(respuesta)

            # =============================================
            # DESCONOCIDO
            # =============================================

            else:

                rep.send_string(
                    "Comando no reconocido"
                )

    except KeyboardInterrupt:

        log_componente(
            COMPONENTE,
            "Servicio detenido manualmente",
            nivel="WARN"
        )

    finally:

        rep.close(linger=0)

        ctx.term()


if __name__ == "__main__":
    main()
