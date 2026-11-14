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

from openstack.network.v2 import port as sdk_port

from rally_openstack.task.contexts.neutron import ports
from tests.unit import test


class PortsContextTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.mock_clients = mock.patch.object(
            ports.osclients, "Clients").start()
        self.neutron = self.mock_clients.return_value.neutron

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

    def test_setup_creates_ports(self):
        created = [sdk_port.Port(id=f"port-{i}") for i in range(1, 5)]
        self.neutron.create_port.side_effect = created
        expected = [port.to_dict(computed=False, original_names=True,
                                 headers=False, ignore_none=True)
                    for port in created]
        context = self._get_context(ports_per_project=2)
        ctx = ports.Ports(context)
        ctx._iterate_per_projects = mock.MagicMock(return_value=[
            (context["users"][0], "foo_tenant"),
            (context["users"][1], "bar_tenant"),
        ])

        ctx.setup()

        self.assertEqual(expected[:2],
                         context["tenants"]["foo_tenant"]["ports"])
        self.assertEqual(expected[2:],
                         context["tenants"]["bar_tenant"]["ports"])
        self.mock_clients.assert_has_calls([
            mock.call(context["users"][0]["credential"],
                      name_generator=ctx.generate_random_name,
                      atomic_inst=ctx.atomic_actions()),
            mock.call(context["users"][1]["credential"],
                      name_generator=ctx.generate_random_name,
                      atomic_inst=ctx.atomic_actions()),
        ], any_order=True)

    def test_setup_distributes_across_networks(self):
        self.neutron.create_port.side_effect = [
            sdk_port.Port(id=f"port-{i}") for i in range(1, 4)]
        context = self._get_context(ports_per_project=3)
        ctx = ports.Ports(context)
        ctx._iterate_per_projects = mock.MagicMock(return_value=[
            (context["users"][0], "foo_tenant"),
        ])

        ctx.setup()

        self.assertEqual(
            [mock.call(network_id="net-foo"),
             mock.call(network_id="net-bar"),
             mock.call(network_id="net-foo")],
            self.neutron.create_port.call_args_list)

    def test_setup_empty_networks(self):
        context = self._get_context(ports_per_project=2)
        context["tenants"]["foo_tenant"]["networks"] = []
        ctx = ports.Ports(context)
        ctx._iterate_per_projects = mock.MagicMock(return_value=[
            (context["users"][0], "foo_tenant"),
        ])

        error = self.assertRaises(ValueError, ctx.setup)

        self.assertIn("No networks found for project foo_tenant", str(error))
        self.assertIn("network@openstack", str(error))
        self.assertFalse(self.neutron.create_port.called)

    def test_cleanup(self):
        context = self._get_context()
        context["tenants"]["foo_tenant"]["ports"] = [
            {"id": "port-1"}, {"id": "port-2"}]
        context["tenants"]["bar_tenant"]["ports"] = []
        ctx = ports.Ports(context)
        ctx._iterate_per_projects = mock.MagicMock(return_value=[
            (context["users"][0], "foo_tenant"),
            (context["users"][1], "bar_tenant"),
        ])

        ctx.cleanup()

        self.assertEqual(
            [mock.call("port-1"), mock.call("port-2")],
            self.neutron.delete_port.call_args_list)

    def test_cleanup_handles_delete_failure(self):
        self.neutron.delete_port.side_effect = [Exception("gone"), None]
        context = self._get_context()
        context["tenants"]["foo_tenant"]["ports"] = [
            {"id": "port-1"}, {"id": "port-2"}]
        context["tenants"]["bar_tenant"]["ports"] = []
        ctx = ports.Ports(context)
        ctx._iterate_per_projects = mock.MagicMock(return_value=[
            (context["users"][0], "foo_tenant"),
        ])

        ctx.cleanup()

        self.assertEqual(2, self.neutron.delete_port.call_count)
