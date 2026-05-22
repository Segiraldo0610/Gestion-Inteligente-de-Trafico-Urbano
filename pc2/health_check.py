#!/usr/bin/env python3
"""
Health check (PC2).
Comprueba de forma periódica si PC3 está disponible (proxy: puerto de BD principal).
Versión 1: solo detección y logging; la notificación a analítica queda preparada como comentario.
"""

import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config_loader import load_config
from common.utils import log_componente

COMPONENTE = "health_check"

# Parámetros fáciles de ajustar en clase / defensa
INTERVALO_ENTRE_CHEQUEOS_S = 15
TIMEOUT_CONEXION_S = 3.0
REINTENTOS = 3
PAUSA_ENTRE_REINTENTOS_S = 0.5


def _probar_tcp(host: str, puerto: int, timeout_s: float) -> bool:
    """
    Intenta abrir una conexión TCP de corta duración.
    Devuelve True si el puerto acepta la conexión.
    """
    try:
        with socket.create_connection((host, puerto), timeout=timeout_s):
            return True
    except OSError:
        return False


def verificar_pc3(host: str, puerto: int) -> bool:
    """
    Reintenta varias veces antes de declarar caída la comprobación.
    """
    for intento in range(1, REINTENTOS + 1):
        if _probar_tcp(host, puerto, TIMEOUT_CONEXION_S):
            if intento > 1:
                log_componente(
                    COMPONENTE,
                    f"Éxito en intento {intento}/{REINTENTOS} hacia {host}:{puerto}.",
                )
            return True

        log_componente(
            COMPONENTE,
            f"Intento {intento}/{REINTENTOS} fallido hacia {host}:{puerto}.",
            nivel="WARN",
        )
        if intento < REINTENTOS:
            time.sleep(PAUSA_ENTRE_REINTENTOS_S)

    return False


def main():
    config = load_config()
    host_pc3 = config["pc3"]["host"]
    # Se usa el mismo puerto que escucha bd_principal.py (PULL) como señal de servicio activo en PC3.
    puerto = config["ports"]["analitica_to_db_principal"]

    log_componente(
        COMPONENTE,
        (
            f"Inicio | objetivo PC3={host_pc3}:{puerto} | cada {INTERVALO_ENTRE_CHEQUEOS_S}s | "
            f"timeout TCP={TIMEOUT_CONEXION_S}s | reintentos={REINTENTOS}"
        ),
    )
    log_componente(
        COMPONENTE,
        "Nota: versión 1 solo detecta y registra; integrar con analítica se puede añadir después.",
    )

    try:
        while True:
            disponible = verificar_pc3(host_pc3, puerto)

            if disponible:
                log_componente(
                    COMPONENTE,
                    f"Estado PC3: DISPONIBLE (TCP OK en {host_pc3}:{puerto}).",
                )
                # Futuro: notificar_analitica(disponible=True)
            else:
                log_componente(
                    COMPONENTE,
                    f"Estado PC3: NO DISPONIBLE (sin respuesta TCP estable en {host_pc3}:{puerto}).",
                    nivel="ERROR",
                )
                # Futuro: notificar_analitica(disponible=False)

            time.sleep(INTERVALO_ENTRE_CHEQUEOS_S)
    except KeyboardInterrupt:
        log_componente(COMPONENTE, "Interrumpido por teclado (Ctrl+C).", nivel="WARN")


if __name__ == "__main__":
    main()
