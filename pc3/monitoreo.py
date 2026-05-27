#!/usr/bin/env python3
"""
Monitoreo (PC3).
- Hilo heartbeat: envía pulso periódico a health_check de PC2.
- Loop principal: atiende consultas REQ/REP de clientes (cliente_monitoreo.py).
"""

import json
import os
import sqlite3
import sys
import threading
import time
import zmq

# Modifica el path de ejecución de Python para poder importar utilidades compartidas desde la raíz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importaciones de configuración y sistemas de logs comunes
from common.config_loader import load_config
from common.utils import log_componente

# Identificadores globales y rutas de acceso físico a las bases de datos de la PC3
COMPONENTE   = "monitoreo"
DB_PRINCIPAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pc3_principal.db")


# ---------------------------------------------------------------------------
# Heartbeat hacia PC2 (Ejecución en Hilo Secundario)
# ---------------------------------------------------------------------------

def enviar_heartbeat(host_pc2: str, puerto: int) -> None:
    """
    Mantiene un canal PUSH abierto hacia la máquina PC2.
    Envía de forma constante señales periódicas de vida para evitar falsos positivos de caída.
    """
    ctx  = zmq.Context()
    push = ctx.socket(zmq.PUSH) # Inicializa socket de empuje unidireccional
    endpoint = f"tcp://{host_pc2}:{puerto}"
    push.connect(endpoint) # Se conecta al listener de salud en la máquina intermedia
    
    log_componente(COMPONENTE, f"Heartbeat conectado a {endpoint}")
    
    try:
        while True:
            # Emite el token regular de presencia textual
            push.send_string("heartbeat")
            log_componente(COMPONENTE, "Heartbeat enviado")
            # Frecuencia del pulso: Espera exactamente 3 segundos antes del siguiente ciclo
            time.sleep(3)
    except Exception as exc:
        # Captura cualquier error de socket o de red e informa al log central
        log_componente(COMPONENTE, f"Heartbeat error: {exc}", nivel="ERROR")
    finally:
        # Libera recursos e inactiva los subprocesos de red de ZMQ
        push.close(linger=0)
        ctx.term()


# ---------------------------------------------------------------------------
# Capa de Consultas Analíticas (SQLite Interacting)
# ---------------------------------------------------------------------------

def consultar_interseccion(interseccion: str) -> str:
    """
    Realiza una consulta agregada para extraer el estado resumido de una intersección vial.
    Devuelve un string serializado en formato JSON.
    """
    try:
        # Abre el descriptor de archivo de la base de datos local SQLite
        conn   = sqlite3.connect(DB_PRINCIPAL)
        cursor = conn.cursor()

        # QUERY 1: Cuenta el volumen total de eventos históricos recibidos de cualquier sensor en esa esquina
        cursor.execute(
            "SELECT COUNT(*) FROM eventos WHERE interseccion = ?",
            (interseccion,),
        )
        total_eventos = cursor.fetchone()[0] # Extrae el entero del conteo global

        # QUERY 2: Obtiene la última acción de semáforo registrada ordenando por ID auto-incremental decreciente
        cursor.execute(
            """
            SELECT estado, motivo, timestamp
            FROM acciones_semaforo
            WHERE interseccion = ?
            ORDER BY id DESC LIMIT 1
            """,
            (interseccion,),
        )
        accion = cursor.fetchone() # Captura la tupla de resultados o devuelve None
        conn.close() # Cierra el puntero de conexión inmediatamente para evitar bloqueos del archivo de BD

        # Si existen registros de comandos en esa intersección, concatena el JSON de respuesta
        if accion:
            estado, motivo, timestamp = accion
            return json.dumps({
                "interseccion":   interseccion,
                "estado":         estado,
                "motivo":         motivo,
                "ultimo_cambio":  timestamp,
                "total_eventos":  total_eventos,
            }, ensure_ascii=False)

        # Respuesta de contingencia si la calle es válida pero no ha registrado tráfico aún
        return json.dumps({"interseccion": interseccion, "info": "sin datos aún"})

    except sqlite3.Error as exc:
        # Manejo de excepciones en caso de corrupción o fallo en el motor SQLite
        return json.dumps({"error": str(exc)})


def consultar_historico(interseccion: str, limite: int = 10) -> str:
    """
    Recupera una traza de auditoría con las últimas 'N' decisiones tomadas por el motor analítico.
    """
    try:
        conn   = sqlite3.connect(DB_PRINCIPAL)
        cursor = conn.cursor()
        
        # Ejecuta la consulta de filtrado aplicando un parámetro dinámico LIMIT
        cursor.execute(
            """
            SELECT estado, motivo, duracion, timestamp
            FROM acciones_semaforo
            WHERE interseccion = ?
            ORDER BY id DESC LIMIT ?
            """,
            (interseccion, limite),
        )
        
        # List Comprehension para parsear las tuplas nativas a diccionarios limpios de Python
        rows = [
            {"estado": r[0], "motivo": r[1], "duracion": r[2], "timestamp": r[3]}
            for r in cursor.fetchall()
        ]
        conn.close()
        
        # Retorna el árbol estructurado convertido a JSON string
        return json.dumps({"interseccion": interseccion, "historico": rows}, ensure_ascii=False)
    except sqlite3.Error as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Hilo Principal (Orquestador de Comandos REP)
# ---------------------------------------------------------------------------

def main():
    # 1. PARSEO DE DIRECCIONES DE INFRAESTRUCTURA
    config   = load_config()
    host_pc2 = config["pc2"]["host"]                  # Dirección IP de la máquina intermedia (PC2)
    puerto_hc   = config["ports"]["healthcheck"]      # Puerto de escucha del monitor de salud
    puerto_rep  = config["ports"]["monitoreo_to_analitica"] # Puerto local para peticiones síncronas

    # 2. DISPARO DEL HILO DE PULSO (BACKGROUND HEARTBEAT)
    # Se configura como daemon=True para que no impida el cierre del script si el bucle principal cae
    threading.Thread(
        target=enviar_heartbeat,
        args=(host_pc2, puerto_hc),
        daemon=True,
    ).start()

    # 3. ENLAZADO DEL SOCKET REP (RESPONSE)
    ctx = zmq.Context()
    rep = ctx.socket(zmq.REP) # Socket síncrono del patrón Pregunta/Respuesta
    rep.bind(f"tcp://*:{puerto_rep}") # Escucha en todas las interfaces de red locales (* indicando 0.0.0.0)
    log_componente(COMPONENTE, f"REP escuchando en tcp://*:{puerto_rep}")

    # 4. BUCLE DE ATENCIÓN A SOLICITUDES DE CLIENTES
    try:
        while True:
            # Espera bloqueante de strings entrantes por la red
            mensaje = rep.recv_string()
            log_componente(COMPONENTE, f"Solicitud: {mensaje!r}")

            # Descompone el string por espacios en blanco para separar el comando de los argumentos
            partes  = mensaje.strip().split()
            comando = partes[0].lower() if partes else ""

            # EVALUACIÓN DE OPCIONES DE MENSAJERÍA:
            # Ejecuta la consulta puntual de estado actual (Uso: "consultar I1")
            if comando == "consultar" and len(partes) >= 2:
                rep.send_string(consultar_interseccion(partes[1]))

            # Ejecuta la consulta del listado histórico (Uso: "historico I1 15")
            elif comando == "historico" and len(partes) >= 2:
                # Si el usuario no provee un límite explícito, aplica el valor de fallback (10)
                limite = int(partes[2]) if len(partes) >= 3 else 10
                rep.send_string(consultar_historico(partes[1], limite))

            # Manejo preventivo de errores sintácticos para evitar colgar el patrón REQ/REP
            else:
                rep.send_string(json.dumps({
                    "error": "comando_desconocido",
                    "uso":   "consultar <INTER> | historico <INTER> [N]",
                }))

    # 5. PROCEDIMIENTO DE APAGADO DE COMPONENTES
    except KeyboardInterrupt:
        # Permite la cancelación del servicio mediante la señal de teclado Ctrl+C
        log_componente(COMPONENTE, "Detenido manualmente.", nivel="WARN")
    finally:
        # Cierra los hilos del socket liberando el puerto bindeado del S.O.
        rep.close(linger=0)
        ctx.term()


if __name__ == "__main__":
    main()
