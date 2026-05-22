"""
utils/config.py — Configuración centralizada de la batería de pruebas.
Ajusta los puertos según tu implementación real.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class TestConfig:
    # ── Hosts ────────────────────────────────────────────────────
    host_pc1: str = "localhost"   # Broker ZMQ + Sensores
    host_pc2: str = "localhost"   # Analítica + Semáforos + BD Réplica
    host_pc3: str = "localhost"   # Monitoreo/Consulta + BD Principal

    # ── Puertos (ajustar según implementación) ───────────────────
    # PC1
    port_broker_pub: int  = 5555   # Broker publica hacia PC2  (PUB)
    port_broker_sub: int  = 5556   # Broker recibe sensores     (SUB)

    # PC2
    port_analytics_sub: int  = 5555  # Analítica escucha broker  (SUB -> mismo que broker_pub)
    port_traffic_ctrl:  int  = 5557  # Control semáforos          (PUSH/PULL)
    port_db_replica:    int  = 5558  # BD réplica                 (PUSH/PULL)

    # PC3
    port_monitor_req:   int  = 5559  # Monitoreo REQ/REP (usuario → servidor)
    port_db_main:       int  = 5560  # BD principal PUSH/PULL

    # ── Ciudad ───────────────────────────────────────────────────
    grid_rows:    str = "ABCDE"   # Filas disponibles
    grid_cols:    int = 5         # Columnas 1-5

    # ── Parámetros de prueba ──────────────────────────────────────
    timeout:            int   = 10     # segundos por operación
    output_dir:         str   = "reports"
    sensor_interval_s:  float = 10.0  # escenario 1: 1 sensor c/10s
    sensor_interval_s2: float = 5.0   # escenario 2: 2 sensores c/5s

    # ── Reglas de congestión (deben coincidir con tu impl.) ───────
    # Tráfico normal: Q < 5 AND Vp > 35 AND D < 20
    rule_q_normal:  int = 5
    rule_vp_normal: int = 35
    rule_d_normal:  int = 20

    # ── Tiempos semáforo (seg) ────────────────────────────────────
    green_duration_normal:     int = 15
    green_duration_congestion: int = 30   # ejemplo; ajustar
    green_duration_priority:   int = 60   # ola verde ambulancia

    # ── Tipos de sensores ─────────────────────────────────────────
    sensor_types: tuple = ("camara", "espira_inductiva", "gps")

    def intersection(self, row: str, col: int) -> str:
        """Devuelve el ID de una intersección, p.ej. INT_C5"""
        return f"INT_{row.upper()}{col}"

    def sensor_id(self, stype: str, row: str, col: int) -> str:
        prefix = {"camara": "CAM", "espira_inductiva": "ESP", "gps": "GPS"}.get(stype, "SNS")
        return f"{prefix}-{row.upper()}{col}"
