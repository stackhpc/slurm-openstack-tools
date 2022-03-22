import subprocess

def get_slurm_conf():
    """ Return the path for Slurm's StateSaveLocation """
    scontrol = subprocess.run(
        ['scontrol', 'show', 'config'],
        stdout=subprocess.PIPE, universal_newlines=True,
        )
    config = {}
    for line in scontrol.stdout.splitlines()[1:]: # skips e.g. 'Configuration data as of 2022-03-22T09:38:28' in first item
        k, _, v = line.strip().partition('=')
        config[k.strip()] = v.strip()
    return config

def expand_nodes(hostlist_expr):
    scontrol = subprocess.run(
        ['scontrol', 'show', 'hostnames', hostlist_expr],
        stdout=subprocess.PIPE, universal_newlines=True)
    return scontrol.stdout.strip().split('\n')
