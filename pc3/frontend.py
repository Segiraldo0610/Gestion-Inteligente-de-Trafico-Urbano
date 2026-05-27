#!/usr/bin/env python3
"""
Frontend web (PC3).
Servidor HTTP.
Expone:
  GET /          → dashboard HTML
  GET /api/estado → JSON con estado de las 9 intersecciones
  GET /api/resumen → JSON con totales de la BD
  POST /api/priorizar  → fuerza VERDE en una intersección (control manual)
"""

import json
import os
import sqlite3
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# Añade la raíz del proyecto al path de búsqueda para poder importar los módulos comunes
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importaciones de utilidades comunes del sistema
from common.config_loader import load_config
from common.utils import generar_intersecciones_3x3, generar_timestamp_iso, log_componente

# Identificador de log y configuración de rutas para el acceso físico a SQLite
COMPONENTE = "frontend"
DB_NAME    = "pc3_principal.db"

# Resuelve la ruta absoluta del directorio del archivo actual para evitar fallos si se ejecuta desde otra carpeta
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, DB_NAME)

# Mecanismo de control concurrencia para proteger el puntero del archivo de la base de datos
_lock_db = threading.Lock()


# ---------------------------------------------------------------------------
# Capa de Acceso a Datos (Consultas a SQLite con Seguridad de Hilos)
# ---------------------------------------------------------------------------

def _conectar() -> sqlite3.Connection:
    """Establece una conexión física con la base de datos y mapea las filas como diccionarios (Row)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Permite acceder a las columnas por nombre en lugar de por índices numéricos
    return conn


def consultar_estado_intersecciones() -> list[dict]:
    """Recupera la última directiva aplicada y métricas clave de cada una de las 9 intersecciones."""
    intersecciones = generar_intersecciones_3x3() # Genera lista estática ['I1', 'I2', ..., 'I9']
    resultado = []

    # Bloquea el candado exclusivo; cualquier otra petición HTTP concurrente esperará en cola
    with _lock_db:
        conn = _conectar()
        cur  = conn.cursor()

        for inter in intersecciones:
            # QUERY 1: Extrae la última instrucción de semáforo enviada (Verde/Rojo, motivo, duración)
            cur.execute(
                """
                SELECT estado, motivo, duracion, timestamp
                FROM acciones_semaforo
                WHERE interseccion = ?
                ORDER BY id DESC LIMIT 1
                """,
                (inter,),
            )
            accion = cur.fetchone()

            # QUERY 2: Cuenta la cantidad histórica de telemetrías registradas en la intersección
            cur.execute(
                "SELECT COUNT(*) AS total FROM eventos WHERE interseccion = ?",
                (inter,),
            )
            total = cur.fetchone()["total"]

            # QUERY 3: Extrae el último evento en bruto para deducir la clasificación calculada por analítica
            cur.execute(
                """
                SELECT tipo_evento, datos_json, timestamp
                FROM eventos
                WHERE interseccion = ?
                ORDER BY id DESC LIMIT 1
                """,
                (inter,),
            )
            ultimo_evento = cur.fetchone()

            # Bloque de parseo seguro del campo de texto estructurado JSON interno
            clasificacion = "—"
            if ultimo_evento:
                try:
                    datos = json.loads(ultimo_evento["datos_json"])
                    clasificacion = datos.get("clasificacion", "—")
                except Exception:
                    pass # En caso de JSON corrupto, mantiene el carácter por defecto

            # Empaqueta y mapea los resultados procesados en una estructura limpia para la API web
            resultado.append({
                "interseccion": inter,
                "estado":       accion["estado"]    if accion else "SIN_DATOS",
                "motivo":       accion["motivo"]    if accion else "—",
                "duracion":     accion["duracion"]  if accion else 0,
                "timestamp":    accion["timestamp"] if accion else "—",
                "total_eventos": total,
                "clasificacion": clasificacion,
            })

        conn.close() # Libera el archivo físico de la base de datos
    return resultado


def consultar_resumen() -> dict:
    """Extrae contadores globales agregados para las tarjetas de estadísticas principales del Dashboard."""
    with _lock_db:
        conn = _conectar()
        cur  = conn.cursor()
        
        # Conteo acumulado de eventos de sensores
        cur.execute("SELECT COUNT(*) AS total FROM eventos")
        total_ev = cur.fetchone()["total"]
        
        # Conteo acumulado de comandos de semáforo emitidos
        cur.execute("SELECT COUNT(*) AS total FROM acciones_semaforo")
        total_ac = cur.fetchone()["total"]
        
        # Conteo histórico de aperturas de ondas verdes
        cur.execute("SELECT COUNT(*) AS total FROM acciones_semaforo WHERE estado='VERDE'")
        verdes = cur.fetchone()["total"]
        
        # Conteo analítico de mitigaciones por eventos de congestión vial detectados
        cur.execute(
            "SELECT COUNT(*) AS total FROM acciones_semaforo WHERE motivo LIKE '%congestion%'"
        )
        congestion = cur.fetchone()["total"]
        conn.close()
        
    return {
        "total_eventos":   total_ev,
        "total_acciones":  total_ac,
        "total_verdes":    verdes,
        "total_congestion": congestion,
        "timestamp":       generar_timestamp_iso(),
    }


def insertar_prioridad(interseccion: str) -> dict:
    """Fuerza la inserción de un registro VERDE manual que simula la anulación o control por sala de mandos."""
    ts = generar_timestamp_iso()
    with _lock_db:
        conn = _conectar()
        cur  = conn.cursor()
        # Inserta el comando de prioridad con duración extendida de 60 segundos
        cur.execute(
            """
            INSERT INTO acciones_semaforo (interseccion, estado, duracion, motivo, timestamp)
            VALUES (?, 'VERDE', 60, 'control_manual', ?)
            """,
            (interseccion, ts),
        )
        conn.commit() # Escribe los cambios de forma permanente en el disco
        conn.close()
    log_componente(COMPONENTE, f"Control manual VERDE aplicado en {interseccion}")
    return {"ok": True, "interseccion": interseccion, "estado": "VERDE", "timestamp": ts}


# ---------------------------------------------------------------------------
# HTML, Plantillas CSS y Lógica JavaScript del Dashboard Integrado
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Control de Tráfico Urbano</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=DM+Sans:wght@300;400;500&display=swap');

  :root {
    --bg:        #0a0c10;
    --surface:   #111318;
    --border:    #1e2330;
    --accent:    #00e5a0;
    --danger:    #ff4757;
    --warn:      #ffa502;
    --muted:     #4a5568;
    --text:      #e2e8f0;
    --text-dim:  #718096;
    --mono:      'Share Tech Mono', monospace;
    --sans:      'DM Sans', sans-serif;
    --radius:    6px;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
    min-height: 100vh;
  }

  /* Textura de líneas de escaneo estilo terminal retro */
  body::before {
    content: '';
    position: fixed; inset: 0;
    background: repeating-linear-gradient(
      0deg, transparent, transparent 2px,
      rgba(0,0,0,0.08) 2px, rgba(0,0,0,0.08) 4px
    );
    pointer-events: none;
    z-index: 9999;
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 28px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }

  .logo {
    font-family: var(--mono);
    font-size: 13px;
    color: var(--accent);
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .logo span { color: var(--text-dim); }

  .status-bar {
    display: flex;
    align-items: center;
    gap: 20px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-dim);
  }

  .dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 8px var(--accent);
    animation: pulse 2s ease-in-out infinite;
    display: inline-block;
    margin-right: 5px;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.4; }
  }

  main { padding: 24px 28px; }

  .stats {
    display: flex;
    gap: 12px;
    margin-bottom: 28px;
    flex-wrap: wrap;
  }

  .stat {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px 20px;
    flex: 1;
    min-width: 140px;
  }
  .stat-label {
    font-size: 10px;
    font-family: var(--mono);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 6px;
  }
  .stat-value {
    font-family: var(--mono);
    font-size: 28px;
    font-weight: 400;
    color: var(--accent);
  }

  .section-label {
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .section-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 28px;
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.3s;
  }

  .card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--muted);
    transition: background 0.4s;
  }

  .card.verde::before  { background: var(--accent); box-shadow: 0 0 10px var(--accent); }
  .card.rojo::before   { background: var(--danger); box-shadow: 0 0 10px var(--danger); }
  .card.warn::before   { background: var(--warn);   box-shadow: 0 0 10px var(--warn); }

  .card-id {
    font-family: var(--mono);
    font-size: 18px;
    font-weight: 400;
    color: var(--text);
    margin-bottom: 10px;
  }

  .badge {
    display: inline-block;
    font-family: var(--mono);
    font-size: 10px;
    font-weight: 400;
    letter-spacing: 0.08em;
    padding: 3px 8px;
    border-radius: 3px;
    text-transform: uppercase;
    margin-bottom: 10px;
  }
  .badge-verde  { background: rgba(0,229,160,0.12); color: var(--accent); border: 1px solid rgba(0,229,160,0.3); }
  .badge-rojo   { background: rgba(255,71,87,0.12);  color: var(--danger); border: 1px solid rgba(255,71,87,0.3); }
  .badge-sin    { background: rgba(74,85,104,0.3);   color: var(--muted);  border: 1px solid var(--border); }

  .card-meta {
    font-size: 11px;
    color: var(--text-dim);
    line-height: 1.7;
  }
  .card-meta strong { color: var(--text); font-weight: 500; }

  .btn-prior {
    margin-top: 12px;
    width: 100%;
    padding: 7px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text-dim);
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-prior:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(0,229,160,0.05);
  }
  .btn-prior:active { transform: scale(0.98); }

  .log-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
  }
  .log-panel pre {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-dim);
    line-height: 1.8;
    max-height: 180px;
    overflow-y: auto;
    white-space: pre-wrap;
  }
  .log-line-verde  { color: var(--accent); }
  .log-line-rojo   { color: var(--danger); }
  .log-line-warn   { color: var(--warn); }
  .log-line-manual { color: #a78bfa; }

  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

  #clock { font-family: var(--mono); font-size: 11px; color: var(--text-dim); }
</style>
</head>
<body>

<header>
  <div class="logo">
    SITU<span>/</span>PC3
    <span style="margin-left:14px;font-size:11px;color:var(--text-dim)">
      Sistema Inteligente de Tráfico Urbano
    </span>
  </div>
  <div class="status-bar">
    <span><span class="dot"></span>EN LÍNEA</span>
    <span id="clock">--:--:--</span>
    <span id="last-update" style="color:var(--muted)">actualizando...</span>
  </div>
</header>

<main>
  <div class="stats" id="stats">
    <div class="stat"><div class="stat-label">Total eventos</div><div class="stat-value" id="s-eventos">—</div></div>
    <div class="stat"><div class="stat-label">Total acciones</div><div class="stat-value" id="s-acciones">—</div></div>
    <div class="stat"><div class="stat-label">Señales VERDE</div><div class="stat-value" id="s-verdes" style="color:#00e5a0">—</div></div>
    <div class="stat"><div class="stat-label">Por congestión</div><div class="stat-value" id="s-cong" style="color:#ffa502">—</div></div>
  </div>

  <div class="section-label">Intersecciones — cuadrícula 3×3</div>
  <div class="grid" id="grid"></div>

  <div class="section-label">Actividad reciente</div>
  <div class="log-panel">
    <pre id="log">Esperando datos...</pre>
  </div>
</main>

<script>
const MAX_LOG = 40;
let logLines = [];

// Reloj en tiempo real
function tick() {
  const now = new Date();
  document.getElementById('clock').textContent = now.toTimeString().slice(0,8);
}
setInterval(tick, 1000); tick();

// Agrega líneas de registro al visor interno del navegador
function addLog(msg, cls='') {
  const ts = new Date().toTimeString().slice(0,8);
  logLines.unshift(`<span class="${cls}">[${ts}] ${msg}</span>`);
  if (logLines.length > MAX_LOG) logLines.pop();
  document.getElementById('log').innerHTML = logLines.join('\n');
}

function badgeClass(estado) {
  if (estado === 'VERDE')    return 'badge-verde';
  if (estado === 'ROJO')     return 'badge-rojo';
  return 'badge-sin';
}
function cardClass(estado) {
  if (estado === 'VERDE')    return 'verde';
  if (estado === 'ROJO')     return 'rojo';
  if (estado === 'SIN_DATOS') return '';
  return 'warn';
}

// Emite la petición POST asíncrona para forzar la prioridad vial
async function priorizar(inter) {
  try {
    const r = await fetch('/api/priorizar', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({interseccion: inter})
    });
    const d = await r.json();
    addLog(`Control manual VERDE → ${inter}`, 'log-line-manual');
  } catch(e) {
    addLog(`Error al priorizar ${inter}`, 'log-line-rojo');
  }
}

let prevEstados = {};

// Orquestador del Polling asíncronizado (AJAX)
async function fetchEstado() {
  try {
    const [eRes, rRes] = await Promise.all([
      fetch('/api/estado'),
      fetch('/api/resumen')
    ]);
    const estado  = await eRes.json();
    const resumen = await rRes.json();

    // Actualiza los bloques de datos globales
    document.getElementById('s-eventos').textContent  = resumen.total_eventos.toLocaleString();
    document.getElementById('s-acciones').textContent = resumen.total_acciones.toLocaleString();
    document.getElementById('s-verdes').textContent   = resumen.total_verdes.toLocaleString();
    document.getElementById('s-cong').textContent     = resumen.total_congestion.toLocaleString();

    // Renderiza la matriz visual dinámica de las 9 esquinas urbanas
    const grid = document.getElementById('grid');
    grid.innerHTML = '';
    estado.forEach(d => {
      const cc = cardClass(d.estado);
      const bc = badgeClass(d.estado);
      const ts = d.timestamp !== '—' ? d.timestamp.replace('T',' ').replace('Z','') : '—';

      const card = document.createElement('div');
      card.className = `card ${cc}`;
      card.innerHTML = `
        <div class="card-id">${d.interseccion}</div>
        <span class="badge ${bc}">${d.estado}</span>
        <div class="card-meta">
          <strong>Motivo:</strong> ${d.motivo}<br>
          <strong>Clasificación:</strong> ${d.clasificacion}<br>
          <strong>Duración:</strong> ${d.duracion}s<br>
          <strong>Eventos:</strong> ${d.total_eventos.toLocaleString()}<br>
          <strong>Actualizado:</strong> ${ts}
        </div>
        <button class="btn-prior" onclick="priorizar('${d.interseccion}')">
          ▲ forzar verde
        </button>
      `;
      grid.appendChild(card);

      // Dispara una línea de log únicamente ante transiciones netas de estado
      const prev = prevEstados[d.interseccion];
      if (prev && prev !== d.estado) {
        const cls = d.estado === 'VERDE' ? 'log-line-verde'
                  : d.estado === 'ROJO'  ? 'log-line-rojo' : 'log-line-warn';
        addLog(`${d.interseccion}: ${prev} → ${d.estado}  [${d.motivo}]`, cls);
      }
      prevEstados[d.interseccion] = d.estado;
    });

    document.getElementById('last-update').textContent =
      'actualizado ' + new Date().toTimeString().slice(0,8);

  } catch(e) {
    addLog('Error de conexión con el servidor', 'log-line-rojo');
  }
}

// Configuración de sondeo por intervalos (Polling) cada 3 segundos
fetchEstado();
setInterval(fetchEstado, 3000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Controlador de Peticiones HTTP (Manejador de la Librería Estándar)
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Silencia la impresión nativa de cada request (como "GET / HTTP/1.1 200") en consola 
        # para evitar saturar la salida y mantener legibles los logs del sistema distribuido
        pass

    def _send(self, code: int, content_type: str, body: str | bytes) -> None:
        """Centraliza la lógica para armar e inyectar cabeceras y payloads HTTP de respuesta."""
        if isinstance(body, str):
            body = body.encode("utf-8") # Convierte strings a bytes codificados en UTF-8
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*") # Habilita mecanismos CORS de desarrollo abierto
        self.end_headers() # Inserta el salto de línea obligatorio del protocolo HTTP (\r\n)
        self.wfile.write(body) # Transmite el bloque de datos a través del canal de socket

    def _send_json(self, code: int, data) -> None:
        """Serializa objetos nativos o listas de Python a cadenas de texto JSON antes del envío."""
        self._send(code, "application/json", json.dumps(data, ensure_ascii=False))

    def do_GET(self):
        """Atiende todas las llamadas entrantes bajo la tipología del método GET."""
        parsed = urlparse(self.path)
        path   = parsed.path

        # Enrutador (Router) básico basado en condicionales lógicos
        if path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", HTML)

        elif path == "/api/estado":
            try:
                data = consultar_estado_intersecciones()
                self._send_json(200, data)
            except Exception as exc:
                log_componente(COMPONENTE, f"Error /api/estado: {exc}", nivel="ERROR")
                self._send_json(500, {"error": str(exc)})

        elif path == "/api/resumen":
            try:
                data = consultar_resumen()
                self._send_json(200, data)
            except Exception as exc:
                log_componente(COMPONENTE, f"Error /api/resumen: {exc}", nivel="ERROR")
                self._send_json(500, {"error": str(exc)})

        else:
            self._send_json(404, {"error": "ruta no encontrada"})

    def do_POST(self):
        """Atiende todas las peticiones entrantes bajo el método POST de alteración de estado."""
        if self.path == "/api/priorizar":
            # Lee la longitud del contenido indicada en las cabeceras para saber cuántos bytes leer del socket
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length) # Lee el stream de datos crudos entrante
            try:
                data         = json.loads(body)
                interseccion = str(data.get("interseccion", "")).strip().upper()
                intersecciones_validas = generar_intersecciones_3x3()
                
                # Validación defensiva ante entradas maliciosas o erróneas desde la UI
                if interseccion not in intersecciones_validas:
                    self._send_json(400, {"error": f"Intersección inválida: {interseccion}"})
                    return
                    
                resultado = insertar_prioridad(interseccion)
                self._send_json(200, resultado)
            except Exception as exc:
                log_componente(COMPONENTE, f"Error /api/priorizar: {exc}", nivel="ERROR")
                self._send_json(500, {"error": str(exc)})
        else:
            self._send_json(404, {"error": "ruta no encontrada"})

    def do_OPTIONS(self):
        """Maneja las peticiones pre-vuelo (Preflight) necesarias para evitar bloqueos por políticas CORS."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ---------------------------------------------------------------------------
# Inicialización del Servidor (Hilo Principal)
# ---------------------------------------------------------------------------

def main():
    # Carga la configuración de red
    config = load_config()
    host = config["pc3"].get("frontend_host", "0.0.0.0") # Enlaza a todas las interfaces por defecto
    port = int(config["pc3"].get("frontend_port", 8080))

    log_componente(COMPONENTE, f"Iniciando servidor en http://{host}:{port}/")
    log_componente(COMPONENTE, f"BD: {DB_PATH}")

    # Instancia el servidor HTTP enlazando la tupla de red con la clase controladora creada
    server = HTTPServer((host, port), Handler)
    try:
        # Pone al proceso en escucha infinita bloqueante atendiendo peticiones secuenciales
        server.serve_forever()
    except KeyboardInterrupt:
        # Captura la detención controlada por consola (Ctrl+C)
        log_componente(COMPONENTE, "Servidor detenido.", nivel="WARN")
    finally:
        # Cierra el socket de escucha del servidor liberando el puerto del Sistema Operativo
        server.server_close()


if __name__ == "__main__":
    main()
