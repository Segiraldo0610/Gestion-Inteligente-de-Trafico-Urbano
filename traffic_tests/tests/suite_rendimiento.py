"""
tests/suite_rendimiento.py — Pruebas de rendimiento (Tabla 1 del enunciado).

Escenarios:
  P01 — 1 sensor de cada tipo, datos cada 10 s → solicitudes almacenadas en 2 min
  P02 — 2 sensores de cada tipo, datos cada 5 s → solicitudes almacenadas en 2 min
  P03 — Latencia usuario→semáforo en escenario 1 sensor
  P04 — Latencia usuario→semáforo en escenario 2 sensores
  P05 — Comparación diseño monohilo vs diseño multihilo (Broker)
  P06 — Throughput del broker bajo carga sostenida
"""

import time
import json
import threading
import statistics
from datetime import datetime, timezone
from typing import List

from utils.base_test import BaseTestSuite, TestResult
from utils.config import TestConfig

try:
    import zmq
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False


def _ts():
    return datetime.now(timezone.utc).isoformat()


class PerformanceTestSuite(BaseTestSuite):

    MEASURE_WINDOW_S = 120   # 2 minutos según enunciado

    def __init__(self, config: TestConfig):
        super().__init__(config)
        self.tests = [
            ("P01 - Solicitudes en BD en 2 min (1 sensor/tipo, c/10s)",    self._p01_throughput_1s),
            ("P02 - Solicitudes en BD en 2 min (2 sensores/tipo, c/5s)",   self._p02_throughput_2s),
            ("P03 - Latencia usuario→semáforo (escenario 1 sensor)",       self._p03_latencia_1s),
            ("P04 - Latencia usuario→semáforo (escenario 2 sensores)",     self._p04_latencia_2s),
            ("P05 - Comparación throughput mono vs multihilo",              self._p05_mono_vs_multi),
            ("P06 - Throughput broker bajo carga sostenida 30s",           self._p06_broker_carga),
        ]

    # ══════════════════════════════════════════════════════════════
    # P01 — 1 sensor/tipo, 10 s
    # ══════════════════════════════════════════════════════════════

    def _p01_throughput_1s(self, tr: TestResult):
        """
        Lanza 1 hilo por tipo de sensor (3 en total), cada uno envía eventos
        cada 10 s durante 2 minutos. Al finalizar consulta cuántos registros
        almacenó la BD principal.
        """
        self._skip_if_no_zmq(tr)
        cfg = self.config

        count_before = self._count_bd_records(cfg.host_pc3, cfg.port_monitor_req)
        sent_events  = self._run_sensor_scenario(
            n_sensors_per_type=1,
            interval_s=cfg.sensor_interval_s,
            duration_s=self.MEASURE_WINDOW_S,
        )
        time.sleep(3)   # margen para que la BD procese los últimos mensajes
        count_after  = self._count_bd_records(cfg.host_pc3, cfg.port_monitor_req)

        stored  = count_after - count_before
        rate    = stored / (self.MEASURE_WINDOW_S / 60)  # registros/min

        tr.status = "PASS"
        tr.data   = {
            "escenario":          "1 sensor/tipo, 10 s",
            "eventos_enviados":   sent_events,
            "registros_en_bd":    stored,
            "tasa_por_minuto":    round(rate, 2),
            "duracion_medicion_s":self.MEASURE_WINDOW_S,
        }
        print(f"\n    → Enviados: {sent_events}  |  Almacenados en BD: {stored}  "
              f"|  {rate:.1f} reg/min")

    # ══════════════════════════════════════════════════════════════
    # P02 — 2 sensores/tipo, 5 s
    # ══════════════════════════════════════════════════════════════

    def _p02_throughput_2s(self, tr: TestResult):
        """
        Lanza 2 hilos por tipo de sensor (6 en total), cada uno envía eventos
        cada 5 s durante 2 minutos.
        """
        self._skip_if_no_zmq(tr)
        cfg = self.config

        count_before = self._count_bd_records(cfg.host_pc3, cfg.port_monitor_req)
        sent_events  = self._run_sensor_scenario(
            n_sensors_per_type=2,
            interval_s=cfg.sensor_interval_s2,
            duration_s=self.MEASURE_WINDOW_S,
        )
        time.sleep(3)
        count_after  = self._count_bd_records(cfg.host_pc3, cfg.port_monitor_req)

        stored  = count_after - count_before
        rate    = stored / (self.MEASURE_WINDOW_S / 60)

        tr.status = "PASS"
        tr.data   = {
            "escenario":          "2 sensores/tipo, 5 s",
            "eventos_enviados":   sent_events,
            "registros_en_bd":    stored,
            "tasa_por_minuto":    round(rate, 2),
            "duracion_medicion_s":self.MEASURE_WINDOW_S,
        }
        print(f"\n    → Enviados: {sent_events}  |  Almacenados en BD: {stored}  "
              f"|  {rate:.1f} reg/min")

    # ══════════════════════════════════════════════════════════════
    # P03 & P04 — Latencia usuario→semáforo
    # ══════════════════════════════════════════════════════════════

    def _p03_latencia_1s(self, tr: TestResult):
        """
        Mide el tiempo desde que el operador envía 'FORZAR_VERDE' en PC3
        hasta que el semáforo refleja el cambio (consulta REQ/REP).
        Repite 10 veces; reporta media, mediana, p95 y máximo.
        """
        latencias = self._medir_latencias(n=10, interseccion="INT_A1")
        self._guardar_latencias(tr, latencias, "1 sensor/tipo, 10 s")

    def _p04_latencia_2s(self, tr: TestResult):
        """Igual que P03 pero bajo carga del escenario de 2 sensores/5 s."""
        # Primero lanzamos carga en background
        stop_flag = threading.Event()
        t = threading.Thread(
            target=self._background_load,
            args=(stop_flag, 2, self.config.sensor_interval_s2),
            daemon=True
        )
        t.start()
        time.sleep(5)   # deja que la carga se establezca

        latencias = self._medir_latencias(n=10, interseccion="INT_A2")
        stop_flag.set()
        t.join(timeout=5)
        self._guardar_latencias(tr, latencias, "2 sensores/tipo, 5 s")

    # ══════════════════════════════════════════════════════════════
    # P05 — Mono vs multihilo
    # ══════════════════════════════════════════════════════════════

    def _p05_mono_vs_multi(self, tr: TestResult):
        """
        Compara el throughput de la BD en el diseño monohilo (normal) y
        el diseño multihilo del BrokerZMQ.
        NOTA: requiere que el servidor exponga un endpoint para cambiar el modo.
        Si el endpoint no está disponible, la prueba se documenta como SKIP.
        """
        self._skip_if_no_zmq(tr)
        cfg = self.config

        resultados = {}
        for modo in ("MONOHILO", "MULTIHILO"):
            # Intentar cambiar el modo del broker
            switched = self._switch_broker_mode(modo)
            if not switched:
                tr.status = "SKIP"
                tr.error  = (f"El broker no soporta el endpoint CAMBIAR_MODO. "
                             "Ejecute prueba P05 manualmente con dos binarios diferentes.")
                return

            time.sleep(1)
            cnt_before = self._count_bd_records(cfg.host_pc3, cfg.port_monitor_req)
            self._run_sensor_scenario(n_sensors_per_type=2,
                                      interval_s=cfg.sensor_interval_s2,
                                      duration_s=30)
            time.sleep(2)
            cnt_after  = self._count_bd_records(cfg.host_pc3, cfg.port_monitor_req)
            resultados[modo] = cnt_after - cnt_before

        tr.status = "PASS"
        tr.data   = {
            "throughput_monohilo":  resultados.get("MONOHILO",  0),
            "throughput_multihilo": resultados.get("MULTIHILO", 0),
            "mejora_pct": (
                round((resultados["MULTIHILO"] - resultados["MONOHILO"])
                      / max(resultados["MONOHILO"], 1) * 100, 1)
                if "MONOHILO" in resultados and "MULTIHILO" in resultados else 0
            ),
        }
        print(f"\n    → Monohilo: {resultados.get('MONOHILO')} reg  |  "
              f"Multihilo: {resultados.get('MULTIHILO')} reg")

    # ══════════════════════════════════════════════════════════════
    # P06 — Throughput del broker 30 s
    # ══════════════════════════════════════════════════════════════

    def _p06_broker_carga(self, tr: TestResult):
        """
        Mide cuántos mensajes por segundo puede retransmitir el broker bajo
        carga sostenida de 6 sensores durante 30 s.
        """
        self._skip_if_no_zmq(tr)
        DURATION = 30
        ctx = self._zmq_ctx()

        received: list = []
        lock = threading.Lock()
        stop_ev = threading.Event()

        # Hilo receptor
        def _receiver():
            sub = self._sub_socket(self.config.host_pc1,
                                   self.config.port_broker_pub, topic="")
            sub.setsockopt(zmq.RCVTIMEO, 200)
            while not stop_ev.is_set():
                try:
                    sub.recv_string()
                    with lock:
                        received.append(time.perf_counter())
                except zmq.Again:
                    pass
            sub.close()

        recv_thread = threading.Thread(target=_receiver, daemon=True)
        recv_thread.start()

        sent = self._run_sensor_scenario(
            n_sensors_per_type=2,
            interval_s=0.5,     # alta frecuencia para estresar el broker
            duration_s=DURATION,
        )
        stop_ev.set()
        recv_thread.join(timeout=3)

        total_recv = len(received)
        rate       = total_recv / DURATION

        tr.status = "PASS"
        tr.data   = {
            "enviados":          sent,
            "recibidos_por_sub": total_recv,
            "perdidos":          sent - total_recv,
            "tasa_msg_s":        round(rate, 2),
            "duracion_s":        DURATION,
        }
        print(f"\n    → Enviados: {sent}  |  Recibidos: {total_recv}  "
              f"|  {rate:.1f} msg/s")

    # ══════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════

    def _run_sensor_scenario(self, n_sensors_per_type: int,
                             interval_s: float, duration_s: float) -> int:
        """
        Lanza hilos que simulan sensores publicando al broker.
        Devuelve el número total de eventos enviados.
        """
        counter   = [0]
        lock      = threading.Lock()
        stop_flag = threading.Event()
        threads   = []

        sensor_types = ["camara", "espira_inductiva", "gps"]
        rows = list(self.config.grid_rows)

        for stype in sensor_types:
            for idx in range(n_sensors_per_type):
                row = rows[idx % len(rows)]
                col = (idx % self.config.grid_cols) + 1
                t = threading.Thread(
                    target=self._sensor_worker,
                    args=(stype, row, col, interval_s, stop_flag, counter, lock),
                    daemon=True,
                )
                threads.append(t)
                t.start()

        time.sleep(duration_s)
        stop_flag.set()
        for t in threads:
            t.join(timeout=interval_s + 2)

        return counter[0]

    def _sensor_worker(self, stype: str, row: str, col: int,
                       interval_s: float, stop_flag: threading.Event,
                       counter: list, lock: threading.Lock):
        """Hilo que simula un sensor publicando al broker (PUB)."""
        import random
        if not ZMQ_AVAILABLE:
            return
        try:
            pub = self._pub_socket(self.config.port_broker_sub)
            time.sleep(0.2)
            while not stop_flag.is_set():
                evento = self._make_event(stype, row, col)
                topic  = stype
                pub.send_string(f"{topic} {json.dumps(evento)}")
                with lock:
                    counter[0] += 1
                time.sleep(interval_s)
            pub.close()
        except Exception:
            pass

    def _make_event(self, stype: str, row: str, col: int) -> dict:
        import random
        if stype == "camara":
            return {
                "sensor_id":          self.config.sensor_id(stype, row, col),
                "tipo_sensor":        "camara",
                "interseccion":       self.config.intersection(row, col),
                "volumen":            random.randint(0, 30),
                "velocidad_promedio": random.randint(5, 50),
                "timestamp":          _ts(),
            }
        elif stype == "espira_inductiva":
            return {
                "sensor_id":          self.config.sensor_id(stype, row, col),
                "tipo_sensor":        "espira_inductiva",
                "interseccion":       self.config.intersection(row, col),
                "vehiculos_contados": random.randint(0, 25),
                "intervalo_segundos": 30,
                "timestamp_inicio":   _ts(),
                "timestamp_fin":      _ts(),
            }
        else:
            vp    = random.randint(5, 55)
            nivel = "ALTA" if vp < 10 else ("NORMAL" if vp <= 39 else "BAJA")
            return {
                "sensor_id":          self.config.sensor_id(stype, row, col),
                "nivel_congestion":   nivel,
                "velocidad_promedio": vp,
                "timestamp":          _ts(),
            }

    def _medir_latencias(self, n: int, interseccion: str) -> List[float]:
        """
        Envía n comandos FORZAR_VERDE y mide el tiempo hasta que el estado
        del semáforo refleja el cambio. Devuelve lista de latencias en ms.
        """
        latencias = []
        for _ in range(n):
            t0 = time.perf_counter()
            sock = None
            try:
                sock = self._req_socket(self.config.host_pc3, self.config.port_monitor_req)
                cmd = {"accion": "FORZAR_VERDE", "interseccion": interseccion,
                       "motivo": "prueba_latencia", "timestamp": _ts()}
                self._send_req(sock, cmd)
            finally:
                self._close(sock)

            # Poll hasta detectar cambio (máx timeout_s)
            changed = False
            for _ in range(self.config.timeout * 10):
                time.sleep(0.1)
                estado = self._poll_estado(interseccion)
                if estado == "VERDE":
                    latencias.append((time.perf_counter() - t0) * 1000)
                    changed = True
                    break
            if not changed:
                latencias.append(self.config.timeout * 1000.0)  # timeout como latencia máx

            # Reset a ROJO antes de siguiente iteración
            self._reset_semaforo(interseccion)
            time.sleep(0.5)
        return latencias

    def _guardar_latencias(self, tr: TestResult, latencias: List[float], escenario: str):
        if not latencias:
            tr.status = "FAIL"
            tr.error  = "No se obtuvieron medidas de latencia"
            return
        tr.status = "PASS"
        tr.data   = {
            "escenario":     escenario,
            "n_medidas":     len(latencias),
            "media_ms":      round(statistics.mean(latencias), 2),
            "mediana_ms":    round(statistics.median(latencias), 2),
            "p95_ms":        round(sorted(latencias)[int(len(latencias) * 0.95)], 2),
            "max_ms":        round(max(latencias), 2),
            "min_ms":        round(min(latencias), 2),
            "latencias_ms":  [round(l, 2) for l in latencias],
        }
        print(f"\n    → media={tr.data['media_ms']}ms  "
              f"mediana={tr.data['mediana_ms']}ms  "
              f"p95={tr.data['p95_ms']}ms  "
              f"max={tr.data['max_ms']}ms")

    def _count_bd_records(self, host: str, port: int) -> int:
        if not ZMQ_AVAILABLE:
            return 0
        sock = None
        try:
            sock = self._req_socket(host, port)
            resp = self._send_req(sock, {"accion": "CONTAR_REGISTROS", "timestamp": _ts()})
            if resp:
                return resp.get("total", resp.get("count", 0))
            return 0
        finally:
            self._close(sock)

    def _poll_estado(self, interseccion: str) -> str:
        if not ZMQ_AVAILABLE:
            return "DESCONOCIDO"
        sock = None
        try:
            sock = self._req_socket(self.config.host_pc3, self.config.port_monitor_req)
            resp = self._send_req(sock, {"accion": "CONSULTA_INTERSECCION",
                                         "interseccion": interseccion,
                                         "timestamp": _ts()})
            return resp.get("estado_semaforo", "DESCONOCIDO") if resp else "TIMEOUT"
        finally:
            self._close(sock)

    def _reset_semaforo(self, interseccion: str):
        if not ZMQ_AVAILABLE:
            return
        sock = None
        try:
            sock = self._push_socket(self.config.host_pc2, self.config.port_traffic_ctrl)
            sock.send_json({"tipo": "CAMBIO_LUZ", "interseccion": interseccion,
                            "nuevo_estado": "ROJO", "timestamp": _ts()})
        finally:
            self._close(sock)

    def _switch_broker_mode(self, mode: str) -> bool:
        """Intenta cambiar el modo del broker vía REQ/REP. Devuelve False si no está implementado."""
        if not ZMQ_AVAILABLE:
            return False
        sock = None
        try:
            sock = self._req_socket(self.config.host_pc1, self.config.port_broker_sub + 100)
            resp = self._send_req(sock, {"accion": "CAMBIAR_MODO", "modo": mode})
            return resp is not None and resp.get("estado") in ("OK", "ACEPTADO")
        except Exception:
            return False
        finally:
            self._close(sock)

    def _background_load(self, stop_flag: threading.Event,
                         n_per_type: int, interval_s: float):
        counter = [0]
        lock    = threading.Lock()
        self._run_sensor_scenario.__doc__  # just for ref
        # Re-usa el worker directamente
        sub_flag = threading.Event()
        threads  = []
        for stype in ["camara", "espira_inductiva", "gps"]:
            for i in range(n_per_type):
                t = threading.Thread(
                    target=self._sensor_worker,
                    args=(stype, "A", i + 1, interval_s, stop_flag, counter, lock),
                    daemon=True,
                )
                threads.append(t)
                t.start()
        stop_flag.wait()
        for t in threads:
            t.join(timeout=interval_s + 2)
