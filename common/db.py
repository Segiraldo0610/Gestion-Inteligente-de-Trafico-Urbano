import sqlite3
from typing import Any, Dict, List, Optional


def _obtener_conexion(db_path: str) -> sqlite3.Connection:
    """
    Crea una conexión SQLite con filas tipo diccionario.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_db(db_path: str) -> None:
    """
    Crea las tablas necesarias si no existen.
    - eventos
    - acciones_semaforo
    """
    with _obtener_conexion(db_path) as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_evento TEXT NOT NULL,
                sensor_id TEXT NOT NULL,
                interseccion TEXT NOT NULL,
                datos_json TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS acciones_semaforo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interseccion TEXT NOT NULL,
                estado TEXT NOT NULL,
                duracion INTEGER NOT NULL,
                motivo TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )

        conn.commit()


def guardar_evento(
    db_path: str,
    tipo_evento: str,
    sensor_id: str,
    interseccion: str,
    datos_json: str,
    timestamp: str,
) -> int:
    """
    Inserta un evento y devuelve el id insertado.
    """
    with _obtener_conexion(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO eventos (tipo_evento, sensor_id, interseccion, datos_json, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tipo_evento, sensor_id, interseccion, datos_json, timestamp),
        )
        conn.commit()
        return cur.lastrowid


def guardar_accion(
    db_path: str,
    interseccion: str,
    estado: str,
    duracion: int,
    motivo: str,
    timestamp: str,
) -> int:
    """
    Inserta una acción de semáforo y devuelve el id insertado.
    """
    with _obtener_conexion(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO acciones_semaforo (interseccion, estado, duracion, motivo, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (interseccion, estado, duracion, motivo, timestamp),
        )
        conn.commit()
        return cur.lastrowid


def consultar_historico(
    db_path: str,
    interseccion: Optional[str] = None,
    limite: int = 100,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Consulta histórico reciente de:
    - eventos
    - acciones_semaforo

    Si se envía interseccion, filtra por esa intersección.
    """
    if limite <= 0:
        limite = 100

    with _obtener_conexion(db_path) as conn:
        cur = conn.cursor()

        if interseccion:
            cur.execute(
                """
                SELECT id, tipo_evento, sensor_id, interseccion, datos_json, timestamp
                FROM eventos
                WHERE interseccion = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (interseccion, limite),
            )
        else:
            cur.execute(
                """
                SELECT id, tipo_evento, sensor_id, interseccion, datos_json, timestamp
                FROM eventos
                ORDER BY id DESC
                LIMIT ?
                """,
                (limite,),
            )
        eventos = [dict(row) for row in cur.fetchall()]

        if interseccion:
            cur.execute(
                """
                SELECT id, interseccion, estado, duracion, motivo, timestamp
                FROM acciones_semaforo
                WHERE interseccion = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (interseccion, limite),
            )
        else:
            cur.execute(
                """
                SELECT id, interseccion, estado, duracion, motivo, timestamp
                FROM acciones_semaforo
                ORDER BY id DESC
                LIMIT ?
                """,
                (limite,),
            )
        acciones = [dict(row) for row in cur.fetchall()]

    return {
        "eventos": eventos,
        "acciones_semaforo": acciones,
    }


def consultar_estado_general(db_path: str) -> Dict[str, Any]:
    """
    Retorna un resumen general de la base de datos:
    - cantidad total de eventos
    - cantidad total de acciones
    - último evento registrado
    - última acción registrada
    """
    with _obtener_conexion(db_path) as conn:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) AS total FROM eventos")
        total_eventos = cur.fetchone()["total"]

        cur.execute("SELECT COUNT(*) AS total FROM acciones_semaforo")
        total_acciones = cur.fetchone()["total"]

        cur.execute(
            """
            SELECT id, tipo_evento, sensor_id, interseccion, datos_json, timestamp
            FROM eventos
            ORDER BY id DESC
            LIMIT 1
            """
        )
        ultimo_evento_row = cur.fetchone()
        ultimo_evento = dict(ultimo_evento_row) if ultimo_evento_row else None

        cur.execute(
            """
            SELECT id, interseccion, estado, duracion, motivo, timestamp
            FROM acciones_semaforo
            ORDER BY id DESC
            LIMIT 1
            """
        )
        ultima_accion_row = cur.fetchone()
        ultima_accion = dict(ultima_accion_row) if ultima_accion_row else None

    return {
        "total_eventos": total_eventos,
        "total_acciones_semaforo": total_acciones,
        "ultimo_evento": ultimo_evento,
        "ultima_accion_semaforo": ultima_accion,
    }
