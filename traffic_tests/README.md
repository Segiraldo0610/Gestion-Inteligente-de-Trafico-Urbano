# Batería de Pruebas — Gestión Inteligente de Tráfico Urbano
**ISD 2026-30 | Segunda Entrega**

---

## Estructura del proyecto

```
traffic_tests/
├── run_tests.py              ← Punto de entrada principal
├── README.md
├── tests/
│   ├── suite_funcional.py    ← F01-F17: pruebas funcionales
│   ├── suite_rendimiento.py  ← P01-P06: Tabla 1 (throughput + latencia)
│   └── suite_fallos.py       ← FA01-FA07: tolerancia a fallas
└── utils/
    ├── config.py             ← Parámetros centralizados (hosts, puertos, reglas)
    ├── base_test.py          ← Clase base con helpers ZMQ
    └── reporter.py           ← Generador de reportes HTML y JSON
```

---

## Instalación

```bash
pip install pyzmq
```

---

## Uso

### Ejecutar todo contra localhost (todos en el mismo PC)
```bash
python run_tests.py
```

### Ejecutar contra 3 máquinas reales
```bash
python run_tests.py \
  --host-pc1 192.168.1.10 \
  --host-pc2 192.168.1.11 \
  --host-pc3 192.168.1.12 \
  --suite all \
  --report both
```

### Solo pruebas funcionales
```bash
python run_tests.py --suite functional
```

### Solo pruebas de rendimiento (Tabla 1)
```bash
python run_tests.py --suite performance --report html
```

### Solo pruebas de tolerancia a fallas
```bash
python run_tests.py --suite fault
```

---

## Opciones completas

| Argumento        | Valores                          | Default     |
|------------------|----------------------------------|-------------|
| `--host-pc1`     | IP o hostname                    | localhost   |
| `--host-pc2`     | IP o hostname                    | localhost   |
| `--host-pc3`     | IP o hostname                    | localhost   |
| `--suite`        | `all`, `functional`, `performance`, `fault` | all |
| `--report`       | `html`, `json`, `both`           | both        |
| `--output-dir`   | ruta al directorio               | reports/    |
| `--timeout`      | segundos (int)                   | 10          |

---

## Qué prueba cada suite

### Suite Funcional (F01–F17)
| ID   | Prueba |
|------|--------|
| F01  | Sensor cámara genera evento válido (esquema JSON) |
| F02  | Sensor espira inductiva genera evento válido |
| F03  | Sensor GPS genera evento válido + coherencia velocidad/nivel |
| F04  | Broker PUB/SUB reenvía eventos de PC1 a PC2 |
| F05  | Analítica clasifica tráfico como NORMAL (Q<5, Vp>35, D<20) |
| F06  | Analítica detecta CONGESTIÓN |
| F07  | Analítica activa OLA VERDE por indicación directa (ambulancia) |
| F08  | Control semáforo ROJO → VERDE |
| F09  | Control semáforo VERDE → ROJO |
| F10  | Semáforo permanece verde ≥ 15 s en condición NORMAL |
| F11  | Monitoreo responde consulta de estado actual |
| F12  | Monitoreo devuelve historial por rango de tiempo (hora pico) |
| F13  | Consulta puntual de intersección (INT_C5) |
| F14  | Forzar verde desde PC3 (paso ambulancia) |
| F15  | BD principal (PC3) almacena eventos |
| F16  | BD réplica (PC2) almacena eventos asíncronamente |
| F17  | Consistencia entre BD principal y réplica (diff ≤ 5) |

### Suite de Rendimiento (P01–P06) — Tabla 1
| ID   | Prueba |
|------|--------|
| P01  | Throughput: 1 sensor/tipo, 10 s → registros en BD en 2 min |
| P02  | Throughput: 2 sensores/tipo, 5 s → registros en BD en 2 min |
| P03  | Latencia usuario→semáforo (escenario 1 sensor) |
| P04  | Latencia usuario→semáforo (escenario 2 sensores, bajo carga) |
| P05  | Comparación diseño monohilo vs multihilo del Broker |
| P06  | Throughput broker bajo carga sostenida (30 s) |

### Suite de Tolerancia a Fallas (FA01–FA07)
| ID   | Prueba |
|------|--------|
| FA01 | Health check detecta PC3 activo (PING/PONG) |
| FA02 | BD réplica está actualizada antes de la falla (diff ≤ 5) |
| FA03 | Failover transparente a réplica al desconectar PC3 |
| FA04 | Sistema opera sin interrupción durante la falla |
| FA05 | Semáforos siguen funcionando sin PC3 |
| FA06 | Monitoreo detecta y reporta la falla de PC3 |
| FA07 | Reconexión automática cuando PC3 vuelve |

---

## Configuración de puertos

Editar `utils/config.py` para que coincida con tu implementación:

```python
port_broker_pub:   5555   # Broker → PC2 (PUB)
port_broker_sub:   5556   # Sensores → Broker (SUB)
port_traffic_ctrl: 5557   # Analítica → Control semáforos (PUSH)
port_db_replica:   5558   # Analítica → BD réplica (PUSH)
port_monitor_req:  5559   # PC3 REQ/REP (usuario ↔ monitoreo)
port_db_main:      5560   # Analítica → BD principal (PUSH)
```

---

## Convenciones de respuesta REQ/REP

El servidor debe responder JSON con al menos:
```json
{ "estado": "OK" }           // para comandos
{ "estado": "PONG" }         // para PING
{ "total": 142 }             // para CONTAR_REGISTROS
{ "estado_semaforo": "VERDE", "interseccion": "INT_C5" }  // para CONSULTA_INTERSECCION
{ "registros": [...] }       // para CONSULTA_HISTORICA
```

---

## Salida esperada

```
═════════════════════════════════════════════════════════════
  BATERÍA DE PRUEBAS — Gestión Inteligente de Tráfico Urbano
  PC1=192.168.1.10  PC2=192.168.1.11  PC3=192.168.1.12
  Inicio: 2026-05-21 14:30:00
═════════════════════════════════════════════════════════════

─────────────────────────────────────────────────────────────
  ▶  Suite: FUNCIONAL
─────────────────────────────────────────────────────────────
  ✔ [PASS]  F01 - Sensor cámara genera evento válido           12ms
  ✔ [PASS]  F02 - Sensor espira inductiva genera evento...     8ms
  ...
```

Los reportes HTML y JSON se guardan en `reports/`.
