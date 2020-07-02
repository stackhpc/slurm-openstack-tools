2. Edit the ``/etc/slurm-openstack-tools/slurm-openstack-tools.conf`` file and complete the following
   actions:

   * In the ``[database]`` section, configure database access:

     .. code-block:: ini

        [database]
        ...
        connection = mysql+pymysql://slurm-openstack-tools:SLURM-OPENSTACK-TOOLS_DBPASS@controller/slurm-openstack-tools
