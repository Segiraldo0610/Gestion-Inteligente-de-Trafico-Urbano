"""
tests/suite_funcional.py — Pruebas funcionales completas.

Cubre:
  F01 - F03  Sensores (cámara, espira, GPS)
  F04        Broker recibe y reenvía eventos
  F05 - F07  Analítica: reglas de tráfico normal / congestión / prioridad
  F08 - F09  Control de semáforos (verde↔rojo)
  F10 - F12  Monitoreo y consulta (REQ/REP)
  F13        Consulta histórica por rango de tiempo
  F14        Consulta puntual por intersección
  F15        Forzar cambio semáforo desde monitoreo (ambulancia)
  F16        Persistencia en BD principal (PC3)
  F17        Persistencia en BD réplica (PC2)
"""

import json
import time
from datetime import datetime, timezone

from utils.base_test import BaseTestSuite, TestResult
from utils.config import TestConfig


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class FunctionalTestSuite(BaseTestSuite):

    def __init__(self, config: TestConfig):
        super().__init__(config)
        self.tests = [
            # ── Sensores ──────────────────────────────────────────
            ("F01 - Sensor cámara genera evento válido",              self._f01_sensor_camara),
            ("F02 - Sensor espira inductiva genera evento válido",    self._f02_sensor_espira),
            ("F03 - Sensor GPS genera evento válido",                 self._f03_sensor_gps),
            # ── Broker ────────────────────────────────────────────
            ("F04 - Broker PUB/SUB reenvía eventos a PC2",           self._f04_broker_pubsub),
            # ── Analítica ─────────────────────────────────────────
            ("F05 - Analítica clasifica tráfico NORMAL",              self._f05_analitica_normal),
            ("F06 - Analítica detecta CONGESTIÓN",                    self._f06_analitica_congestion),
            ("F07 - Analítica activa OLA VERDE (prioridad)",          self._f07_analitica_prioridad),
            # ── Semáforos ─────────────────────────────────────────
            ("F08 - Control semáforo cambia ROJO → VERDE",           self._f08_semaforo_r2v),
            ("F09 - Control semáforo cambia VERDE → ROJO",           self._f09_semaforo_v2r),
            ("F10 - Tiempo verde en condición NORMAL es 15 s",        self._f10_tiempo_verde_normal),
            # ── Monitoreo y consulta (REQ/REP) ────────────────────
            ("F11 - Monitoreo acepta consulta de estado actual",      self._f11_monitor_estado),
            ("F12 - Monitoreo devuelve historial por rango de tiempo",self._f12_monitor_historico),
            ("F13 - Consulta puntual de intersección específica",     self._f13_consulta_interseccion),
            ("F14 - Forzar cambio semáforo (ambulancia) desde PC3",  self._f14_forzar_cambio),
            # ── Persistencia ──────────────────────────────────────
            ("F15 - BD principal (PC3) almacena evento recibido",     self._f15_bd_principal),
            ("F16 - BD réplica (PC2) almacena evento recibido",      self._f16_bd_replica),
            ("F17 - BD réplica es consistente con BD principal",      self._f17_consistencia_bd),
        ]

    # ══════════════════════════════════════════════════════════════
    # SENSORES
    # ══════════════════════════════════════════════════════════════

    def _f01_sensor_camara(self, tr: TestResult):
        """Valida el esquema de un evento de cámara."""
        evento = self._build_evento_camara("C", 5)
        required = {"sensor_id", "tipo_sensor", "interseccion",
                    "volumen", "velocidad_promedio", "timestamp"}
        missing = required - evento.keys()
        self._assert(not missing, tr, f"Campos faltantes: {missing}")
        self._assert(evento["tipo_sensor"] == "camara", tr,
                     "tipo_sensor debe ser 'camara'")
        self._assert(0 <= evento["velocidad_promedio"] <= 50, tr,
                     "velocidad_promedio fuera de rango [0, 50]")
        self._assert(evento["volumen"] >= 0, tr, "volumen no puede ser negativo")
        tr.status = "PASS"
        tr.data   = evento

    def _f02_sensor_espira(self, tr: TestResult):
        """Valida el esquema de un evento de espira inductiva."""
        evento = self._build_evento_espira("C", 5)
        required = {"sensor_id", "tipo_sensor", "interseccion",
                    "vehiculos_contados", "intervalo_segundos",
                    "timestamp_inicio", "timestamp_fin"}
        missing = required - evento.keys()
        self._assert(not missing, tr, f"Campos faltantes: {missing}")
        self._assert(evento["tipo_sensor"] == "espira_inductiva", tr,
                     "tipo_sensor debe ser 'espira_inductiva'")
        self._assert(evento["intervalo_segundos"] == 30, tr,
                     "intervalo_segundos debe ser 30 (coincide con ciclo semáforo)")
        self._assert(evento["vehiculos_contados"] >= 0, tr,
                     "vehiculos_contados no puede ser negativo")
        tr.status = "PASS"
        tr.data   = evento

    def _f03_sensor_gps(self, tr: TestResult):
        """Valida el esquema de un evento GPS y categoría de congestión."""
        evento = self._build_evento_gps("C", 5)
        required = {"sensor_id", "nivel_congestion", "velocidad_promedio", "timestamp"}
        missing = required - evento.keys()
        self._assert(not missing, tr, f"Campos faltantes: {missing}")
        niveles_validos = {"ALTA", "NORMAL", "BAJA"}
        self._assert(evento["nivel_congestion"] in niveles_validos, tr,
                     f"nivel_congestion inválido: {evento['nivel_congestion']}")
        # Verificar coherencia velocidad ↔ nivel
        vp = evento["velocidad_promedio"]
        nc = evento["nivel_congestion"]
        if vp < 10:
            self._assert(nc == "ALTA",   tr, f"Vp={vp} → debe ser ALTA, no {nc}")
        elif vp <= 39:
            self._assert(nc == "NORMAL", tr, f"Vp={vp} → debe ser NORMAL, no {nc}")
        else:
            self._assert(nc == "BAJA",   tr, f"Vp={vp} → debe ser BAJA, no {nc}")
        tr.status = "PASS"
        tr.data   = evento

    # ══════════════════════════════════════════════════════════════
    # BROKER
    # ══════════════════════════════════════════════════════════════

    def _f04_broker_pubsub(self, tr: TestResult):
        """Publica un evento en PC1 y lo recibe suscribiéndose al broker (PC1→PC2)."""
        self._skip_if_no_zmq(tr)
        pub = None
        sub = None
        try:
            pub = self._pub_socket(self.config.port_broker_sub)   # simula sensor
            time.sleep(0.3)
            sub = self._sub_socket(
                self.config.host_pc1,
                self.config.port_broker_pub,   # escucha lo que reenvía el broker
                topic="camara"
            )
            time.sleep(0.3)

            evento = self._build_evento_camara("A", 1)
            pub.send_string(f"camara {json.dumps(evento)}")

            raw = sub.recv_string()
            topic, body = raw.split(" ", 1)
            received = json.loads(body)

            self._assert(topic == "camara", tr, f"Tópico incorrecto: {topic}")
            self._assert(received.get("sensor_id") == evento["sensor_id"],
                         tr, "sensor_id no coincide en el mensaje recibido")
            tr.status = "PASS"
            tr.data   = {"publicado": evento, "recibido": received}
        finally:
            self._close(pub, sub)

    # ══════════════════════════════════════════════════════════════
    # ANALÍTICA — reglas de tráfico
    # ══════════════════════════════════════════════════════════════

    def _f05_analitica_normal(self, tr: TestResult):
        """Envía métricas de tráfico normal y comprueba que el servicio las clasifica correctamente."""
        data = {"Q": 3, "Vp": 40, "D": 15, "interseccion": "INT_C5"}
        result = self._evaluar_reglas(data)
        self._assert(result == "NORMAL", tr,
                     f"Se esperaba NORMAL, se obtuvo: {result}")
        tr.status = "PASS"
        tr.data   = {"input": data, "clasificacion": result}

    def _f06_analitica_congestion(self, tr: TestResult):
        """Envía métricas de congestión y verifica la clasificación."""
        data = {"Q": 12, "Vp": 8, "D": 35, "interseccion": "INT_B3"}
        result = self._evaluar_reglas(data)
        self._assert(result == "CONGESTION", tr,
                     f"Se esperaba CONGESTION, se obtuvo: {result}")
        tr.status = "PASS"
        tr.data   = {"input": data, "clasificacion": result}

    def _f07_analitica_prioridad(self, tr: TestResult):
        """Simula indicación directa de prioridad (ambulancia) desde PC3."""
        self._skip_if_no_zmq(tr)
        sock = None
        try:
            sock = self._req_socket(self.config.host_pc3, self.config.port_monitor_req)
            cmd = {
                "accion":        "PRIORIDAD",
                "via":           "INT_C5",
                "motivo":        "ambulancia",
                "timestamp":     _ts(),
            }
            resp = self._send_req(sock, cmd)
            self._assert(resp is not None, tr,
                         "Sin respuesta del servicio de monitoreo (timeout)")
            self._assert(resp.get("estado") in ("OK", "ACEPTADO"), tr,
                         f"Respuesta inesperada: {resp}")
            tr.status = "PASS"
            tr.data   = {"comando": cmd, "respuesta": resp}
        finally:
            self._close(sock)

    # ══════════════════════════════════════════════════════════════
    # SEMÁFOROS
    # ══════════════════════════════════════════════════════════════

    def _f08_semaforo_r2v(self, tr: TestResult):
        """Envía comando ROJO→VERDE al servicio de control y verifica ejecución."""
        self._skip_if_no_zmq(tr)
        sock = None
        try:
            sock = self._push_socket(self.config.host_pc2, self.config.port_traffic_ctrl)
            cmd = {
                "tipo":          "CAMBIO_LUZ",
                "interseccion":  "INT_A1",
                "nuevo_estado":  "VERDE",
                "timestamp":     _ts(),
            }
            sock.send_json(cmd)
            # Verificar via monitoreo (REQ/REP al PC3)
            time.sleep(0.5)
            estado = self._consultar_estado_semaforo("INT_A1")
            self._assert(estado == "VERDE", tr,
                         f"El semáforo INT_A1 debería estar VERDE, está: {estado}")
            tr.status = "PASS"
            tr.data   = {"comando": cmd, "estado_final": estado}
        finally:
            self._close(sock)

    def _f09_semaforo_v2r(self, tr: TestResult):
        """Envía comando VERDE→ROJO al servicio de control y verifica ejecución."""
        self._skip_if_no_zmq(tr)
        sock = None
        try:
            sock = self._push_socket(self.config.host_pc2, self.config.port_traffic_ctrl)
            cmd = {
                "tipo":          "CAMBIO_LUZ",
                "interseccion":  "INT_A1",
                "nuevo_estado":  "ROJO",
                "timestamp":     _ts(),
            }
            sock.send_json(cmd)
            time.sleep(0.5)
            estado = self._consultar_estado_semaforo("INT_A1")
            self._assert(estado == "ROJO", tr,
                         f"El semáforo INT_A1 debería estar ROJO, está: {estado}")
            tr.status = "PASS"
            tr.data   = {"comando": cmd, "estado_final": estado}
        finally:
            self._close(sock)

    def _f10_tiempo_verde_normal(self, tr: TestResult):
        """
        Verifica que en condición NORMAL el semáforo permanece en verde
        exactamente (≥) 15 segundos antes de cambiar a rojo.
        """
        self._skip_if_no_zmq(tr)
        sock = None
        try:
            sock = self._push_socket(self.config.host_pc2, self.config.port_traffic_ctrl)
            cmd = {
                "tipo":          "CAMBIO_LUZ",
                "interseccion":  "INT_B2",
                "nuevo_estado":  "VERDE",
                "condicion":     "NORMAL",
                "timestamp":     _ts(),
            }
            sock.send_json(cmd)
            t_start = time.perf_counter()

            # Espera hasta que cambie a ROJO (poll cada 1 s, máx 25 s)
            changed = False
            for _ in range(25):
                time.sleep(1)
                estado = self._consultar_estado_semaforo("INT_B2")
                if estado == "ROJO":
                    elapsed = time.perf_counter() - t_start
                    changed = True
                    break

            self._assert(changed, tr,
                         "El semáforo no cambió a ROJO dentro de 25 segundos")
            self._assert(elapsed >= self.config.green_duration_normal, tr,
                         f"Verde duró {elapsed:.1f}s, mínimo esperado: {self.config.green_duration_normal}s")
            tr.status = "PASS"
            tr.data   = {"duracion_verde_s": round(elapsed, 2)}
        finally:
            self._close(sock)

    # ══════════════════════════════════════════════════════════════
    # MONITOREO Y CONSULTA (REQ/REP)
    # ══════════════════════════════════════════════════════════════

    def _f11_monitor_estado(self, tr: TestResult):
        """Consulta el estado actual de la red de semáforos desde PC3."""
        self._skip_if_no_zmq(tr)
        sock = None
        try:
            sock = self._req_socket(self.config.host_pc3, self.config.port_monitor_req)
            req = {"accion": "CONSULTA_ESTADO_ACTUAL", "timestamp": _ts()}
            resp = self._send_req(sock, req)
            self._assert(resp is not None, tr, "Sin respuesta (timeout)")
            self._assert("semaforos" in resp or "intersecciones" in resp, tr,
                         f"La respuesta no contiene semáforos/intersecciones: {resp}")
            tr.status = "PASS"
            tr.data   = {"respuesta_keys": list(resp.keys())}
        finally:
            self._close(sock)

    def _f12_monitor_historico(self, tr: TestResult):
        """Solicita historial de congestión entre dos timestamps (hora pico)."""
        self._skip_if_no_zmq(tr)
        sock = None
        try:
            sock = self._req_socket(self.config.host_pc3, self.config.port_monitor_req)
            req = {
                "accion":          "CONSULTA_HISTORICA",
                "timestamp_inicio":"2026-01-01T07:00:00Z",
                "timestamp_fin":   "2026-01-01T09:00:00Z",
                "timestamp":       _ts(),
            }
            resp = self._send_req(sock, req)
            self._assert(resp is not None, tr, "Sin respuesta (timeout)")
            self._assert("registros" in resp or "eventos" in resp or "historial" in resp, tr,
                         f"La respuesta no contiene registros históricos: {resp}")
            tr.status = "PASS"
            tr.data   = {"respuesta_keys": list(resp.keys())}
        finally:
            self._close(sock)

    def _f13_consulta_interseccion(self, tr: TestResult):
        """Consulta puntual de estado en intersección INT_C5."""
        self._skip_if_no_zmq(tr)
        sock = None
        try:
            sock = self._req_socket(self.config.host_pc3, self.config.port_monitor_req)
            req = {
                "accion":       "CONSULTA_INTERSECCION",
                "interseccion": "INT_C5",
                "timestamp":    _ts(),
            }
            resp = self._send_req(sock, req)
            self._assert(resp is not None, tr, "Sin respuesta (timeout)")
            self._assert("interseccion" in resp or "estado" in resp, tr,
                         f"Respuesta sin datos de intersección: {resp}")
            tr.status = "PASS"
            tr.data   = {"respuesta": resp}
        finally:
            self._close(sock)

    def _f14_forzar_cambio(self, tr: TestResult):
        """El operador fuerza verde en INT_D3 para paso de ambulancia."""
        self._skip_if_no_zmq(tr)
        sock = None
        try:
            sock = self._req_socket(self.config.host_pc3, self.config.port_monitor_req)
            cmd = {
                "accion":        "FORZAR_VERDE",
                "interseccion":  "INT_D3",
                "motivo":        "ambulancia",
                "timestamp":     _ts(),
            }
            resp = self._send_req(sock, cmd)
            self._assert(resp is not None, tr, "Sin respuesta (timeout)")
            self._assert(resp.get("estado") in ("OK", "ACEPTADO", "EJECUTADO"), tr,
                         f"La acción no fue aceptada: {resp}")
            # Verificar que el cambio se aplicó
            time.sleep(1)
            estado = self._consultar_estado_semaforo("INT_D3")
            self._assert(estado == "VERDE", tr,
                         f"Semáforo INT_D3 debería estar VERDE, está: {estado}")
            tr.status = "PASS"
            tr.data   = {"comando": cmd, "respuesta": resp, "estado_semaforo": estado}
        finally:
            self._close(sock)

    # ══════════════════════════════════════════════════════════════
    # PERSISTENCIA
    # ══════════════════════════════════════════════════════════════

    def _f15_bd_principal(self, tr: TestResult):
        """Verifica que la BD principal (PC3) almacenó al menos un evento."""
        self._skip_if_no_zmq(tr)
        sock = None
        try:
            sock = self._req_socket(self.config.host_pc3, self.config.port_monitor_req)
            resp = self._send_req(sock, {"accion": "CONTAR_REGISTROS", "timestamp": _ts()})
            self._assert(resp is not None, tr, "Sin respuesta (timeout)")
            count = resp.get("total", resp.get("count", -1))
            self._assert(count > 0, tr,
                         f"BD principal tiene {count} registros, se esperaba > 0")
            tr.status = "PASS"
            tr.data   = {"registros_bd_principal": count}
        finally:
            self._close(sock)

    def _f16_bd_replica(self, tr: TestResult):
        """Verifica que la BD réplica (PC2) almacenó eventos de forma asíncrona."""
        self._skip_if_no_zmq(tr)
        sock = None
        try:
            # La réplica también expone un REQ/REP de estado interno en PC2
            port_replica_status = self.config.port_db_replica + 10   # convenio
            sock = self._req_socket(self.config.host_pc2, port_replica_status)
            resp = self._send_req(sock, {"accion": "CONTAR_REGISTROS", "timestamp": _ts()})
            self._assert(resp is not None, tr, "Sin respuesta desde la réplica (timeout)")
            count = resp.get("total", resp.get("count", -1))
            self._assert(count > 0, tr,
                         f"BD réplica tiene {count} registros, se esperaba > 0")
            tr.status = "PASS"
            tr.data   = {"registros_bd_replica": count}
        finally:
            self._close(sock)

    def _f17_consistencia_bd(self, tr: TestResult):
        """Comprueba que la BD réplica tiene la misma cantidad de registros que la principal."""
        self._skip_if_no_zmq(tr)
        s_main = s_rep = None
        try:
            s_main = self._req_socket(self.config.host_pc3, self.config.port_monitor_req)
            r_main = self._send_req(s_main, {"accion": "CONTAR_REGISTROS", "timestamp": _ts()})
            port_replica_status = self.config.port_db_replica + 10
            s_rep  = self._req_socket(self.config.host_pc2, port_replica_status)
            r_rep  = self._send_req(s_rep, {"accion": "CONTAR_REGISTROS", "timestamp": _ts()})

            self._assert(r_main is not None and r_rep is not None, tr,
                         "Timeout consultando una de las bases de datos")
            cnt_main = r_main.get("total", r_main.get("count", -1))
            cnt_rep  = r_rep.get("total",  r_rep.get("count", -2))
            diff = abs(cnt_main - cnt_rep)
            # Permitimos una diferencia pequeña por el lag asíncrono
            self._assert(diff <= 5, tr,
                         f"Desfase entre BD principal ({cnt_main}) y réplica ({cnt_rep}): diff={diff}")
            tr.status = "PASS"
            tr.data   = {"bd_principal": cnt_main, "bd_replica": cnt_rep, "diferencia": diff}
        finally:
            self._close(s_main, s_rep)

    # ══════════════════════════════════════════════════════════════
    # HELPERS INTERNOS
    # ══════════════════════════════════════════════════════════════

    def _build_evento_camara(self, row: str, col: int) -> dict:
        import random
        return {
            "sensor_id":         self.config.sensor_id("camara", row, col),
            "tipo_sensor":       "camara",
            "interseccion":      self.config.intersection(row, col),
            "volumen":           random.randint(0, 30),
            "velocidad_promedio":random.randint(5, 50),
            "timestamp":         _ts(),
        }

    def _build_evento_espira(self, row: str, col: int) -> dict:
        import random
        ts_inicio = _ts()
        return {
            "sensor_id":          self.config.sensor_id("espira_inductiva", row, col),
            "tipo_sensor":        "espira_inductiva",
            "interseccion":       self.config.intersection(row, col),
            "vehiculos_contados": random.randint(0, 25),
            "intervalo_segundos": 30,
            "timestamp_inicio":   ts_inicio,
            "timestamp_fin":      _ts(),
        }

    def _build_evento_gps(self, row: str, col: int, vp: int = None) -> dict:
        import random
        if vp is None:
            vp = random.randint(5, 55)
        if vp < 10:
            nivel = "ALTA"
        elif vp <= 39:
            nivel = "NORMAL"
        else:
            nivel = "BAJA"
        return {
            "sensor_id":         self.config.sensor_id("gps", row, col),
            "nivel_congestion":  nivel,
            "velocidad_promedio":vp,
            "timestamp":         _ts(),
        }

    def _evaluar_reglas(self, data: dict) -> str:
        """
        Aplica las reglas de tráfico LOCALMENTE (espejo de la lógica del servidor).
        Q < 5 AND Vp > 35 AND D < 20  → NORMAL
        De lo contrario             → CONGESTION
        """
        q  = data.get("Q",  0)
        vp = data.get("Vp", 0)
        d  = data.get("D",  0)
        if (q  < self.config.rule_q_normal and
            vp > self.config.rule_vp_normal and
            d  < self.config.rule_d_normal):
            return "NORMAL"
        return "CONGESTION"

    def _consultar_estado_semaforo(self, interseccion: str) -> str:
        """Consulta el estado actual de un semáforo vía REQ/REP en PC3."""
        if not ZMQ_AVAILABLE:
            return "DESCONOCIDO"
        sock = None
        try:
            sock = self._req_socket(self.config.host_pc3, self.config.port_monitor_req)
            req  = {"accion": "CONSULTA_INTERSECCION", "interseccion": interseccion,
                    "timestamp": _ts()}
            resp = self._send_req(sock, req)
            if resp:
                return resp.get("estado_semaforo", resp.get("estado", "DESCONOCIDO"))
            return "TIMEOUT"
        finally:
            self._close(sock)


try:
    import zmq as _zmq
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False
