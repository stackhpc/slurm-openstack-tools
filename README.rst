===============================
slurm-openstack-tools
===============================

.. image:: https://travis-ci.com/stackhpc/slurm-openstack-tools.svg?branch=master
    :target: https://travis-ci.com/stackhpc/slurm-openstack-tools

Tools to manage and provide functionality for Slurm clusters on OpenStack.

* Free software: Apache license
* Source: https://github.com/stackhpc/slurm-openstack-tools
* Bugs: https://github.com/stackhpc/slurm-openstack-tools/issues


Setting up a virtual environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is recommended that you use this tool with a virtual environment::

    python3 -m venv /opt/slurm-tools
    source /opt/slurm-tools/bin/activate
    pip install --upgrade pip
    pip install git+https://github.com/stackhpc/slurm-openstack-tools.git


slurm-openstack-rebuild
^^^^^^^^^^^^^^^^^^^^^^^

Command-line tool suitable for use as Slurm's RebootProgram.

You can make use of it by updating slurm.conf::

    RebootProgram=/opt/slurm-tools/bin/slurm-openstack-rebuild

For openstack nodes you can use this special reason to rebuild a node::

    scontrol reboot [ASAP] reason="rebuild image:<image_id>" [<NODES>]

Non-openstack nodes will ignore the reason, and just do a regular reboot.
If you don't specifiy the image, it will default to doing a rebuild with
the existing image. If you don't have "rebuild" at the start of your
reason, openstack nodes will do a regular reboot.

slurm-stats
^^^^^^^^^^^

Command-line tool which transforms sacct output into a form that is more
amenable for importing into elasticsearch/loki.

It uses slurm's sacct to extract job stats of finished jobs. It stores the
last timestamp in a file called "lasttimestamp". This means the tool can fetch all
jobs since the last time stamp. If there is no stored timestime it defaults to
fetching all jobs since midnight.

Note: the default OpenHPC install doesn't enable the accounting service. It appears
this must be enabled before --starttime and --endtime options work as expected.

Assuming the virtualenv created above::

    rm -f lasttimestamp  # clear any old state, default to today's job
    TZ=UTC /opt/slurm-tools/bin/slurm-stats >>finished_jobs.json

For example, you would expect output a bit like this::

    tail -n2 finished_jobs.json
    {"JobID": "20", "JobIDRaw": "20", "Cluster": "linux", "Partition": "normal", "Account": "", "Group": "centos", "GID": 1000, "User": "centos", "UID": 1000, "Submit": "2020-06-23T12:43:17", "Eligible": "2020-06-23T12:43:17", "Start": "2020-06-23T12:43:21", "End": "2020-06-23T12:43:23", "Elapsed": "00:00:02", "ExitCode": "1:0", "State": "FAILED", "NNodes": 1, "NCPUS": 1, "ReqCPUS": 1, "ReqMem": "500Mc", "ReqGRES": "", "ReqTRES": "bb/datawarp=2800G,billing=1,cpu=1,mem=500M,node=1", "Timelimit": "5-00:00:00", "NodeList": "c1", "JobName": "use-perjob.sh", "AllNodes": ["c1"]}
    {"JobID": "21", "JobIDRaw": "21", "Cluster": "linux", "Partition": "normal", "Account": "", "Group": "centos", "GID": 1000, "User": "centos", "UID": 1000, "Submit": "2020-06-23T12:45:30", "Eligible": "2020-06-23T12:45:30", "Start": "2020-06-23T12:45:33", "End": "2020-06-23T12:45:35", "Elapsed": "00:00:02", "ExitCode": "1:0", "State": "FAILED", "NNodes": 1, "NCPUS": 1, "ReqCPUS": 1, "ReqMem": "500Mc", "ReqGRES": "", "ReqTRES": "bb/datawarp=2800G,billing=1,cpu=1,mem=500M,node=1", "Timelimit": "5-00:00:00", "NodeList": "c1", "JobName": "use-perjob.sh", "AllNodes": ["c1"]}

OpenDistro Setup
~~~~~~~~~~~~~~~~

Best to see the data via Elasticsearch. We used OpenDistro.

Get started here: https://opendistro.github.io/for-elasticsearch-docs/docs/install/docker/

Install FileBeat
----------------

Be sure to use the oss filebeat, e.g. https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-oss-7.7.0-x86_64.rpm

Be sure to do add something like this to filebeat config::

    setup.ilm.enabled: false
    xpack.monitoring.enabled: false
    output.elasticsearch:
    hosts: ["localhost:9200"]
    protocol: "https"
    ssl.verification_mode: none
    username: "admin"
    password: "admin"

Then execute the setup::

    sudo filebeat modules enable system
    sudo filebeat setup -e --dashboards --pipelines --template
    sudo systemctl start filebeat

To parse the files as json, add this::

    - type: log
    json.add_error_key: true
    paths:
        - '/mnt/ohpc/centos/*.json'
    fields:
        event.kind: event
    fields_under_root: true
    processors:
        - timestamp:
            field: json.End
            layouts:
            - '2006-01-02T15:04:05'
            test:
            - '2020-06-17T10:17:48'
        - timestamp:
            target_field: 'event.end'
            field: json.End
            layouts:
            - '2006-01-02T15:04:05'
            test:
            - '2020-06-17T10:17:48'
        - timestamp:
            target_field: 'event.start'
            field: json.Start
            layouts:
            - '2006-01-02T15:04:05'
            test:
            - '2020-06-17T10:17:48'
        - convert:
            fields:
            - {from: "json.NNodes", type: "integer"}
            - {from: "json.NCPUS", type: "integer"}
            - {from: "json.ElapsedRaw", type: "integer"}
