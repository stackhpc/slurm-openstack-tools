===============================
slurm-openstack-tools
===============================

[![Build Status](https://travis-ci.com/stackhpc/slurm-openstack-tools.svg?branch=master)](https://travis-ci.com/stackhpc/slurm-openstack-tools)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Tools to manage and provide functionality for Slurm clusters on OpenStack.

* Free software: Apache license
* Source: https://github.com/stackhpc/slurm-openstack-tools
* Bugs: https://github.com/stackhpc/slurm-openstack-tools/issues


slurm-openstack-rebuild
-----------------------

Command-line tool suitable for use as Slurm's RebootProgram.

Best installed inside an virtual environment:

    python3 -m venv /opt/slurm-tools
    source /opt/slurm-tools/bin/activate
    pip install --upgrade pip
    pip install git+https://github.com/stackhpc/slurm-openstack-tools.git

You can make use of it by updating slurm.conf:

    RebootProgram=/opt/slurm-tools/bin/slurm-openstack-rebuild

For openstack nodes you can use this special reason to rebuild a node:

    scontrol reboot [ASAP] reason="rebuild image:<image_id>" [<NODES>]

Non-openstack nodes will ignore the reason, and just do a regular reboot.
If you don't specifiy the image, it will default to doing a rebuild with
the existing image. If you don't have "rebuild" at the start of your
reason, openstack nodes will do a regular reboot.
