"""
utils/base_test.py — Clase base para todas las suites de prueba.
Provee helpers ZMQ (REQ/REP, PUB/SUB, PUSH/PULL) y registro de resultados.
"""

import time
import json
import traceback
from typing import Any, Dict, Optional, List
from utils.config import TestConfig

try:
    import zmq
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False


class TestResult:
    def __init__(self, name: str):
        self.name        = name
        self.status      = "SKIP"
        self.error       = None
        self.duration_ms = 0.0
        self.data        = {}

    def as_dict(self) -> Dict:
        return {
            "name":        self.name,
            "status":      self.status,
            "error":       self.error,
            "duration_ms": round(self.duration_ms, 2),
            "data":        self.data,
        }


class BaseTestSuite:
    """
    Clase base para suites de prueba.

    Subclases deben definir:
        self.tests = [("Nombre legible", self._nombre_metodo), ...]
    y los métodos correspondientes que reciben un TestResult y lo modifican.
    """

    def __init__(self, config: TestConfig):
        self.config  = config
        self.tests: List = []      # lista de (nombre, callable)
        self._ctx: Any  = None    # contexto ZMQ

    # ── ZMQ helpers ───────────────────────────────────────────────

    def _zmq_ctx(self):
        if not ZMQ_AVAILABLE:
            raise RuntimeError("pyzmq no está instalado. Ejecuta: pip install pyzmq")
        if self._ctx is None:
            self._ctx = zmq.Context()
        return self._ctx

    def _req_socket(self, host: str, port: int):
        ctx = self._zmq_ctx()
        s = ctx.socket(zmq.REQ)
        s.setsockopt(zmq.RCVTIMEO, self.config.timeout * 1000)
        s.setsockopt(zmq.SNDTIMEO, self.config.timeout * 1000)
        s.connect(f"tcp://{host}:{port}")
        return s

    def _push_socket(self, host: str, port: int):
        ctx = self._zmq_ctx()
        s = ctx.socket(zmq.PUSH)
        s.setsockopt(zmq.SNDTIMEO, self.config.timeout * 1000)
        s.connect(f"tcp://{host}:{port}")
        return s

    def _pull_socket(self, port: int, bind: bool = True):
        ctx = self._zmq_ctx()
        s = ctx.socket(zmq.PULL)
        s.setsockopt(zmq.RCVTIMEO, self.config.timeout * 1000)
        if bind:
            s.bind(f"tcp://*:{port}")
        return s

    def _pub_socket(self, port: int):
        ctx = self._zmq_ctx()
        s = ctx.socket(zmq.PUB)
        s.bind(f"tcp://*:{port}")
        return s

    def _sub_socket(self, host: str, port: int, topic: str = ""):
        ctx = self._zmq_ctx()
        s = ctx.socket(zmq.SUB)
        s.setsockopt(zmq.RCVTIMEO, self.config.timeout * 1000)
        s.connect(f"tcp://{host}:{port}")
        s.setsockopt_string(zmq.SUBSCRIBE, topic)
        return s

    def _send_req(self, socket, payload: dict) -> Optional[dict]:
        """Envía un diccionario por REQ y retorna la respuesta o None si hay timeout."""
        try:
            socket.send_json(payload)
            return socket.recv_json()
        except Exception:
            return None

    def _close(self, *sockets):
        for s in sockets:
            try:
                s.close()
            except Exception:
                pass

    # ── Ejecución de pruebas ──────────────────────────────────────

    def run(self) -> List[Dict]:
        results = []
        for name, fn in self.tests:
            tr = TestResult(name)
            t0 = time.perf_counter()
            try:
                fn(tr)
            except Exception as exc:
                tr.status = "FAIL"
                tr.error  = f"{type(exc).__name__}: {exc}"
                tr.data["traceback"] = traceback.format_exc()
            finally:
                tr.duration_ms = (time.perf_counter() - t0) * 1000
            results.append(tr.as_dict())
        return results

    # ── Utilidades de validación ──────────────────────────────────

    def _assert(self, condition: bool, tr: TestResult, msg: str):
        if not condition:
            tr.status = "FAIL"
            tr.error  = msg
            raise AssertionError(msg)

    def _skip_if_no_zmq(self, tr: TestResult):
        if not ZMQ_AVAILABLE:
            tr.status = "SKIP"
            tr.error  = "pyzmq no instalado"
            raise SystemExit("skip")
