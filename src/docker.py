import os
import sys

import docker
import logging

DOCKER_SOCK = "/var/run/docker.sock"

def get_client():
    if not os.path.exists(DOCKER_SOCK):
        logging.error("Docker Socket not found. Socket file must be created at {}".format(DOCKER_SOCK))
        sys.exit(1)

    return docker.from_env()