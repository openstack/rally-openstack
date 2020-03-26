# Copyright 2019 Ericsson Software Technology
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from unittest import mock

from rally_openstack.task.contexts.network import networking_agents
from tests.unit import test

CTX = "rally_openstack.task.contexts.network"


class NetworkingAgentsTestCase(test.TestCase):

    def setUp(self):
        super(NetworkingAgentsTestCase, self).setUp()

        self.config = {}
        self.context = test.get_test_context()
        self.context.update({
            "users": [
                {"id": 1,
                 "tenant_id": "tenant1",
                 "credential": mock.Mock()},
            ],
            "admin": {
                "credential": mock.Mock(),
            },
            "config": {
                "networking_agents": self.config,
            },
        })

    @mock.patch("rally_openstack.common.osclients.Clients")
    def test_setup(self, mock_clients):
        context = networking_agents.NetworkingAgents(self.context)
        context.setup()
        mock_clients.assert_has_calls([
            mock.call().neutron().list_agents(),
        ])

    def test_cleanup(self):
        # NOTE(stpierre): Test that cleanup is not abstract
        networking_agents.NetworkingAgents(
            {"task": mock.MagicMock()}).cleanup()
