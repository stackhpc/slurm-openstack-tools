# -*- coding: utf-8 -*-

# See ../LICENCE

import logging.handlers
import os
import subprocess
import sys
import time

import openstack
import pbr.version

from slurm_openstack_tools.resume import resume
from slurm_openstack_tools.suspend import suspend
from slurm_openstack_tools import utils

__version__ = pbr.version.VersionInfo("slurm-openstack-tools").version_string()

# configure logging to syslog - by default only "info"
# and above categories appear
logger = logging.getLogger("syslogger")
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler("/dev/log")
handler.setFormatter(logging.Formatter(sys.argv[0] + ': %(message)s'))
logger.addHandler(handler)

def matching_nodes(hostlist_expr, state):
    """ Returns a hostlist expression for only nodes matching `state`. """

    sinfo = subprocess.run(
        ['sinfo', 'noheader', f"--nodes={hostlist_expr}", f"--states={state}", "--format='%N'"],
        stdout=subprocess.PIPE, universal_newlines=True)
    
    return sinfo.stdout.strip()

def openstack_instance_status(conn, uuids):
    """ Return a dict keyed by UUID with status str (or None). """
    statuses = dict((id, None) for id in uuids)
    for uuid in uuids:
        response = conn.compute.get(f"/servers/detail").json()
        for server in response['servers']:
            id = server['id']
            if id in uuids:
                statuses[id] = server['status']
    return statuses

def redeploy(hostlist_expr):
    """A PrologSlurmctld for slurm which deletes and recreates CLOUD nodes.

    Messages and errors are logged to syslog.

    Any non-CLOUD-state nodes in the job are not modified.

    Requires:
    - Python 3 with openstacksdk module
    - An application credential:
        - with at least POST rights to /v3/servers/{server_id}/action
        - available via a clouds.yaml file containing only one cloud
    """ # noqa E501
    
    logger.info(f"Slurmctld invoked PrologSlurmctld for {hostlist_expr}")

    conn = openstack.connection.from_config()
    
    # filter out non-CLOUD nodes:
    cloud_hostlist = matching_nodes(hostlist_expr, 'CLOUD')
    if not cloud_hostlist:
        exit(0)
    
    # get slurm config:
    slurm_conf = utils.get_slurm_conf()
    resume_timeout = slurm_conf['ResumeTimeout'].split() # time from issuing resume to being available for use, e.g. '300 sec'
    suspend_timeout = slurm_conf['SuspendTimeout'].split() # time from issuing suspend to being ready for new resume, e.g. '30 sec'
    
    # delete nodes:
    suspend(cloud_hostlist)
    assert suspend_timeout[1] == 'sec', 'SuspendTimeout not defined in seconds'
    time.sleep(int(suspend_timeout[0]))
    
    # recreate them:
    new_uuids = resume(cloud_hostlist)

    # wait until all instances are ACTIVE or timeout:
    assert resume_timeout[1] == 'sec', 'ResumeTimeout not defined in seconds'
    start = time.monotonic()
    sleep_time = int(resume_timeout[0]) / 10
    all_active = False
    while True:
        status = openstack_instance_status(new_uuids)
        if all(s == 'ACTIVE' for s in status.values()):
            all_active = True
            break
        if (time.monotonic() - start) > int(resume_timeout[0]):
            break
        time.sleep(sleep_time)
    
    # check all nodes up:
    if not all_active:
        logger.error(f"Not all nodes ACTIVE by ResumeTimeout: {status}")
        exit(1)
    

def main():
    try:
        hostlist_expr = os.getenv('SLURM_JOB_NODELIST')
        redeploy(hostlist_expr)
    except BaseException:
        logger.exception('Exception in redeploy():')
        raise
