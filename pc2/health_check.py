#!/usr/bin/env python3
"""
Health check (PC2).
Comprueba periódicamente si PC3 está disponible usando una conexión TCP.
Versión 1: solo detección y logging (sin notificación a otros componentes).
"""

import os
import socket
import sys
import time

# Permite importar módulos del proyecto (directorio padre)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config_loader import load_config  # Carga configuración desde archivo
from common.utils import log_componente       # Función de logging común

COMPONENTE = "health_check"

# Parámetros configurables
INTERVALO_ENTRE_CHEQUEOS_S = 15       # Tiempo entre chequeos
TIMEOUT_CONEXION_S = 3.0              # Timeout de conexión TCP
REINTENTOS = 3                        # Número de intentos por chequeo
PAUSA_ENTRE_REINTENTOS_S = 0.5        # Espera entre intentos


def _probar_tcp(host: str, puerto: int, timeout_s: float) -> bool:
    """
    Intenta abrir una conexión TCP al host y puerto indicados.
    Devuelve True si la conexión se establece correctamente.
    """
    try:
        # Intenta crear una conexión TCP con timeout
        with socket.create_connection((host, puerto), timeout=timeout_s):
            return True
    except OSError:
        # Error de conexión (timeout, rechazo, etc.)
        return False


def verificar_pc3(host: str, puerto: int) -> bool:
    """
    Verifica disponibilidad de PC3 con múltiples intentos.
    Devuelve True si alguno de los intentos tiene éxito.
    """
    for intento in range(1, REINTENTOS + 1):
        # Intenta conexión TCP
        if _probar_tcp(host, puerto, TIMEOUT_CONEXION_S):
            # Si no fue el primer intento, se registra recuperación parcial
            if intento > 1:
                log_componente(
                    COMPONENTE,
                    f"Éxito en intento {intento}/{REINTENTOS} hacia {host}:{puerto}.",
                )
            return True

        # Si falla, se registra intento fallido
        log_componente(
            COMPONENTE,
            f"Intento {intento}/{REINTENTOS} fallido hacia {host}:{puerto}.",
            nivel="WARN",
        )

        # Espera antes del siguiente intento (si no es el último)
        if intento < REINTENTOS:
            time.sleep(PAUSA_ENTRE_REINTENTOS_S)

    # Si todos los intentos fallan
    return False


def main():
    # Carga configuración del sistema
    config = load_config()
    host_pc3 = config["pc3"]["host"]

    # Se utiliza el puerto de la base de datos principal como indicador de servicio activo
    puerto = config["ports"]["analitica_to_db_principal"]

    # Log inicial con parámetros del sistema
    log_componente(
        COMPONENTE,
        (
            f"Inicio | objetivo PC3={host_pc3}:{puerto} | cada {INTERVALO_ENTRE_CHEQUEOS_S}s | "
            f"timeout TCP={TIMEOUT_CONEXION_S}s | reintentos={REINTENTOS}"
        ),
    )

    log_componente(
        COMPONENTE,
        "Nota: esta versión solo detecta estado y registra logs.",
    )

    try:
        while True:
            # Ejecuta verificación de disponibilidad
            disponible = verificar_pc3(host_pc3, puerto)

            if disponible:
                # PC3 responde correctamente
                log_componente(
                    COMPONENTE,
                    f"Estado PC3: DISPONIBLE (TCP OK en {host_pc3}:{puerto}).",
                )
            else:
                # PC3 no responde tras varios intentos
                log_componente(
                    COMPONENTE,
                    f"Estado PC3: NO DISPONIBLE (sin respuesta TCP estable en {host_pc3}:{puerto}).",
                    nivel="ERROR",
                )

            # Espera hasta el siguiente chequeo
            time.sleep(INTERVALO_ENTRE_CHEQUEOS_S)

    except KeyboardInterrupt:
        # Permite finalizar el programa manualmente con Ctrl+C
        log_componente(COMPONENTE, "Interrumpido por teclado (Ctrl+C).", nivel="WARN")


# Punto de entrada del programa
if __name__ == "__main__":
    main()
