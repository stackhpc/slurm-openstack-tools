# -*- coding: utf-8 -*-

# Copyright 2010-2011 OpenStack Foundation
# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
#
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

import os
from os import path
from unittest import mock

from oslotest import base

from slurm_openstack_tools import reboot


class TestReboot(base.BaseTestCase):
    @mock.patch.object(path, "exists")
    def test_get_openstack_server_id_missing_file(self, mock_exists):
        mock_exists.return_value = False
        self.assertIsNone(reboot.get_openstack_server_id())
        mock_exists.assert_called_once_with("/var/lib/cloud/data/instance-id")

    def test_reboot_bad_input(self):
        image = reboot.get_image_from_reason("asdf")
        self.assertIsNone(image)
        image = reboot.get_image_from_reason("rebuild asdf:asdf")
        self.assertIsNone(image)
        image = reboot.get_image_from_reason("rebuild image:")
        self.assertIsNone(image)

    def test_reboot_with_image(self):
        image = reboot.get_image_from_reason("rebuild image:uuid")
        self.assertEqual("uuid", image)

    @mock.patch.object(reboot, "do_reboot")
    @mock.patch.object(reboot, "rebuild_openstack_server")
    @mock.patch.object(
        reboot, "get_reboot_reason", return_value="rebuild image:uuid"
    )
    @mock.patch.object(
        reboot, "get_openstack_server_id", return_value="server_id"
    )
    def test_rebuild_or_reboot(
        self, mock_id, mock_reason, mock_rebuild, mock_reboot
    ):
        reboot.rebuild_or_reboot()
        mock_rebuild.assert_called_once_with("server_id", "rebuild image:uuid")
        self.assertEqual(0, mock_reboot.call_count)
        mock_id.assert_called_once_with()
        mock_reason.assert_called_once_with()

    @mock.patch.object(reboot, "do_reboot")
    @mock.patch.object(reboot, "rebuild_openstack_server")
    @mock.patch.object(
        reboot, "get_reboot_reason", return_value="reboot as normal"
    )
    @mock.patch.object(
        reboot, "get_openstack_server_id", return_value="server_id"
    )
    def test_rebuild_or_reboot_does_reboot(
        self, mock_id, mock_reason, mock_rebuild, mock_reboot
    ):
        reboot.rebuild_or_reboot()
        self.assertEqual(0, mock_rebuild.call_count)
        mock_reboot.assert_called_once_with()
        mock_id.assert_called_once_with()
        mock_reason.assert_called_once_with()

    @mock.patch.object(os, "execvp")
    @mock.patch.object(
        reboot, "get_openstack_server_id", return_value=None
    )
    def test_rebuild_or_reboot_non_openstack(
        self, mock_id, mock_exec
    ):
        reboot.rebuild_or_reboot()
        mock_exec.assert_called_once_with("reboot", ["reboot"])
        mock_id.assert_called_once_with()

    @mock.patch.object(reboot, "get_rebuild_image_from_file",
                       return_value="uuid")
    def test_get_reboot_reason(self, mock_get_image):
        reason = reboot.get_reboot_reason()
        self.assertEqual("rebuild image:uuid", reason)
        mock_get_image.assert_called_once_with()
