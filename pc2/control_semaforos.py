#!/usr/bin/env python3
"""
Control de semáforos (PC2).
Recibe comandos PUSH/PULL desde analítica en el puerto analitica_to_semaforos.
"""

import json
import os
import sys

import zmq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config_loader import load_config
from common.utils import generar_intersecciones_3x3, log_componente

COMPONENTE = "control_semaforos"
ESTADOS_PERMITIDOS = frozenset({"VERDE", "ROJO"})


class Semaforo:
    """Representa un semáforo en una intersección (solo ROJO o VERDE)."""

    def __init__(self, interseccion: str, estado: str = "ROJO"):
        self.interseccion = interseccion
        self.estado = estado.upper() if estado else "ROJO"

    def aplicar(self, nuevo_estado: str) -> bool:
        """
        Cambia el estado si es válido y distinto al actual.
        Devuelve True si hubo cambio.
        """
        s = nuevo_estado.strip().upper()
        if s not in ESTADOS_PERMITIDOS:
            return False
        if s == self.estado:
            return False
        self.estado = s
        return True


def _normalizar_comando(msg: dict) -> dict | None:
    """Valida campos mínimos del JSON recibido."""
    if not isinstance(msg, dict):
        return None
    for clave in ("interseccion", "estado", "duracion", "motivo"):
        if clave not in msg:
            return None
    return msg


def main():
    config = load_config()
    host_pc2 = config["pc2"]["host"]
    puerto = config["ports"]["analitica_to_semaforos"]

    intersecciones = generar_intersecciones_3x3()
    semaforos = {codigo: Semaforo(codigo, "ROJO") for codigo in intersecciones}

    ctx = zmq.Context()
    socket = ctx.socket(zmq.PULL)
    endpoint = f"tcp://{host_pc2}:{puerto}"
    socket.bind(endpoint)

    log_componente(COMPONENTE, f"PULL escuchando en {endpoint} (esperando PUSH de analítica)")

    try:
        while True:
            raw = socket.recv_string()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                log_componente(COMPONENTE, f"Mensaje JSON inválido: {raw!r}", nivel="ERROR")
                continue

            cmd = _normalizar_comando(data)
            if cmd is None:
                log_componente(COMPONENTE, f"Comando incompleto o no es objeto: {data!r}", nivel="WARN")
                continue

            inter = str(cmd["interseccion"]).strip()
            estado_nuevo = str(cmd["estado"]).strip().upper()
            duracion = cmd["duracion"]
            motivo = str(cmd["motivo"]).strip()

            if inter not in semaforos:
                log_componente(COMPONENTE, f"Intersección desconocida: {inter}", nivel="WARN")
                continue

            if estado_nuevo not in ESTADOS_PERMITIDOS:
                log_componente(
                    COMPONENTE,
                    f"Estado no permitido (solo VERDE/ROJO): {estado_nuevo!r}",
                    nivel="WARN",
                )
                continue

            sem = semaforos[inter]
            anterior = sem.estado
            cambio = sem.aplicar(estado_nuevo)

            if cambio:
                log_componente(
                    COMPONENTE,
                    (
                        f"CAMBIO | {inter}: {anterior} -> {sem.estado} | "
                        f"duracion_s={duracion} | motivo={motivo}"
                    ),
                )
                print(
                    f"[{inter}] Semáforo: {anterior} -> {sem.estado} "
                    f"(duración solicitada: {duracion}s, motivo: {motivo})"
                )
            else:
                if anterior == estado_nuevo:
                    log_componente(
                        COMPONENTE,
                        f"Sin cambio | {inter} ya en {anterior} | motivo={motivo}",
                    )
    except KeyboardInterrupt:
        log_componente(COMPONENTE, "Interrumpido por teclado (Ctrl+C).", nivel="WARN")
    finally:
        socket.close(linger=0)
        ctx.term()


if __name__ == "__main__":
    main()
