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
import socket
import subprocess
import sys
import traceback

import openstack
import pbr.version

__version__ = pbr.version.VersionInfo("slurm-openstack-tools").version_string()

MAX_REASON_LENGTH = 1000

# configure logging to syslog - by default only "info"
# and above categories appear
logger = logging.getLogger("syslogger")
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler("/dev/log")
logger.addHandler(handler)


def rebuild_or_reboot():
    """A RebootProgram for slurm which can rebuild the node running it.

    This is intended to set as the `RebootProgram` in `slurm.conf`.
    It is then triggered by slurm using something like:
        scontrol reboot [ASAP] reason="rebuild image:<image_id>" <NODES>

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
    if not path.exists("/var/lib/cloud/data/instance-id"):
        logger.info("Restarting non openstack server")
        os.system("reboot")
        sys.exit(0)

    try:
        # find our short hostname (without fqdn):
        hostname = socket.gethostname().split(".")[0]

        # see why we're being rebooted:
        sinfo = subprocess.run(
            [
                "sinfo",
                "--noheader",
                "--nodes=%s" % hostname,
                "-O",
                "Reason:%i" % MAX_REASON_LENGTH,
            ],
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )
        reason = sinfo.stdout.strip()

        # find server running this script:
        with open("/var/lib/cloud/data/instance-id") as f:
            instance_id = f.readline().strip()
        logger.info(
            "%s (server id %s): reason=%r", __file__, instance_id, reason
        )

        if reason.startswith("rebuild"):
            # NB what's actually required in rebuild() isn't as documented,
            # hence we need to set some "optional" parameters:
            conn = openstack.connection.from_config()
            me = conn.compute.get_server(instance_id)
            params = {
                "name": hostname,
                "admin_password": None,
                "image": me.image.id,
            }
            user_params = dict(
                param.split(":") for param in reason.split()[1:]
            )
            params.update(user_params)
            logger.info(
                "%s (server id %s): rebuilding %s",
                __file__,
                instance_id,
                params,
            )
            conn.compute.rebuild_server(instance_id, **params)
        else:
            logger.info("%s (server id %s): rebooting", __file__, instance_id)
            os.system("reboot")

    except Exception:
        logger.error(traceback.format_exc())
        sys.exit(1)
