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

import ddt

from rally_openstack.task.contexts.neutron import tap_services
from tests.unit import test


@ddt.ddt
class TapServicesContextTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.clients = mock.patch.object(
            tap_services.osclients, "Clients").start()
        self.client = self.clients.return_value.neutron

    def _get_context(self, **config):
        return {
            "task": {"uuid": "task-uuid"},
            "users": [
                {"credential": mock.Mock(), "tenant_id": "foo"},
                {"credential": mock.Mock(), "tenant_id": "foo"},
                {"credential": mock.Mock(), "tenant_id": "bar"},
            ],
            "config": {"tap_services": config},
            "tenants": {
                "foo": {"ports": [{"id": "foo-0"}, {"id": "foo-1"}]},
                "bar": {"ports": [{"id": "bar-0"}, {"id": "bar-1"}]},
            },
        }

    def test_setup_defaults(self):
        context = self._get_context()
        ctx = tap_services.TapServices(context)
        self.client.create_tap_service.side_effect = [
            mock.Mock(id="service-foo"), mock.Mock(id="service-bar")]

        ctx.setup()

        self.client.create_tap_service.assert_has_calls([
            mock.call(port_id="foo-0"), mock.call(port_id="bar-0")])
        self.assertEqual(2, self.client.create_tap_service.call_count)
        self.assertEqual(
            [{"id": "service-foo", "port_id": "foo-0"}],
            context["tenants"]["foo"]["tap_services"])
        self.assertEqual(
            [{"id": "service-bar", "port_id": "bar-0"}],
            context["tenants"]["bar"]["tap_services"])
        self.assertEqual(
            ctx.generate_random_name,
            self.clients.call_args.kwargs["name_generator"])
        self.client.create_port.assert_not_called()

    def test_setup_multiple_services(self):
        context = self._get_context(services_per_project=2)
        ctx = tap_services.TapServices(context)
        self.client.create_tap_service.side_effect = [
            mock.Mock(id="service-%d" % i) for i in range(4)]

        ctx.setup()

        self.client.create_tap_service.assert_has_calls([
            mock.call(port_id="foo-0"), mock.call(port_id="foo-1"),
            mock.call(port_id="bar-0"), mock.call(port_id="bar-1")])
        self.assertEqual(2, len(context["tenants"]["foo"]["tap_services"]))

    @ddt.data([], [{"id": "only-port"}])
    def test_setup_insufficient_ports(self, ports):
        context = self._get_context(services_per_project=2)
        context["tenants"]["foo"]["ports"] = ports
        ctx = tap_services.TapServices(context)

        self.assertRaises(ValueError, ctx.setup)

        self.client.create_tap_service.assert_not_called()

    def test_cleanup_partial_setup(self):
        context = self._get_context(services_per_project=2)
        ctx = tap_services.TapServices(context)
        self.client.create_tap_service.side_effect = [
            mock.Mock(id="service-0"), RuntimeError("failed")]

        self.assertRaises(RuntimeError, ctx.setup)
        ctx.cleanup()

        self.client.delete_tap_service.assert_called_once_with("service-0")

    def test_cleanup_continues_after_failure(self):
        context = self._get_context()
        context["tenants"]["foo"]["tap_services"] = [{"id": "service-0"}]
        context["tenants"]["bar"]["tap_services"] = [{"id": "service-1"}]
        self.client.delete_tap_service.side_effect = [
            RuntimeError("failed"), None]
        ctx = tap_services.TapServices(context)

        ctx.cleanup()

        self.client.delete_tap_service.assert_has_calls([
            mock.call("service-0"), mock.call("service-1")])
        self.client.delete_port.assert_not_called()

    def test_cleanup_before_setup(self):
        ctx = tap_services.TapServices(self._get_context())

        ctx.cleanup()

        self.client.delete_tap_service.assert_not_called()
