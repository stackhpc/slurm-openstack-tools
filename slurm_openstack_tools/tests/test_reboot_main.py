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

import sys
from unittest import mock

from oslotest import base

from slurm_openstack_tools import reboot


@mock.patch.object(reboot.openstack.connection, "from_config")
@mock.patch.object(reboot, "process_node")
class TestRebootMain(base.BaseTestCase):

    def _run_main(self, hostlist):
        with mock.patch.object(sys, "argv", ["reboot", hostlist]):
            with self.assertRaises(SystemExit) as cm:
                reboot.main()
        return cm.exception.code

    def test_all_nodes_succeed(self, mock_process, mock_conn):
        code = self._run_main("node-0,node-1,node-2")
        self.assertEqual(0, code)
        self.assertEqual(
            ["node-0", "node-1", "node-2"],
            [c.args[1] for c in mock_process.call_args_list],
        )

    def test_failure_does_not_skip_remaining_nodes(
        self, mock_process, mock_conn
    ):
        def _process(conn, node):
            if node == "node-0":
                raise Exception("rebuild failed")

        mock_process.side_effect = _process

        code = self._run_main("node-0,node-1,node-2")

        self.assertEqual(1, code)
        self.assertEqual(
            ["node-0", "node-1", "node-2"],
            [c.args[1] for c in mock_process.call_args_list],
        )
