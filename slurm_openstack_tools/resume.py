# -*- coding: utf-8 -*-

# See ../LICENCE

"""A Slurm ResumeProgram to create OpenStack instances.

Usage:

    resume HOSTLIST_EXPRESSION [debug]

where: HOSTLIST_EXPRESSION: Name(s) of node(s) to create, using Slurm's
    hostlist expression, as per [1]. debug: Any 2nd argument puts this in debug
    mode which is more verbose but does not actually create nodes.

Output and exceptions are written to the syslog. The OpenStack ID(s) of the
created node(s) are written to hostname-named files in the Slurm control
daemons spool directory [2].

The flavor, image, network and keypair to be used must be defined as node
Features [3] in the format "parameter=value".

OpenStack credentials must be available to this script (e.g. via an
application credential in /etc/openstack/clouds.yaml readable by the slurm
user). DNS must be available and `SlurmctldParameters=cloud_dns` set in the
slurm.conf [4].

[1]: https://slurm.schedmd.com/slurm.conf.html#OPT_ResumeProgram [2]:
https://slurm.schedmd.com/slurm.conf.html#OPT_SlurmdSpoolDir [3]:
https://slurm.schedmd.com/slurm.conf.html#OPT_Features [4]:
https://slurm.schedmd.com/slurm.conf.html#OPT_cloud_dns

"""

import logging.handlers
import os
import subprocess
import sys

import openstack

from slurm_openstack_tools.utils import get_slurm_conf, expand_nodes

REQUIRED_PARAMS = ('image', 'flavor', 'keypair', 'network')

# configure logging to syslog - by default only "info" and above
# categories appear
logger = logging.getLogger("syslogger")
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler("/dev/log")
handler.setFormatter(logging.Formatter(sys.argv[0] + ': %(message)s'))
logger.addHandler(handler)


def get_features(nodenames):
    """Retrieve the features specified for given node(s).

    Returns a dict with a key/value pair for each node. Keys are node names,
    values are lists of strings, one string per feature.
    """

    scontrol = subprocess.run(
        ['scontrol', 'show', 'node', nodenames],
        stdout=subprocess.PIPE, universal_newlines=True)
    features = {}
    for line in scontrol.stdout.splitlines():
        line = line.strip()
        if line.startswith(
            'NodeName'):  # NodeName=dev-small-cloud-1 CoresPerSocket=1
            node = line.split()[0].split('=')[1]
        if line.startswith('AvailableFeatures'):
            feature_args = line.split('=', 1)[1]
            features[node] = feature_args.split(',')

    return features


def create_server(conn, name, image, flavor, network, keypair, port=None):

    server = conn.compute.create_server(
        name=name, image_id=image.id, flavor_id=flavor.id,
        networks=[{"port": port.id}] if port else [{"uuid": network.id}],
    )

    return server


def resume(hostlist_expr, debug=False):
    """ Creates nodes defined by a hostlist expression. Returns a sequence of OpenStack instance UUIDs. """

    logger.info(f"Slurmctld invoked resume {hostlist_expr}")
    new_nodes = expand_nodes(hostlist_expr)

    conn = openstack.connection.from_config()
    logger.info(f"Got openstack connection {conn}")

    features = get_features(hostlist_expr)
    logger.info(f"Read feature information from slurm")

    statedir = get_slurm_conf()['StateSaveLocation']

    created_instance_ids = []
    for node in new_nodes:
        # extract the openstack parameters from node features:
        if node not in features:
            logger.error(
                f"No Feature definitions found for node {node}: {features}")
        os_parameters = dict(feature.split('=') for feature in features[node])
        if debug:
            logger.info(f"os_parameters for {node}: {os_parameters}")
        missing = set(REQUIRED_PARAMS).difference(os_parameters.keys())
        if missing:
            logger.error(
                f"Missing {','.join(missing)} from feature definition for "
                f"node {node}: {os_parameters}"
            )

        # get openstack objects:
        os_objects = {
            'image': conn.compute.find_image(os_parameters['image']),
            'flavor': conn.compute.find_flavor(os_parameters['flavor']),
            'network': conn.network.find_network(os_parameters['network']),
            'keypair': conn.compute.find_keypair(os_parameters['keypair']),
        }
        not_found = dict([(k, os_parameters[k]) for (k, v) in os_objects.items() if v is None])
        if not_found:
            raise ValueError(
                'Could not find openstack objects for: '
                ', '.join([f'{k}={v}' for (k, v) in not_found.items()])
                )

        # get optional port - done outside os_objects so an error finding network doesn't cause unhelpful port traceback:
        os_objects['port'] = conn.network.find_port(node, network_id=os_objects['network'].id)

        if debug:
            logger.info(f"os_objects for {node} : {os_objects}")
        else:
            logger.info(f"creating node {node}")
            server = create_server(conn, node, **os_objects)
            logger.info(f"server: {server}")
            with open(os.path.join(statedir, node), 'w') as f:
                f.write(server.id)
            # Don't need scontrol update nodename={node} nodeaddr={server_ip}
            # as using SlurmctldParameters=cloud_dns
        created_instance_ids.append(server.id)

    return created_instance_ids

def main():

    try:
        hostlist_expr = sys.argv[1]
        debug = True if len(sys.argv) > 2 else False
        if debug:
            logger.info(f"Running in debug mode - won't actually create nodes")
        resume(hostlist_expr, debug)
    except BaseException:
        logger.exception('Exception in main:')
        raise
