# Copyright 2013: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock

from rally_openstack import credential
from rally_openstack.scenarios.cinder import utils
from tests.unit import test


class CinderBasicTestCase(test.ScenarioTestCase):

    def _get_context(self):
        context = test.get_test_context()

        cred = credential.OpenStackCredential(auth_url="url",
                                              username="user",
                                              password="pass")
        context.update({
            "admin": {
                "id": "fake_user_id",
                "credential": cred
            },
            "user": {"id": "fake_user_id",
                     "credential": cred},
            "tenant": {"id": "fake", "name": "fake",
                       "volumes": [{"id": "uuid", "size": 1}],
                       "servers": [1]}})
        return context

    def setUp(self):
        super(CinderBasicTestCase, self).setUp()

    @mock.patch("random.choice")
    def test_get_random_server(self, mock_choice):
        basic = utils.CinderBasic(self._get_context())
        server_id = mock_choice(basic.context["tenant"]["servers"])
        return_server = basic.get_random_server()
        basic.clients("nova").servers.get.assert_called_once_with(server_id)
        self.assertEqual(basic.clients("nova").servers.get.return_value,
                         return_server)
