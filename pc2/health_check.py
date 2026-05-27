#!/usr/bin/env python3
"""
Health check (PC2).
Comprueba periódicamente si PC3 está disponible.
Publica el estado via ZMQ PUB para que analítica reaccione en tiempo real.

Protocolo de notificación:
  - "PC3_UP"   → PC3 disponible, analítica debe usar BD principal.
  - "PC3_DOWN" → PC3 caído, analítica debe redirigir a réplica.

Solo publica cuando el estado cambia (evita ruido innecesario).
"""

import os
import socket
import sys
import time
import zmq

# Modifica el path de Python para permitir importaciones desde la raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importaciones de utilidades internas del sistema distribuido
from common.config_loader import load_config
from common.utils import log_componente

# Identificador único de este componente para el sistema de logs
COMPONENTE = "health_check"

# Parámetros de temporización y resiliencia para el sondeo de red
INTERVALO_ENTRE_CHEQUEOS_S = 10  # Tiempo de espera (segundos) entre cada ciclo de verificación
TIMEOUT_CONEXION_S         = 3.0 # Tiempo máximo de espera para abrir el socket TCP antes de fallar
REINTENTOS                 = 3   # Intentos consecutivos fallidos necesarios para confirmar caída
PAUSA_ENTRE_REINTENTOS_S   = 0.5 # Tiempo de espera entre reintentos en caso de error intermitente

# Eventos de string que se enviarán por el canal PUB
MSG_UP   = "PC3_UP"
MSG_DOWN = "PC3_DOWN"


def _probar_tcp(host: str, puerto: int, timeout_s: float) -> bool:
    """
    Subrutina de bajo nivel que realiza un 'ping' TCP al puerto objetivo.
    Abre una conexión rudimentaria y el uso de 'with' garantiza que el socket
    se cierre de inmediato al terminar (exitoso o no).
    """
    try:
        # Intenta establecer el apretón de manos (handshake) TCP
        with socket.create_connection((host, puerto), timeout=timeout_s):
            return True # Conexión establecida con éxito
    except OSError:
        return False # Error de red (host inaccesible, puerto cerrado, timeout, etc.)


def verificar_pc3(host: str, puerto: int) -> bool:
    """
    Orquestador de la política de reintentos.
    Evita falsos positivos causados por microcortes temporales en la red local.
    """
    for intento in range(1, REINTENTOS + 1):
        # Llama a la subrutina TCP
        if _probar_tcp(host, puerto, TIMEOUT_CONEXION_S):
            if intento > 1:
                # Si tuvo éxito pero requirió más de un intento, registra un log de advertencia/recuperación
                log_componente(
                    COMPONENTE,
                    f"Éxito en intento {intento}/{REINTENTOS} hacia {host}:{puerto}.",
                )
            return True # Retorna de inmediato si la máquina responde
            
        # Registra el fallo actual del intento en el buffer de logs
        log_componente(
            COMPONENTE,
            f"Intento {intento}/{REINTENTOS} fallido hacia {host}:{puerto}.",
            nivel="WARN",
        )
        
        # Si todavía le quedan intentos disponibles en este ciclo, duerme el hilo brevemente
        if intento < REINTENTOS:
            time.sleep(PAUSA_ENTRE_REINTENTOS_S)
            
    return False # Si agota todos los reintentos sin éxito, confirma que la máquina está caída


def main():
    # 1. CARGA DE CONFIGURACIÓN Y DIRECCIONAMIENTO
    config = load_config()
    host_pc2 = config["pc2"]["host"]                               # IP de la máquina local (PC2)
    host_pc3 = config["pc3"]["host"]                               # IP del objetivo a vigilar (PC3)
    puerto_chequeo = config["ports"]["analitica_to_db_principal"]  # Puerto de la BD en PC3 usado para el test
    puerto_pub     = config["ports"]["healthcheck"]                # Puerto local donde se publicará el estado

    # 2. CONFIGURACIÓN DEL CANAL PUB DE ZERO MQ
    ctx = zmq.Context()
    pub = ctx.socket(zmq.PUB) # Socket tipo Editor/Publicador
    endpoint_pub = f"tcp://{host_pc2}:{puerto_pub}"
    pub.bind(endpoint_pub) # Reserva el puerto en la máquina local para los suscriptores

    # Pausa técnica preventiva para mitigar la pérdida del primer mensaje (Slow Joiner de ZMQ)
    time.sleep(1.0)

    log_componente(
        COMPONENTE,
        f"Inicio | objetivo PC3={host_pc3}:{puerto_chequeo} | "
        f"PUB estado en {endpoint_pub} | intervalo={INTERVALO_ENTRE_CHEQUEOS_S}s",
    )

    # Variable de memoria de estado fundamental para aplicar el patrón de supresión de ruido.
    # Inicializa en None para forzar el envío del primer resultado, sea cual sea.
    estado_anterior: bool | None = None   

    # 3. BUCLE INFINITO DE MONITOREO (HEARTBEAT LOGIC)
    try:
        while True:
            # Lanza las pruebas de conectividad hacia la PC3
            disponible = verificar_pc3(host_pc3, puerto_chequeo)

            # MÁQUINA DE ESTADOS COMPORTAMENTAL: ¿Hubo un cambio respecto al ciclo anterior?
            if disponible != estado_anterior:
                # El estado mutó (ej: de ONLINE a OFFLINE o viceversa) -> Se requiere notificación
                mensaje = MSG_UP if disponible else MSG_DOWN
                pub.send_string(mensaje) # Transmite la alerta instantáneamente por el socket PUB

                # Bloques condicionales para logs estéticos según el tipo de transición
                if disponible:
                    log_componente(
                        COMPONENTE,
                        f"PC3 DISPONIBLE → publicado '{MSG_UP}' en {endpoint_pub}",
                    )
                else:
                    log_componente(
                        COMPONENTE,
                        f"PC3 CAÍDO → publicado '{MSG_DOWN}' en {endpoint_pub}",
                        nivel="ERROR",
                    )
                # Actualiza la variable de control con el nuevo estado verificado
                estado_anterior = disponible
            else:
                # El estado se mantiene idéntico -> No se publica nada por ZMQ para no saturar la red.
                # Solo genera un log local interno para auditoría visual silenciosa.
                nivel = "INFO" if disponible else "WARN"
                log_componente(
                    COMPONENTE,
                    f"PC3 {'OK' if disponible else 'SIGUE CAÍDO'} (sin cambio de estado)",
                    nivel=nivel,
                )

            # Pausa el proceso completo durante los 10 segundos configurados antes de reevaluar
            time.sleep(INTERVALO_ENTRE_CHEQUEOS_S)

    # 4. RUTINA DE DESCONEXIÓN LIMPIA
    except KeyboardInterrupt:
        # Detiene el bucle de forma segura al presionar Ctrl+C
        log_componente(COMPONENTE, "Detenido manualmente.", nivel="WARN")
    finally:
        # Cierra el publicador y destruye el contexto de red liberando los hilos internos del núcleo de ZMQ
        pub.close(linger=0)
        ctx.term()


if __name__ == "__main__":
    main()
