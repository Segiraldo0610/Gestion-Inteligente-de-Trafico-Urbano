import json
import os


REQUIRED_TOP_LEVEL_KEYS = ["pc1", "pc2", "pc3", "ports"]
REQUIRED_PC_KEYS = ["host", "role"]
REQUIRED_PORT_KEYS = [
    "sensor_to_broker",
    "broker_to_analitica",
    "analitica_to_db_principal",
    "analitica_to_db_replica",
    "analitica_to_semaforos",
    "monitoreo_to_analitica",
    "healthcheck",
]


def _validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("La configuración debe ser un diccionario JSON.")

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in config:
            raise ValueError(f"Falta la clave obligatoria: '{key}'.")

    for pc in ["pc1", "pc2", "pc3"]:
        if not isinstance(config[pc], dict):
            raise ValueError(f"La sección '{pc}' debe ser un objeto.")
        for subkey in REQUIRED_PC_KEYS:
            if subkey not in config[pc]:
                raise ValueError(f"Falta '{subkey}' en la sección '{pc}'.")
            if not isinstance(config[pc][subkey], str) or not config[pc][subkey].strip():
                raise ValueError(f"'{pc}.{subkey}' debe ser un texto no vacío.")

    if not isinstance(config["ports"], dict):
        raise ValueError("La sección 'ports' debe ser un objeto.")

    for port_key in REQUIRED_PORT_KEYS:
        if port_key not in config["ports"]:
            raise ValueError(f"Falta el puerto obligatorio: 'ports.{port_key}'.")
        port_value = config["ports"][port_key]
        if not isinstance(port_value, int):
            raise ValueError(f"'ports.{port_key}' debe ser un número entero.")
        if port_value < 1 or port_value > 65535:
            raise ValueError(f"'ports.{port_key}' debe estar entre 1 y 65535.")

    return True


def load_config(config_path=None):
    """
    Carga y valida el archivo config.json.

    Args:
        config_path (str | None): Ruta opcional al config.json.
                                  Si es None, usa la ruta por defecto en la raíz del proyecto.

    Returns:
        dict: Configuración validada.
    """
    if config_path is None:
        # common/config_loader.py -> subir un nivel para llegar a la raíz del proyecto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config.json")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    _validate_config(config)
    return config

