#!/usr/bin/env python3

import time
import zmq

from common.config_loader import load_config
from common.utils import log_componente

COMPONENTE = "healthcheck"


def main():

    config = load_config()

    host_pc2 = config["pc2"]["host"]

    puerto = config["ports"]["healthcheck"]

    ctx = zmq.Context()

    socket = ctx.socket(zmq.PUSH)

    endpoint = f"tcp://{host_pc2}:{puerto}"

    socket.connect(endpoint)

    log_componente(
        COMPONENTE,
        f"Heartbeat conectado a {endpoint}"
    )

    try:

        while True:

            socket.send_string("heartbeat")

            log_componente(
                COMPONENTE,
                "Heartbeat enviado"
            )

            time.sleep(3)

    except KeyboardInterrupt:

        log_componente(
            COMPONENTE,
            "Health check detenido",
            nivel="WARN"
        )

    finally:

        socket.close(linger=0)

        ctx.term()


if __name__ == "__main__":
    main()
