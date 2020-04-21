# All Rights Reserved.
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

from rally_openstack.task.contexts.network import existing_network
from tests.unit import test

CTX = "rally_openstack.task.contexts.network"


class ExistingNetworkTestCase(test.TestCase):

    def setUp(self):
        super(ExistingNetworkTestCase, self).setUp()

        self.config = {"foo": "bar"}
        self.context = test.get_test_context()
        self.context.update({
            "users": [
                {"id": 1,
                 "tenant_id": "tenant1",
                 "credential": mock.Mock(tenant_name="tenant_1")},
                {"id": 2,
                 "tenant_id": "tenant2",
                 "credential": mock.Mock(tenant_name="tenant_2")},
            ],
            "tenants": {
                "tenant1": {},
                "tenant2": {},
            },
            "config": {
                "existing_network": self.config
            },
        })

    @mock.patch("rally_openstack.common.osclients.Clients")
    def test_setup(self, mock_clients):
        clients = {
            # key is tenant_name
            "tenant_1": mock.MagicMock(),
            "tenant_2": mock.MagicMock()
        }
        mock_clients.side_effect = lambda cred: clients[cred.tenant_name]

        networks = {
            # key is tenant_id
            "tenant_1": [mock.Mock(), mock.Mock()],
            "tenant_2": [mock.Mock()]
        }
        subnets = {
            # key is tenant_id
            "tenant_1": [mock.Mock()],
            "tenant_2": [mock.Mock()]
        }
        neutron1 = clients["tenant_1"].neutron.return_value
        neutron2 = clients["tenant_2"].neutron.return_value
        neutron1.list_networks.return_value = {
            "networks": networks["tenant_1"]}
        neutron2.list_networks.return_value = {
            "networks": networks["tenant_2"]}
        neutron1.list_subnets.return_value = {"subnets": subnets["tenant_1"]}
        neutron2.list_subnets.return_value = {"subnets": subnets["tenant_2"]}

        context = existing_network.ExistingNetwork(self.context)
        context.setup()

        mock_clients.assert_has_calls([
            mock.call(u["credential"]) for u in self.context["users"]])

        neutron1.list_networks.assert_called_once_with()
        neutron1.list_subnets.assert_called_once_with()
        neutron2.list_networks.assert_called_once_with()
        neutron2.list_subnets.assert_called_once_with()

        self.assertEqual(
            self.context["tenants"],
            {
                "tenant1": {"networks": networks["tenant_1"],
                            "subnets": subnets["tenant_1"]},
                "tenant2": {"networks": networks["tenant_2"],
                            "subnets": subnets["tenant_2"]},
            }
        )

    def test_cleanup(self):
        # NOTE(stpierre): Test that cleanup is not abstract
        existing_network.ExistingNetwork({"task": mock.MagicMock()}).cleanup()
