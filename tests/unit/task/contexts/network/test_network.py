# Copyright 2014: Mirantis Inc.
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
import netaddr

from rally_openstack.task.contexts.network import networks as network_context
from tests.unit import test

PATH = "rally_openstack.task.contexts.network.networks"


@ddt.ddt
class NetworkTestCase(test.TestCase):
    def get_context(self, **kwargs):
        return {"task": {"uuid": "foo_task"},
                "admin": {"credential": "foo_admin"},
                "config": {"network": kwargs},
                "users": [{"id": "foo_user", "tenant_id": "foo_tenant",
                           "credential": mock.MagicMock()},
                          {"id": "bar_user", "tenant_id": "bar_tenant",
                           "credential": mock.MagicMock()}],
                "tenants": {"foo_tenant": {"networks": [{"id": "foo_net"}]},
                            "bar_tenant": {"networks": [{"id": "bar_net"}]}}}

    def test_default_start_cidr_is_valid(self):
        netaddr.IPNetwork(network_context.Network.DEFAULT_CONFIG["start_cidr"])

    def test__init__default(self):
        context = network_context.Network(self.get_context())
        self.assertEqual(1, context.config["networks_per_tenant"])
        self.assertEqual(network_context.Network.DEFAULT_CONFIG["start_cidr"],
                         context.config["start_cidr"])

    def test__init__explicit(self):
        context = network_context.Network(
            self.get_context(start_cidr="foo_cidr", networks_per_tenant=42,
                             network_create_args={"fakearg": "fake"},
                             dns_nameservers=["1.2.3.4", "5.6.7.8"]))
        self.assertEqual(42, context.config["networks_per_tenant"])
        self.assertEqual("foo_cidr", context.config["start_cidr"])
        self.assertEqual({"fakearg": "fake"},
                         context.config["network_create_args"])
        self.assertEqual(("1.2.3.4", "5.6.7.8"),
                         context.config["dns_nameservers"])

    def test_setup(self):
        ctx = self.get_context(networks_per_tenant=1,
                               network_create_args={},
                               subnets_per_network=2,
                               dns_nameservers=None,
                               external=True)
        user = ctx["users"][0]
        nc = user["credential"].clients.return_value.neutron.return_value
        network = {"id": "net-id", "name": "s-1"}
        subnets = [
            {"id": "subnet1-id", "name": "subnet1-name"},
            {"id": "subnet2-id", "name": "subnet2-name"}
        ]
        router = {"id": "router"}
        nc.create_network.return_value = {"network": network.copy()}
        nc.create_router.return_value = {"router": router.copy()}
        nc.create_subnet.side_effect = [{"subnet": s} for s in subnets]

        network_context.Network(ctx).setup()

        ctx_data = ctx["tenants"][ctx["users"][0]["tenant_id"]]
        self.assertEqual(
            [{
                "id": network["id"],
                "name": network["name"],
                "router_id": router["id"],
                "subnets": [s["id"] for s in subnets]
            }],
            ctx_data["networks"]
        )

        nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY}})
        nc.create_router.assert_called_once_with(
            {"router": {"name": mock.ANY}})
        self.assertEqual(
            [
                mock.call({"subnet": {
                    "name": mock.ANY, "network_id": network["id"],
                    "dns_nameservers": mock.ANY,
                    "ip_version": 4,
                    "cidr": mock.ANY}})
                for i in range(2)],
            nc.create_subnet.call_args_list
        )
        self.assertEqual(
            [
                mock.call(router["id"], {"subnet_id": subnets[0]["id"]}),
                mock.call(router["id"], {"subnet_id": subnets[1]["id"]})
            ],
            nc.add_interface_router.call_args_list
        )

    def test_setup_without_router(self):
        dns_nameservers = ["1.2.3.4", "5.6.7.8"]
        ctx = self.get_context(networks_per_tenant=1,
                               network_create_args={},
                               subnets_per_network=2,
                               router=None,
                               dns_nameservers=dns_nameservers)
        user = ctx["users"][0]
        nc = user["credential"].clients.return_value.neutron.return_value
        network = {"id": "net-id", "name": "s-1"}
        subnets = [
            {"id": "subnet1-id", "name": "subnet1-name"},
            {"id": "subnet2-id", "name": "subnet2-name"}
        ]
        router = {"id": "router"}
        nc.create_network.return_value = {"network": network.copy()}
        nc.create_router.return_value = {"router": router.copy()}
        nc.create_subnet.side_effect = [{"subnet": s} for s in subnets]

        network_context.Network(ctx).setup()

        ctx_data = ctx["tenants"][ctx["users"][0]["tenant_id"]]
        self.assertEqual(
            [{
                "id": network["id"],
                "name": network["name"],
                "router_id": None,
                "subnets": [s["id"] for s in subnets]
            }],
            ctx_data["networks"]
        )

        nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY}})
        self.assertEqual(
            [
                mock.call({"subnet": {
                    "name": mock.ANY, "network_id": network["id"],
                    # rally.task.context.Context converts list to unchangeable
                    #   collection - tuple
                    "dns_nameservers": tuple(dns_nameservers),
                    "ip_version": 4,
                    "cidr": mock.ANY}})
                for i in range(2)],
            nc.create_subnet.call_args_list
        )

        self.assertFalse(nc.create_router.called)
        self.assertFalse(nc.add_interface_router.called)

    @mock.patch("%s.resource_manager.cleanup" % PATH)
    def test_cleanup(self, mock_cleanup):
        ctx = self.get_context()

        network_context.Network(ctx).cleanup()

        mock_cleanup.assert_called_once_with(
            names=["neutron.subnet", "neutron.network", "neutron.router",
                   "neutron.port"],
            superclass=network_context.Network,
            admin=ctx.get("admin"),
            users=ctx.get("users", []),
            task_id=ctx["task"]["uuid"]
        )
