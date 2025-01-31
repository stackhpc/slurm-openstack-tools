# -*- coding: utf-8 -*-

 # Licensed under the Apache License, Version 2.0 (the "License"); you may
 # not use this file except in compliance with the License. You may obtain
 # a copy of the License at
 #
 #      http://www.apache.org/licenses/LICENSE-2.0
 #
 # Unless required by applicable law or agreed to in writing, software
 # distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 # WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 # License for the specific language governing permissions and limitations
 # under the License.

import logging.handlers
import os
import re
import sys
from pathlib import Path

import openstack
import yaml

# Configure logging to syslog
logger = logging.getLogger("syslogger")
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler("/dev/log")
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s"))
logger.addHandler(handler)

# Directory containing per-node configurations
HOSTVARS_DIR = "/exports/cluster/hostvars"


def read_hostvars(node):
    """
    Read the hostvars.yml file for a specific node.
    """
    if not re.match(r'^[A-Za-z0-9-]+$', node):
        logger.error(f"Invalid node name: {node}. Node name must contain only alphanumeric characters.")
        sys.exit(1)

    hostvars_file = Path(HOSTVARS_DIR) / node / "hostvars.yml"
    if not hostvars_file.exists():
        logger.warning(f"No hostvars.yml found for node: {node}")
        return None

    with open(hostvars_file, "r") as f:
        return yaml.safe_load(f)


def find_server(conn, server_id):
    """
    Retrieve the server object using the server ID.
    """
    try:
        server = conn.get_server(server_id)
        if not server:
            logger.error(f"Server with ID {server_id} not found.")
            return None
        return server
    except openstack.exceptions.ResourceNotFound:
        logger.error(f"Server with ID {server_id} not found.")
        return None
    except Exception as e:
        logger.error(f"An error occurred while retrieving server {server_id}: {e}")
        raise


def process_node(conn, node):
    """
    Process a single node by comparing its target and current images.
    """
    hostvars = read_hostvars(node)
    if not hostvars:
        logger.info(f"No hostvars defined for node {node}, skipping...")
        return

    server_id = hostvars.get("instance_id")
    target_image_id = hostvars.get("image_id")

    if not server_id:
        raise ValueError(f"Node {node} does not have a valid server_id. Exiting.")

    if not target_image_id:
        raise ValueError(f"Node {node} does not have a target image defined. Exiting.")

    # Fetch the server object once
    server = find_server(conn, server_id)
    if not server:
        return

    current_image_id = server.image['id'] if 'image' in server and server.image else None
    if current_image_id != target_image_id:
        logger.info(f"Node {node} requires rebuild: current image {current_image_id}, target image {target_image_id}")
        rebuild_node(conn, server, target_image_id)
    else:
        logger.info(f"Node {node} is already using the target image, performing reboot...")
        reboot_node(conn, server)


def rebuild_node(conn, server, target_image_id):
    """
    Rebuild the node with the target image using the server object.
    """
    image = conn.image.get_image(target_image_id)
    if not image:
        logger.error(f"Target image {target_image_id} not found in OpenStack")
        return False

    conn.rebuild_server(server, image)
    logger.info(f"Rebuilt server {server.id} with image {target_image_id}.")


def reboot_node(conn, server, reboot_type="SOFT"):
    """
    Reboot the node using the server object (default: soft reboot).
    """
    conn.compute.reboot_server(server, reboot_type=reboot_type)
    logger.info(f"Rebooted server {server.id} with {reboot_type.lower()} reboot.")


def main():
    """
    Main function to process nodes from the Slurm-provided hostlist.
    """
    if len(sys.argv) < 2:
        logger.error("Usage: <script> <hostlist>")
        sys.exit(1)

    hostlist = sys.argv[1].split(",")

    try:
        conn = openstack.connection.from_config()
        logger.debug("OpenStack connection established")
    except Exception as e:
        logger.error(f"Failed to establish OpenStack connection: {e}")
        sys.exit(1)

    failed_nodes = 0

    for node in hostlist:
        logger.debug(f"Processing node: {node}")
        try:
            process_node(conn, node)
        except Exception as e:
            logger.error(f"Failed to process node {node}: {e}")
            failed_nodes += 1

        if failed_nodes > 0:
            logger.error(f"{failed_nodes} nodes failed to process. Exiting with error.")
            sys.exit(1)

    logger.info("All nodes processed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
