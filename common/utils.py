from datetime import datetime, timezone
import random

# Estados válidos para el semáforo en este proyecto
ESTADOS_SEMAFORO_VALIDOS = {"ROJO", "AMARILLO", "VERDE"}


def generar_timestamp_iso() -> str:
    """
    Genera un timestamp en formato ISO 8601 en UTC.
    Ejemplo: 2026-04-08T15:30:45Z
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def log_componente(nombre_componente: str, mensaje: str, nivel: str = "INFO") -> None:
    """
    Imprime un log simple con timestamp, nivel y nombre del componente.
    """
    timestamp = generar_timestamp_iso()
    print(f"[{timestamp}] [{nivel}] [{nombre_componente}] {mensaje}")


def generar_intersecciones_3x3() -> list[str]:
    """
    Genera las intersecciones para una ciudad de 3x3:
    I11, I12, I13, I21, I22, I23, I31, I32, I33
    """
    return [f"I{fila}{columna}" for fila in range(1, 4) for columna in range(1, 4)]


def interseccion_aleatoria(intersecciones: list[str] | None = None) -> str:
    """
    Devuelve una intersección aleatoria.
    Si no se pasa lista, usa las intersecciones 3x3 por defecto.
    """
    if intersecciones is None:
        intersecciones = generar_intersecciones_3x3()

    if not intersecciones:
        raise ValueError("La lista de intersecciones no puede estar vacía.")

    return random.choice(intersecciones)


def validar_estado_semaforo(estado: str) -> bool:
    """
    Valida si el estado del semáforo es permitido.
    Acepta mayúsculas/minúsculas, ignorando espacios externos.
    """
    if not isinstance(estado, str):
        return False
    estado_normalizado = estado.strip().upper()
    return estado_normalizado in ESTADOS_SEMAFORO_VALIDOS
