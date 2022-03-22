# -*- coding: utf-8 -*-

# See ../LICENCE

"""A Slurm SuspendProgram to delete OpenStack instances.

Usage:

    suspend HOSTLIST_EXPRESSION

where: HOSTLIST_EXPRESSION: Name(s) of node(s) to create, using Slurm's
    hostlist expression, as per [1].

If a file with the nodename exists in the Slurm control daemons spool directory
[2] then the OpenStack ID is read from it and used to select the instance to
delete. Otherwise, this will attempt to delete the instance by name which
requires that the name is unique.

Output and exceptions are written to the syslog.

[1]: https://slurm.schedmd.com/slurm.conf.html#OPT_SuspendProgram [2]:
https://slurm.schedmd.com/slurm.conf.html#OPT_SlurmdSpoolDir

"""

import logging
import logging.handlers
import os
import subprocess
import sys

import openstack

from slurm_openstack_tools.utils import get_slurm_conf, expand_nodes

# configure logging to syslog - by default only "info" and above
# categories appear
logger = logging.getLogger("syslogger")
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler("/dev/log")
handler.setFormatter(logging.Formatter(sys.argv[0] + ': %(message)s'))
logger.addHandler(handler)

def suspend(hostlist_expr):
    """ Deletes nodes defined by a hostlist expression. Returns a sequence of OpenStack instance UUIDs. """
    
    logger.info(f"Slurmctld invoked suspend {hostlist_expr}")
    remove_nodes = expand_nodes(hostlist_expr)

    conn = openstack.connection.from_config()
    logger.info(f"Got openstack connection {conn}")

    statedir = get_slurm_conf()['StateSaveLocation']

    deleted_instance_ids = []
    for node in remove_nodes:
        instance_id = False
        instance_file = os.path.join(statedir, node)
        try:
            with open(instance_file) as f:
                instance_id = f.readline().strip()
        except FileNotFoundError:
            logger.error(f"no instance file found in {statedir} for node {node}")
            exit(1)

        logger.info(f"deleting node {instance_id}")
        conn.compute.delete_server(instance_id)
        deleted_instance_ids.append(instance_id)

    return deleted_instance_ids

def main():
    try:
        hostlist_expr = sys.argv[1]
        suspend(hostlist_expr)
    except BaseException:
        logger.exception('Exception in main:')
        raise
