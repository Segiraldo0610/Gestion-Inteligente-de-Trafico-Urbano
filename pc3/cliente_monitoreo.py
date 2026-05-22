#!/usr/bin/env python3

import os
import sys

import zmq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config_loader import load_config


def main():

    config = load_config()

    host = "localhost"

    puerto = config["ports"]["monitoreo_to_analitica"]

    ctx = zmq.Context()

    req = ctx.socket(zmq.REQ)

    endpoint = f"tcp://{host}:{puerto}"

    req.connect(endpoint)

    print(f"Conectado a {endpoint}")

    while True:

        mensaje = input(
            "\nComando (consultar/priorizar) > "
        )

        req.send_string(mensaje)

        respuesta = req.recv_string()

        print("\nRESPUESTA:")
        print(respuesta)


if __name__ == "__main__":
    main()
