#!/usr/bin/env python3
import argparse
import os

from dotenv import load_dotenv

MASTER_DIRECTORIES = [
    "autogen/aarch64-master-0",
    "autogen/amd64-master-0",
    "autogen/amd64-master-1",
    "autogen/ppc64le-master-0",
    "autogen/s390x-master-0",
    "autogen/x86-master-0",
    "master-docker-nonstandard",
    "master-galera",
# TODO Enable these once it's more clear what needs to be done
#    "master-libvirt",
#    "master-nonlatent",
    "master-protected-branches",
]

START_TEMPLATE = """
---
version: "3.7"
services:
  mariadb:
    image: mariadb:10.6
    restart: unless-stopped
    container_name: mariadb
    environment:
      - MARIADB_ROOT_PASSWORD=password
      - MARIADB_DATABASE=buildbot
      - MARIADB_USER=buildmaster
      - MARIADB_PASSWORD=password
    networks:
      net_back:
    healthcheck:
      test: ['CMD', "mariadb-admin", "--password=password", "--protocol", "tcp", "ping"]
    volumes:
      - ./db:/docker-entrypoint-initdb.d:ro
      - ./mariadb:/var/lib/mysql:rw
    # command: --tmpdir=/var/lib/mysql/tmp

  crossbar:
    image: crossbario/crossbar
    restart: unless-stopped
    container_name: crossbar
    networks:
      net_back:

  master-web:
    image: quay.io/mariadb-foundation/bb-master:master-web
    restart: unless-stopped
    container_name: master-web
    volumes:
      - ./logs:/var/log/buildbot
      - ./buildbot/:/srv/buildbot/master
    entrypoint:
      - /srv/buildbot/master/docker-compose/start-bbm-web.sh
    networks:
      net_front:
      net_back:
    ports:
      - "127.0.0.1:8010:8010"
    depends_on:
      - mariadb
      - crossbar
"""

DOCKER_COMPOSE_TEMPLATE = """
  {master_name}:
    image: quay.io/mariadb-foundation/bb-master:master
    restart: unless-stopped
    container_name: {master_name}
    volumes:
      - ./logs:/var/log/buildbot
      - ./buildbot/:/srv/buildbot/master
    entrypoint:
      - /bin/bash
      - -c
      - "/srv/buildbot/master/docker-compose/start.sh {master_directory}"
    networks:
      net_front:
      net_back:
    ports:
      - "127.0.0.1:{port}:{port}"
    depends_on:
      - mariadb
      - crossbar
"""

END_TEMPLATE = """
networks:
  net_front:
    driver: bridge
    ipam:
      driver: default
      config:
        - subnet: 172.200.0.0/24
    driver_opts:
      com.docker.network.enable_ipv6: "false"
      com.docker.network.bridge.name: "br_bb_front"
  net_back:
    driver: bridge
    internal: true
    ipam:
      driver: default
      config:
        - subnet: 172.16.201.0/24
    driver_opts:
      com.docker.network.enable_ipv6: "false"
      com.docker.network.bridge.name: "br_bb_back"
"""

# Function to construct environment section for Docker Compose
def construct_env_section(env_vars):
    env_section = "    environment:\n"
    for key, value in env_vars.items():
        env_section += f"      - {key}\n"
    return env_section.rstrip('\n')

def main(args):
    # Capture the current environment variables' keys
    current_env_keys = set(os.environ.keys())

    # Load environment variables from the corresponding .env file
    env_file = ".env" if args.env == "prod" else ".env.dev"
    load_dotenv(env_file)

    # Determine the keys that were added by the .env file
    new_keys = set(os.environ.keys()) - current_env_keys

    # Extract only the variables from the .env file
    env_vars = {key: os.getenv(key) for key in new_keys}

    # Modify the start_template to include the environment variables for master-web
    master_env_section = construct_env_section(env_vars)
    start_template = START_TEMPLATE.replace("container_name: master-web", f"container_name: master-web\n{master_env_section}")

    # Modify the docker_compose_template to include the environment variables
    docker_compose_template = DOCKER_COMPOSE_TEMPLATE.replace("container_name: {master_name}", f"container_name: {{master_name}}\n{master_env_section}")

    # Generate startup scripts and Docker Compose pieces for each master directory
    with open("docker-compose.yaml", "w") as f:
        f.write("# This is an autogenerated file. Do not edit it manually. Use `python generate-config.py` instead.")
        f.write(start_template)
        port = 8011
        for master_directory in MASTER_DIRECTORIES:
            master_name = master_directory.replace("/", "_")

            # Generate Docker Compose piece
            docker_compose_piece = docker_compose_template.format(
                master_name=master_name,
                master_directory=master_directory,
                port=port,
            )
            port += 1

            f.write(docker_compose_piece)
        f.write(END_TEMPLATE)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Docker Compose configuration.")
    parser.add_argument("--env", choices=["prod", "dev"], default="dev", help="Choose the environment (prod/dev). Default is dev.")

    args = parser.parse_args()
    main(args)
