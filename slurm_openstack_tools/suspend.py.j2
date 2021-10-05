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

""" A Slurm SuspendProgram to delete OpenStack instances.

    Usage:

        suspend HOSTLIST_EXPRESSION

    where:
        HOSTLIST_EXPRESSION: Name(s) of node(s) to create, using Slurm's hostlist expression, as per [1].

    If a file with the nodename exists in the Slurm control daemons spool directory [2] then the OpenStack ID is read from it and used to select the instance to delete.
    Otherwise, this will attempt to delete the instance by name which requires that the name is unique.

    Output and exceptions are written to the syslog.

    [1]: https://slurm.schedmd.com/slurm.conf.html#OPT_SuspendProgram
    [2]: https://slurm.schedmd.com/slurm.conf.html#OPT_SlurmdSpoolDir

"""

import sys, os, subprocess, logging, logging.handlers
import openstack
import pprint

# configure logging to syslog - by default only "info" and above categories appear
logger = logging.getLogger("syslogger")
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler("/dev/log")
handler.setFormatter(logging.Formatter(sys.argv[0] + ': %(message)s'))
logger.addHandler(handler)

def get_statesavelocation():
    """ Return the path for Slurm's StateSaveLocation """
    scontrol = subprocess.run(['scontrol', 'show', 'config'], stdout=subprocess.PIPE, universal_newlines=True)
    for line in scontrol.stdout.splitlines():
        if line.startswith('StateSaveLocation'): # StateSaveLocation       = /var/spool/slurm
            return line.split()[-1]

def expand_nodes(hostlist_expr):
    scontrol = subprocess.run(['scontrol', 'show', 'hostnames', hostlist_expr], stdout=subprocess.PIPE, universal_newlines=True)
    return scontrol.stdout.strip().split('\n')

def delete_server(conn, name):
    server = conn.compute.find_server(name)
    conn.compute.delete_server(server)

def suspend():
    hostlist_expr = sys.argv[1]
    logger.info(f"Slurmctld invoked suspend {hostlist_expr}")
    remove_nodes = expand_nodes(hostlist_expr)

    conn = openstack.connection.from_config()
    logger.info(f"Got openstack connection {conn}")

    for node in remove_nodes:
        instance_id = False
        statedir = get_statesavelocation()
        instance_file = os.path.join(statedir, node)
        try:
            with open(instance_file) as f:
                instance_id = f.readline().strip()
        except FileNotFoundError:
            logger.info(f"no instance file found in {statedir} for node {node}")

        logger.info(f"deleting node {instance_id or node}")
        delete_server(conn, (instance_id or node))

def main():
    try:
        suspend()
    except:
        logger.exception('Exception in main:')
        raise
