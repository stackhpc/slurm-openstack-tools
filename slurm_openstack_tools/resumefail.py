# -*- coding: utf-8 -*-

# See ../LICENCE

"""A Slurm ResumeFail for OpenStack instances.

This simply resumes any DOWN nodes for which there is no corresponding cloud instance.

Usage:

    resumefail HOSTLIST_EXPRESSION

where: HOSTLIST_EXPRESSION: Name(s) of node(s) which have failed  using Slurm's
    hostlist expression, as per [1].

Output and exceptions are written to the syslog.

OpenStack credentials must be available to this script (e.g. via an
application credential in /etc/openstack/clouds.yaml readable by the slurm
user).

[1]: https://slurm.schedmd.com/slurm.conf.html#OPT_ResumeFailProgram

"""

import logging.handlers
import os
import subprocess
import sys

import openstack

from slurm_openstack_tools.utils import expand_nodes

SCONTROL_PATH = '/usr/bin/scontrol'

# configure logging to syslog - by default only "info" and above
# categories appear
logger = logging.getLogger("syslogger")
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler("/dev/log")
handler.setFormatter(logging.Formatter(sys.argv[0] + ': %(message)s'))
logger.addHandler(handler)

def resumefail():
    hostlist_expr = sys.argv[1]
    logger.info(f"Slurmctld invoked resumefail {hostlist_expr}")
    failed_nodes = expand_nodes(hostlist_expr)

    conn = openstack.connection.from_config()
    logger.info(f"Got openstack connection {conn}")

    for node in failed_nodes:
        server = conn.compute.find_server(node)
        if server is None:
            logger.info(f"No instance found for {node}, requesting resume of node.")
            scontrol = subprocess.run([SCONTROL_PATH, 'update', 'state=resume', 'nodename=%s' % node],
                stdout=subprocess.PIPE, universal_newlines=True)
        else:
            # retrieve info ourselves for errors, not exposed through the SDK attributes:
            info = conn.compute.get(f"/servers/{server.id}").json()
            if info['server']['status'] == 'ERROR': # https://docs.openstack.org/api-ref/compute/?expanded=show-server-details-detail#id30
                fault_message = info['server'].get('fault', {}).get('message', None)
                if fault_message:
                    if "not enough hosts available" in fault_message:
                        logger.info(f"Instance for {node} has error message '{fault_message}': Requesting instance delete and resume of node.")
                        conn.compute.delete_server(server, ignore_missing=True, force=True)
                        scontrol = subprocess.run([SCONTROL_PATH, 'update', 'state=resume', 'nodename=%s' % node],
                            stdout=subprocess.PIPE, universal_newlines=True)
                    else:
                        logger.error(f"Instance for {node} has error message '{fault_message}'. Cannot fix this.")
            else:
                logger.error(f"Instance for {node} has status {info['server']['status']}. Cannot fix this.")

def main():
    try:
        resumefail()
    except BaseException:
        logger.exception('Exception in main:')
        raise

if __name__ == '__main__':
    # running for testing
    handler = logging.StreamHandler() # log to console
    main()
