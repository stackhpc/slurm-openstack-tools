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

SCONTROL_PATH = '/usr/bin/scontrol'

# configure logging to syslog - by default only "info" and above
# categories appear
logger = logging.getLogger("syslogger")
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler("/dev/log")
handler.setFormatter(logging.Formatter(sys.argv[0] + ': %(message)s'))
logger.addHandler(handler)

def expand_nodes(hostlist_expr):
    scontrol = subprocess.run(
        [SCONTROL_PATH, 'show', 'hostnames', hostlist_expr],
        stdout=subprocess.PIPE, universal_newlines=True)
    return scontrol.stdout.strip().split('\n')


def resumefail():
    hostlist_expr = sys.argv[1]
    logger.info(f"Slurmctld invoked resumefail {hostlist_expr}")
    failed_nodes = expand_nodes(hostlist_expr)

    conn = openstack.connection.from_config()
    logger.info(f"Got openstack connection {conn}")

    statedir = get_statesavelocation()

    for node in failed_nodes:
        server = conn.compute.find_server(node)
        if server is None:
            logger.info(f"No server found for {node}, resuming")
            scontrol = subprocess.run([SCONTROL_PATH, 'update', 'state=resume', 'nodename=%s' % node],
                stdout=subprocess.PIPE, universal_newlines=True)

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
