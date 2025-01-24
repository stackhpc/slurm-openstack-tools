import yaml
import logging.handlers
import openstack
import os
import sys
from pathlib import Path

# Configure logging to syslog
logger = logging.getLogger("syslogger")
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler("/dev/log")
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s"))
logger.addHandler(handler)

# Directory containing per-node configurations
HOSTVARS_DIR = "/exports/cluster/hostvars"


def get_hostlist_from_slurm():
    """
    Parse the hostlist provided by Slurm as command-line arguments.
    """
    if len(sys.argv) < 2:
        logger.error("No hostlist provided by Slurm")
        sys.exit(1)
    return sys.argv[1].split(",")


def read_hostvars(node):
    """
    Read the hostvars.yml file for a specific node.
    """
    hostvars_file = Path(HOSTVARS_DIR) / node / "hostvars.yml"
    if not hostvars_file.exists():
        logger.warning(f"No hostvars.yml found for node: {node}")
        return None

    with open(hostvars_file, "r") as f:
        return yaml.safe_load(f)


def get_current_image(conn, server_id):
    """
    Retrieve the current image for a server using OpenStack.
    """
    server = conn.get_server(server_id)
    if not server:
        logger.error(f"Server ID {server_id} not found in OpenStack")
        return None
    return server.image.id


def rebuild_node(conn, server_id, image_id):
    """
    Rebuild the node with the target image.
    """
    image = conn.image.find_image(image_id)
    if not image:
        logger.error(f"Target image {image_id} not found in OpenStack")
        return False

    logger.info(f"Rebuilding server {server_id} with image {image_id}")
    conn.rebuild_server(server_id, image.id)
    return True


def reboot_node(conn, server_id, reboot_type="HARD"):
    """
    Reboot the node (default: hard reboot).
    """
    logger.info(f"Rebooting server {server_id} with {reboot_type.lower()} reboot")
    conn.compute.reboot_server(server_id, reboot_type=reboot_type)
    return True


def process_node(conn, node):
    """
    Process a single node by comparing its target and current images.
    """
    hostvars = read_hostvars(node)
    if not hostvars:
        logger.info(f"No hostvars defined for node {node}, skipping...")
        return

    server_id = hostvars.get("openstack_id")
    image_id = hostvars.get("image_id")

    if not server_id:
        logger.info(f"Node {node} is not an OpenStack node, performing local reboot...")
        os.system(f"ssh {node} sudo reboot")
        return

    if not image_id:
        logger.info(f"Node {node} does not have a target image defined, performing reboot...")
        reboot_node(conn, server_id)
        return

    current_image = get_current_image(conn, server_id)
    if current_image != image_id:
        logger.info(f"Node {node} requires rebuild: current image {current_image}, target image {image_id}")
        rebuild_node(conn, server_id, image_id)
    else:
        logger.info(f"Node {node} is already using the target image, performing reboot...")
        reboot_node(conn, server_id)


def main():
    """
    Main function to process nodes from the Slurm-provided hostlist.
    """
    if len(sys.argv) < 2:
        logger.error("Usage: <script> <hostlist>")
        sys.exit(1)

    hostlist = sys.argv[1].split(",")
    conn = openstack.connection.from_config()

    for node in hostlist:
        process_node(conn, node)


if __name__ == "__main__":
    main()
