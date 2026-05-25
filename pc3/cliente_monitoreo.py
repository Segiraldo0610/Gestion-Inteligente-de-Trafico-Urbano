#!/usr/bin/env python3
"""
Cliente de monitoreo (PC3).
Permite enviar comandos manuales a analítica usando ZeroMQ (REQ/REP).
"""

import os
import sys

import zmq  # Librería para mensajería distribuida

# Añade el directorio raíz del proyecto al path para importar módulos comunes
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config_loader import load_config  # Carga configuración desde archivo


def main():
    # Carga la configuración del sistema
    config = load_config()

    # Define el host donde corre el servicio de analítica
    host = "localhost"

    # Obtiene el puerto configurado para comunicación monitoreo -> analítica
    puerto = config["ports"]["monitoreo_to_analitica"]

    # Inicializa el contexto de ZeroMQ
    ctx = zmq.Context()

    # Crea un socket tipo REQ (cliente que envía solicitudes)
    req = ctx.socket(zmq.REQ)

    # Construye la dirección de conexión
    endpoint = f"tcp://{host}:{puerto}"

    # Conecta el cliente al servidor de analítica
    req.connect(endpoint)

    # Mensaje informativo de conexión
    print(f"Conectado a {endpoint}")

    while True:
        # Solicita al usuario que introduzca un comando
        mensaje = input("\nComando (consultar/priorizar) > ")

        # Envía el comando como string
        req.send_string(mensaje)

        # Espera la respuesta del servidor (obligatorio en patrón REQ/REP)
        respuesta = req.recv_string()

        # Muestra la respuesta recibida
        print("\nRESPUESTA:")
        print(respuesta)


# Punto de entrada del programa
if __name__ == "__main__":
    main()
