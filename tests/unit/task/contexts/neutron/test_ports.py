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

from unittest import mock

from rally_openstack.task.contexts.neutron import ports
from tests.unit import test


NEUTRON = ("rally_openstack.common.services.network.neutron"
           ".NeutronService")


class PortsContextTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.mock_clients = mock.patch.object(
            ports.osclients, "Clients").start()

    def _get_context(self, **kwargs):
        foo_tenant = {"networks": [{"id": "net-foo"}, {"id": "net-bar"}]}
        bar_tenant = {"networks": [{"id": "net-baz"}]}
        foo_user = {"credential": mock.Mock(), "tenant_id": "foo_tenant"}
        bar_user = {"credential": mock.Mock(), "tenant_id": "bar_tenant"}
        return {
            "task": {"uuid": "task-uuid"},
            "users": [foo_user, bar_user],
            "config": {"ports": kwargs},
            "tenants": {
                "foo_tenant": foo_tenant,
                "bar_tenant": bar_tenant,
            },
        }

    @mock.patch(NEUTRON)
    def test_setup_creates_ports(self, mock_neutron_service):
        mock_client = mock_neutron_service.return_value
        mock_client.create_port.side_effect = [
            {"id": "port-1"}, {"id": "port-2"},
            {"id": "port-3"}, {"id": "port-4"},
        ]
        context = self._get_context(ports_per_project=2)
        ctx = ports.Ports(context)
        ctx._iterate_per_tenants = mock.MagicMock(return_value=[
            (context["users"][0], "foo_tenant"),
            (context["users"][1], "bar_tenant"),
        ])

        ctx.setup()

        self.assertEqual(
            [{"id": "port-1"}, {"id": "port-2"}],
            context["tenants"]["foo_tenant"]["ports"])
        self.assertEqual(
            [{"id": "port-3"}, {"id": "port-4"}],
            context["tenants"]["bar_tenant"]["ports"])
        self.mock_clients.assert_has_calls([
            mock.call(context["users"][0]["credential"]),
            mock.call(context["users"][1]["credential"]),
        ])
        self.assertIs(
            self.mock_clients.return_value,
            mock_neutron_service.call_args.args[0])

    @mock.patch(NEUTRON)
    def test_setup_distributes_across_networks(self, mock_neutron_service):
        mock_client = mock_neutron_service.return_value
        mock_client.create_port.side_effect = [
            {"id": "port-1"}, {"id": "port-2"}, {"id": "port-3"},
        ]
        context = self._get_context(ports_per_project=3)
        ctx = ports.Ports(context)
        ctx._iterate_per_tenants = mock.MagicMock(return_value=[
            (context["users"][0], "foo_tenant"),
        ])

        ctx.setup()

        calls = mock_client.create_port.call_args_list
        self.assertEqual("net-foo", calls[0].kwargs["network_id"])
        self.assertEqual("net-bar", calls[1].kwargs["network_id"])
        self.assertEqual("net-foo", calls[2].kwargs["network_id"])

    @mock.patch(NEUTRON)
    def test_setup_empty_networks(self, mock_neutron_service):
        context = self._get_context(ports_per_project=2)
        context["tenants"]["foo_tenant"]["networks"] = []
        ctx = ports.Ports(context)
        ctx._iterate_per_tenants = mock.MagicMock(return_value=[
            (context["users"][0], "foo_tenant"),
        ])

        error = self.assertRaises(ValueError, ctx.setup)

        self.assertIn("No networks found for project foo_tenant", str(error))
        self.assertIn("network@openstack", str(error))
        mock_neutron_service.return_value.create_port.assert_not_called()

    @mock.patch(NEUTRON)
    def test_cleanup(self, mock_neutron_service):
        mock_client = mock_neutron_service.return_value
        context = self._get_context()
        context["tenants"]["foo_tenant"]["ports"] = [
            {"id": "port-1"}, {"id": "port-2"}]
        context["tenants"]["bar_tenant"]["ports"] = []
        ctx = ports.Ports(context)
        ctx._iterate_per_tenants = mock.MagicMock(return_value=[
            (context["users"][0], "foo_tenant"),
            (context["users"][1], "bar_tenant"),
        ])

        ctx.cleanup()

        mock_client.delete_port.assert_has_calls(
            [mock.call("port-1"), mock.call("port-2")])
        self.mock_clients.assert_has_calls([
            mock.call(context["users"][0]["credential"]),
            mock.call(context["users"][1]["credential"]),
        ])

    @mock.patch(NEUTRON)
    def test_cleanup_handles_delete_failure(self, mock_neutron_service):
        mock_client = mock_neutron_service.return_value
        mock_client.delete_port.side_effect = [Exception("gone"), None]
        context = self._get_context()
        context["tenants"]["foo_tenant"]["ports"] = [
            {"id": "port-1"}, {"id": "port-2"}]
        context["tenants"]["bar_tenant"]["ports"] = []
        ctx = ports.Ports(context)
        ctx._iterate_per_tenants = mock.MagicMock(return_value=[
            (context["users"][0], "foo_tenant"),
        ])

        ctx.cleanup()

        self.assertEqual(2, mock_client.delete_port.call_count)
