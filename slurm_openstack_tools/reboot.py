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
from os import path
import sys
import socket
import subprocess

import openstack
import pbr.version

__version__ = pbr.version.VersionInfo("slurm-openstack-tools").version_string()

MAX_REASON_LENGTH = 1000

# configure logging to syslog - by default only "info"
# and above categories appear
logger = logging.getLogger("syslogger")
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler("/dev/log")
handler.setFormatter(logging.Formatter(sys.argv[0] + ': %(message)s'))
logger.addHandler(handler)

INSTANCE_UUID_FILE = "/var/lib/cloud/data/instance-id"


def get_openstack_server_id():
    if not path.exists(INSTANCE_UUID_FILE):
        return None

    with open(INSTANCE_UUID_FILE) as f:
        return f.readline().strip()


def get_sinfo_path():
    # TODO(johngarbutt): get this from environment or config file?
    sinfo_alt_path = "/usr/local/software/slurm/current/bin/sinfo"
    if path.exists(sinfo_alt_path):
        return sinfo_alt_path
    return "sinfo"


def get_reboot_reason():
    # find our short hostname (without fqdn):
    hostname = socket.gethostname().split(".")[0]
    sinfo_path = get_sinfo_path()
    # see why we're being rebooted:
    sinfo = subprocess.run(
        [
            sinfo_path,
            "--noheader",
            "--nodes=%s" % hostname,
            "-O",
            "Reason:%i" % MAX_REASON_LENGTH,
        ],
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )
    return sinfo.stdout.strip()


def get_image_from_reason(reason):
    tokens = reason.split()
    image = None
    if len(tokens) > 1:
        image_tokens = tokens[1].split(":")
        if len(image_tokens) == 2 and image_tokens[0] == "image":
            if image_tokens[1]:
                image = image_tokens[1]
                logger.info(f"user requested image:%{image}")
    return image


def rebuild_openstack_server(server_id, reason):
    # Validate server_id
    conn = openstack.connection.from_config()
    server = conn.get_server(server_id)

    image_descr = get_image_from_reason(reason)
    if not image_descr:
        image_descr = server.image.id
        logger.info(f"couldn't parse image from reason '%{reason}', falling back to existing image:%{image_descr}")

    image = conn.image.find_image(image_descr) # doesn't throw exception
    if image is None:
        logger.error(f"image {image_descr} either not found or not unique")
        sys.exit(1)

    # Note that OpenStack will power down the server as part of the rebuild
    logger.info(f"rebuilding server %{server_id} with image %{image.id}")
    conn.rebuild_server(server_id, image.id)


def do_reboot():
    # in case we are on an NFS share,
    # try to ensure python stopped before reboot
    os.execvp("reboot", ["reboot"])


def rebuild_or_reboot():
    """A RebootProgram for slurm which can rebuild the node running it.

    This is intended to set as the `RebootProgram` in `slurm.conf`.
    It is then triggered by slurm using something like:
        scontrol reboot [ASAP] reason="rebuild image:<image_name_or_id>" <NODES>

    If the reason starts with "rebuild" then the node is rebuilt; arguments to
    `openstack.compute.rebuild_server()` may optionally be passed by including
    space-separated `name:value` pairs in the reason.

    If the reason does not start with "rebuild" then the node is rebooted.
    Note the "reason" message must be MAX_REASON_LENGTH or less.

    Messages and errors are logged to syslog.

    Requires:
    - Python 3 with openstacksdk module
    - The node's Openstack ID to have been set by cloud init in
      `/var/lib/cloud/data/instance-id`
    - An application credential:
        - with at least POST rights to /v3/servers/{server_id}/action
        - available via a clouds.yaml file containing only one cloud
    """
    server_uuid = get_openstack_server_id()
    if not server_uuid:
        logger.info("rebooting non openstack server")
        do_reboot()
    else:
        reason = get_reboot_reason()
        if not reason.startswith("rebuild"):
            logger.info("rebooting openstack server, locally")
            do_reboot()
        else:
            logger.info("rebuilding openstack server")
            rebuild_openstack_server(server_uuid, reason)

def main():
    try:
        rebuild_or_reboot()
    except:
        logger.exception('Exception in rebuild_or_reboot():')
        raise
