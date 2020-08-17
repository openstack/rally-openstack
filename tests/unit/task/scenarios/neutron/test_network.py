# Copyright 2014: Intel Inc.
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

from rally_openstack.task.scenarios.neutron import network
from tests.unit import test

BASE = "rally_openstack.task.scenarios.neutron.network"


@ddt.ddt
class NeutronNetworksTestCase(test.TestCase):
    def setUp(self):
        super(NeutronNetworksTestCase, self).setUp()
        patch = mock.patch("rally_openstack.common.osclients.Clients")
        self.clients = patch.start().return_value
        self.clients.credential.api_info = {}
        self.addCleanup(patch.stop)

        self.nc = self.clients.neutron.return_value
        self.context = self.get_test_context()

    @staticmethod
    def get_test_context():
        ctx = test.get_test_context()
        ctx.update(
            user_choice_method="random",
            tenants={"tenant-1": {}},
            users=[
                {
                    "tenant_id": "tenant-1",
                    "credential": {}
                }
            ]
        )
        return ctx

    @ddt.data(
        {"network_create_args": {}},
        {"network_create_args": {"admin_state_up": False}},
        {"network_create_args": {"provider:network_type": "vxlan"}}
    )
    @ddt.unpack
    def test_create_and_list_networks(self, network_create_args):
        net = {
            "id": "network-id",
            "name": "network-name",
            "admin_state_up": False
        }
        self.nc.create_network.return_value = {"network": net}

        scenario = network.CreateAndListNetworks(self.context)
        scenario.run(network_create_args=network_create_args)

        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY, **network_create_args}}
        )
        self.nc.list_networks.assert_called_once_with()

    @ddt.data(
        {"network_create_args": {}},
        {"network_create_args": {"admin_state_up": False}},
    )
    @ddt.unpack
    def test_create_and_show_network(self, network_create_args):
        net = {
            "id": "network-id",
            "name": "network-name",
            "admin_state_up": False
        }
        self.nc.create_network.return_value = {"network": net}

        scenario = network.CreateAndShowNetwork(self.context)

        scenario.run(network_create_args=network_create_args)

        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY, **network_create_args}}
        )
        self.nc.show_network.assert_called_once_with(net["id"])

    def test_create_and_update_networks(self):
        net = {
            "id": "network-id",
            "name": "network-name",
            "admin_state_up": False
        }
        self.nc.create_network.return_value = {"network": net}

        scenario = network.CreateAndUpdateNetworks(self.context)

        network_update_args = {"admin_state_up": True}

        # Default options
        scenario.run(network_update_args=network_update_args)

        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY}}
        )
        self.nc.update_network.assert_called_once_with(
            net["id"], {"network": network_update_args}
        )

        self.nc.create_network.reset_mock()
        self.nc.update_network.reset_mock()

        # admin_state_up is specified
        network_create_args = {
            "admin_state_up": False
        }

        scenario.run(network_create_args=network_create_args,
                     network_update_args=network_update_args)
        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY, **network_create_args}}
        )
        self.nc.update_network.assert_called_once_with(
            net["id"], {"network": network_update_args}
        )

    def test_create_and_delete_networks(self):
        net = {
            "id": "network-id",
            "name": "network-name",
            "admin_state_up": False
        }
        self.nc.create_network.return_value = {"network": net}

        scenario = network.CreateAndDeleteNetworks(self.context)

        # Default options
        network_create_args = {}
        scenario.run(network_create_args=network_create_args)
        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY}}
        )
        self.assertTrue(self.nc.delete_network.called)

        self.nc.create_network.reset_mock()
        self.nc.delete_network.reset_mock()

        # Explicit network name is specified
        network_create_args = {"admin_state_up": True}
        scenario.run(network_create_args=network_create_args)

        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY, **network_create_args}}
        )
        self.assertTrue(self.nc.delete_network.called)

    def test_create_and_list_subnets(self):
        network_create_args = {"router:external": True}
        subnet_create_args = {"allocation_pools": []}
        subnet_cidr_start = "10.2.0.0/24"
        subnets_per_network = 5
        net = mock.MagicMock()

        self.nc.create_network.return_value = {"network": net}
        self.nc.create_subnet.side_effect = [
            {"subnet": {"id": i}} for i in range(subnets_per_network)
        ]

        scenario = network.CreateAndListSubnets(self.context)

        scenario.run(network_create_args=network_create_args,
                     subnet_create_args=subnet_create_args,
                     subnet_cidr_start=subnet_cidr_start,
                     subnets_per_network=subnets_per_network)

        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY, **network_create_args}}
        )
        self.assertEqual(
            [mock.call({"subnet": {
                "name": mock.ANY,
                "network_id": net["id"],
                "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
                "ip_version": 4,
                "cidr": mock.ANY,
                **subnet_create_args}}
            )] * subnets_per_network,
            self.nc.create_subnet.call_args_list
        )

        self.nc.list_subnets.assert_called_once_with()

    def test_create_and_show_subnets(self):
        network_create_args = {"router:external": True}
        subnet_create_args = {"allocation_pools": []}
        subnet_cidr_start = "1.1.0.0/30"
        subnets_per_network = 5
        net = mock.MagicMock()

        self.nc.create_subnet.side_effect = [
            {"subnet": {"id": i}} for i in range(subnets_per_network)
        ]

        scenario = network.CreateAndShowSubnets(self.context)
        scenario._get_or_create_network = mock.Mock(return_value=net)

        scenario.run(network_create_args=network_create_args,
                     subnet_create_args=subnet_create_args,
                     subnet_cidr_start=subnet_cidr_start,
                     subnets_per_network=subnets_per_network)

        scenario._get_or_create_network.assert_called_once_with(
            **network_create_args)
        self.assertEqual(
            [mock.call({"subnet": {
                "name": mock.ANY,
                "network_id": net["id"],
                "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
                "ip_version": 4,
                "cidr": mock.ANY,
                **subnet_create_args}}
            )] * subnets_per_network,
            self.nc.create_subnet.call_args_list
        )
        self.assertEqual(
            [mock.call(i) for i in range(subnets_per_network)],
            self.nc.show_subnet.call_args_list
        )

    def test_set_and_clear_router_gateway(self):
        network_create_args = {"router:external": True}
        router_create_args = {"admin_state_up": True}
        enable_snat = True
        ext_net = {"id": "ext-net-1"}
        router = {"id": "router-id"}

        self.nc.create_network.return_value = {"network": ext_net}
        self.nc.create_router.return_value = {"router": router}
        self.nc.list_extensions.return_value = {
            "extensions": [{"alias": "ext-gw-mode"}]
        }

        network.SetAndClearRouterGateway(self.context).run(
            enable_snat, network_create_args, router_create_args
        )

        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY, **network_create_args}}
        )

        self.nc.create_router.assert_called_once_with(
            {"router": {"name": mock.ANY, **router_create_args}}
        )

        self.nc.add_gateway_router.assert_called_once_with(
            router["id"], {"network_id": ext_net["id"],
                           "enable_snat": enable_snat}
        )
        self.nc.remove_gateway_router.assert_called_once_with(router["id"])

    def test_create_and_update_subnets(self):
        network_create_args = {"router:external": True}
        subnet_create_args = {"allocation_pools": []}
        subnet_update_args = {"enable_dhcp": True}
        subnet_cidr_start = "1.1.0.0/30"
        subnets_per_network = 5
        net = mock.MagicMock()

        self.nc.create_network.return_value = {"network": net}
        self.nc.create_subnet.side_effect = [
            {"subnet": {"id": i}} for i in range(subnets_per_network)
        ]

        scenario = network.CreateAndUpdateSubnets(self.context)

        scenario.run(subnet_update_args,
                     network_create_args=network_create_args,
                     subnet_create_args=subnet_create_args,
                     subnet_cidr_start=subnet_cidr_start,
                     subnets_per_network=subnets_per_network)

        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY, **network_create_args}}
        )
        self.assertEqual(
            [mock.call({"subnet": {
                "name": mock.ANY,
                "network_id": net["id"],
                "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
                "ip_version": 4,
                "cidr": mock.ANY,
                **subnet_create_args}}
            )] * subnets_per_network,
            self.nc.create_subnet.call_args_list
        )
        self.assertEqual(
            [mock.call(s, {"subnet": subnet_update_args})
             for s in range(subnets_per_network)],
            self.nc.update_subnet.call_args_list
        )

    def test_create_and_delete_subnets(self):
        network_create_args = {"router:external": True}
        subnet_create_args = {"allocation_pools": []}
        subnet_cidr_start = "1.1.0.0/30"
        subnets_per_network = 5
        net = mock.MagicMock()

        self.nc.create_subnet.side_effect = [
            {"subnet": {"id": i}} for i in range(subnets_per_network)
        ]

        scenario = network.CreateAndDeleteSubnets(self.context)
        scenario._get_or_create_network = mock.Mock(return_value=net)

        scenario.run(network_create_args=network_create_args,
                     subnet_create_args=subnet_create_args,
                     subnet_cidr_start=subnet_cidr_start,
                     subnets_per_network=subnets_per_network)

        scenario._get_or_create_network.assert_called_once_with(
            **network_create_args)
        self.assertEqual(
            [mock.call({"subnet": {
                "name": mock.ANY,
                "network_id": net["id"],
                "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
                "ip_version": 4,
                "cidr": mock.ANY,
                **subnet_create_args}}
            )] * subnets_per_network,
            self.nc.create_subnet.call_args_list
        )
        self.assertEqual(
            [mock.call(s) for s in range(subnets_per_network)],
            self.nc.delete_subnet.call_args_list
        )

    def test_create_and_list_routers(self):
        network_create_args = {"router:external": True}
        subnet_create_args = {"allocation_pools": []}
        subnet_cidr_start = "1.1.0.0/30"
        subnets_per_network = 5
        router_create_args = {"admin_state_up": True}
        net = {"id": "foo"}
        self.nc.create_network.return_value = {"network": net}

        scenario = network.CreateAndListRouters(self.context)

        scenario.run(network_create_args=network_create_args,
                     subnet_create_args=subnet_create_args,
                     subnet_cidr_start=subnet_cidr_start,
                     subnets_per_network=subnets_per_network,
                     router_create_args=router_create_args)
        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY, **network_create_args}}
        )
        self.assertEqual(
            [mock.call({"subnet": {
                "name": mock.ANY,
                "network_id": net["id"],
                "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
                "ip_version": 4,
                "cidr": mock.ANY,
                **subnet_create_args}}
            )] * subnets_per_network,
            self.nc.create_subnet.call_args_list
        )
        self.assertEqual(
            [mock.call({"router": {
                "name": mock.ANY,
                **router_create_args}}
            )] * subnets_per_network,
            self.nc.create_router.call_args_list
        )
        self.nc.list_routers.assert_called_once_with()

    def test_create_and_update_routers(self):
        router_update_args = {"admin_state_up": False}
        network_create_args = {"router:external": True}
        subnet_create_args = {"allocation_pools": []}
        subnet_cidr_start = "1.1.0.0/30"
        subnets_per_network = 5
        router_create_args = {"admin_state_up": True}
        net = {"id": "foo"}
        self.nc.create_network.return_value = {"network": net}
        self.nc.create_subnet.side_effect = [
            {"subnet": {"id": i}} for i in range(subnets_per_network)
        ]
        self.nc.create_router.side_effect = [
            {"router": {"id": i}} for i in range(subnets_per_network)
        ]

        scenario = network.CreateAndUpdateRouters(self.context)

        scenario.run(router_update_args,
                     network_create_args=network_create_args,
                     subnet_create_args=subnet_create_args,
                     subnet_cidr_start=subnet_cidr_start,
                     subnets_per_network=subnets_per_network,
                     router_create_args=router_create_args)

        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY, **network_create_args}}
        )
        self.assertEqual(
            [mock.call({"subnet": {
                "name": mock.ANY,
                "network_id": net["id"],
                "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
                "ip_version": 4,
                "cidr": mock.ANY,
                **subnet_create_args}}
            )] * subnets_per_network,
            self.nc.create_subnet.call_args_list
        )
        self.assertEqual(
            [mock.call({"router": {
                "name": mock.ANY,
                **router_create_args}}
            )] * subnets_per_network,
            self.nc.create_router.call_args_list
        )
        self.assertEqual(
            [mock.call(i, {"router": router_update_args})
             for i in range(subnets_per_network)],
            self.nc.update_router.call_args_list
        )

    def test_create_and_delete_routers(self):
        network_create_args = {"router:external": True}
        subnet_create_args = {"allocation_pools": []}
        subnet_cidr_start = "1.1.0.0/30"
        subnets_per_network = 5
        router_create_args = {"admin_state_up": True}
        net = {"id": "foo"}
        self.nc.create_network.return_value = {"network": net}
        self.nc.create_subnet.side_effect = [
            {"subnet": {"id": f"s-{i}"}} for i in range(subnets_per_network)
        ]
        self.nc.create_router.side_effect = [
            {"router": {"id": f"r-{i}"}} for i in range(subnets_per_network)
        ]

        scenario = network.CreateAndDeleteRouters(self.context)

        scenario.run(network_create_args=network_create_args,
                     subnet_create_args=subnet_create_args,
                     subnet_cidr_start=subnet_cidr_start,
                     subnets_per_network=subnets_per_network,
                     router_create_args=router_create_args)

        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY, **network_create_args}}
        )
        self.assertEqual(
            [mock.call({"subnet": {
                "name": mock.ANY,
                "network_id": net["id"],
                "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
                "ip_version": 4,
                "cidr": mock.ANY,
                **subnet_create_args}}
            )] * subnets_per_network,
            self.nc.create_subnet.call_args_list
        )
        self.assertEqual(
            [mock.call({"router": {
                "name": mock.ANY,
                **router_create_args}}
            )] * subnets_per_network,
            self.nc.create_router.call_args_list
        )
        self.assertEqual(
            [mock.call(f"r-{i}", {"subnet_id": f"s-{i}"})
             for i in range(subnets_per_network)],
            self.nc.remove_interface_router.call_args_list
        )
        self.assertEqual(
            [mock.call(f"r-{i}") for i in range(subnets_per_network)],
            self.nc.delete_router.call_args_list
        )

    def test_create_and_show_routers(self):
        network_create_args = {"router:external": True}
        subnet_create_args = {"allocation_pools": []}
        subnet_cidr_start = "1.1.0.0/30"
        subnets_per_network = 5
        router_create_args = {"admin_state_up": True}
        net = {"id": "foo"}
        self.nc.create_network.return_value = {"network": net}
        self.nc.create_subnet.side_effect = [
            {"subnet": {"id": i}} for i in range(subnets_per_network)
        ]
        self.nc.create_router.side_effect = [
            {"router": {"id": i}} for i in range(subnets_per_network)
        ]

        scenario = network.CreateAndShowRouters(self.context)

        scenario.run(network_create_args=network_create_args,
                     subnet_create_args=subnet_create_args,
                     subnet_cidr_start=subnet_cidr_start,
                     subnets_per_network=subnets_per_network,
                     router_create_args=router_create_args)

        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY, **network_create_args}}
        )
        self.assertEqual(
            [mock.call({"subnet": {
                "name": mock.ANY,
                "network_id": net["id"],
                "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
                "ip_version": 4,
                "cidr": mock.ANY,
                **subnet_create_args}}
            )] * subnets_per_network,
            self.nc.create_subnet.call_args_list
        )
        self.assertEqual(
            [mock.call({"router": {
                "name": mock.ANY,
                **router_create_args}}
            )] * subnets_per_network,
            self.nc.create_router.call_args_list
        )
        self.assertEqual(
            [mock.call(i) for i in range(subnets_per_network)],
            self.nc.show_router.call_args_list
        )

    def test_list_agents(self):
        agent_args = {
            "F": "id",
            "sort-dir": "asc"
        }
        scenario = network.ListAgents(self.context)

        scenario.run(agent_args=agent_args)
        self.nc.list_agents.assert_called_once_with(**agent_args)

    def test_create_and_list_ports(self):
        port_create_args = {"allocation_pools": []}
        ports_per_network = 10
        network_create_args = {"router:external": True}
        net = mock.MagicMock()

        scenario = network.CreateAndListPorts(self.context)
        scenario._get_or_create_network = mock.Mock(return_value=net)

        scenario.run(network_create_args=network_create_args,
                     port_create_args=port_create_args,
                     ports_per_network=ports_per_network)
        scenario._get_or_create_network.assert_called_once_with(
            **network_create_args)
        self.assertEqual(
            [
                mock.call({
                    "port": {
                        "network_id": net["id"],
                        "name": mock.ANY,
                        **port_create_args
                    }
                }) for _ in range(ports_per_network)
            ],
            self.nc.create_port.call_args_list
        )

        self.nc.list_ports.assert_called_once_with()

    def test_create_and_update_ports(self):
        port_update_args = {"admin_state_up": False}
        port_create_args = {"allocation_pools": []}
        ports_per_network = 10
        network_create_args = {"router:external": True}
        net = mock.MagicMock()
        self.nc.create_port.side_effect = [
            {"port": {"id": f"p-{i}"}}
            for i in range(ports_per_network)
        ]

        scenario = network.CreateAndUpdatePorts(self.context)
        scenario._get_or_create_network = mock.Mock(return_value=net)

        scenario.run(port_update_args,
                     network_create_args=network_create_args,
                     port_create_args=port_create_args,
                     ports_per_network=ports_per_network)

        scenario._get_or_create_network.assert_called_once_with(
            **network_create_args)
        self.assertEqual(
            [mock.call({"port": {
                "network_id": net["id"],
                "name": mock.ANY,
                **port_create_args}}
            )] * ports_per_network,
            self.nc.create_port.call_args_list
        )
        self.assertEqual(
            [mock.call(f"p-{i}", {"port": port_update_args})
             for i in range(ports_per_network)],
            self.nc.update_port.call_args_list
        )

    def test_create_and_bind_ports(self):
        ports_per_network = 2
        port_update_args = {
            "device_owner": "compute:nova",
            "device_id": "ba805478-85ff-11e9-a2e4-2b8dea218fc8",
            "binding:host_id": "fake-host",
        }
        net = {"id": "net-id"}
        self.context.update({
            "tenants": {
                "tenant-1": {
                    "id": "tenant-1",
                    "networks": [
                        net
                    ],
                },
            },
            "networking_agents": [{
                "host": "fake-host",
                "alive": True,
                "admin_state_up": True,
                "agent_type": "Open vSwitch agent",
            }],
        })
        scenario = network.CreateAndBindPorts(self.context)
        scenario.admin_neutron = mock.MagicMock()

        self.nc.create_port.side_effect = [
            {"port": {"id": f"p-{i}"}}
            for i in range(ports_per_network)
        ]

        scenario.run(ports_per_network=ports_per_network)

        self.assertEqual(
            [mock.call({"port": {
                "network_id": net["id"],
                "name": mock.ANY}}
            )] * ports_per_network,
            self.nc.create_port.call_args_list
        )
        self.assertEqual(
            [mock.call(port_id=f"p-{i}", **port_update_args)
             for i in range(ports_per_network)],
            scenario.admin_neutron.update_port.call_args_list
        )

    def test_create_and_show_ports(self):
        port_create_args = {"allocation_pools": []}
        ports_per_network = 1
        network_create_args = {"router:external": True}
        net = mock.MagicMock()

        scenario = network.CreateAndShowPorts(self.context)
        scenario._get_or_create_network = mock.MagicMock(return_value=net)
        port = {"id": 1, "name": "f"}
        self.nc.create_port.return_value = {"port": port}

        scenario.run(network_create_args=network_create_args,
                     port_create_args=port_create_args,
                     ports_per_network=ports_per_network)
        scenario._get_or_create_network.assert_called_once_with(
            **network_create_args)
        self.nc.create_port.assert_called_with({"port": {
            "network_id": net["id"], "name": mock.ANY, **port_create_args
        }})

        self.nc.show_port.assert_called_with(port["id"])

    def test_create_and_delete_ports(self):
        port_create_args = {"allocation_pools": []}
        ports_per_network = 10
        network_create_args = {"router:external": True}
        net = mock.MagicMock()
        self.nc.create_port.side_effect = [
            {"port": {"id": f"p-{i}"}}
            for i in range(ports_per_network)
        ]

        scenario = network.CreateAndDeletePorts(self.context)
        scenario._get_or_create_network = mock.Mock(return_value=net)

        scenario.run(network_create_args=network_create_args,
                     port_create_args=port_create_args,
                     ports_per_network=ports_per_network)

        scenario._get_or_create_network.assert_called_once_with(
            **network_create_args)

        self.assertEqual(
            [mock.call({"port": {
                "network_id": net["id"],
                "name": mock.ANY,
                **port_create_args}}
            )] * ports_per_network,
            self.nc.create_port.call_args_list
        )
        self.assertEqual(
            [mock.call(f"p-{i}") for i in range(ports_per_network)],
            self.nc.delete_port.call_args_list
        )

    @ddt.data(
        {},
        {"floating_ip_args": {"floating_ip_address": "1.1.1.1"}},
    )
    @ddt.unpack
    def test_create_and_list_floating_ips(self, floating_ip_args=None):
        floating_ip_args = floating_ip_args or {}
        floating_network = {"id": "ext-net"}

        scenario = network.CreateAndListFloatingIps(self.context)

        self.nc.create_floatingip.return_value = {"floatingip": mock.Mock()}
        self.nc.list_floatingips.return_value = {"floatingips": mock.Mock()}
        scenario.run(floating_network=floating_network,
                     floating_ip_args=floating_ip_args)
        self.nc.create_floatingip.assert_called_once_with(
            {"floatingip": {"description": mock.ANY,
                            "floating_network_id": floating_network["id"],
                            **floating_ip_args}})
        self.nc.list_floatingips.assert_called_once_with()

    @ddt.data(
        {},
        {"floating_ip_args": {"floating_ip_address": "1.1.1.1"}},
    )
    @ddt.unpack
    def test_create_and_delete_floating_ips(self, floating_ip_args=None):
        floating_network = {"id": "ext-net"}
        floating_ip_args = floating_ip_args or {}
        floatingip = {"id": "floating-ip-id"}

        self.nc.create_floatingip.return_value = {"floatingip": floatingip}

        scenario = network.CreateAndDeleteFloatingIps(self.context)

        scenario.run(floating_network=floating_network,
                     floating_ip_args=floating_ip_args)
        self.nc.create_floatingip.assert_called_once_with(
            {"floatingip": {"description": mock.ANY,
                            "floating_network_id": floating_network["id"],
                            **floating_ip_args}})
        self.nc.delete_floatingip.assert_called_once_with(floatingip["id"])

    def test_associate_and_dissociate_floating_ips(self):
        floating_network = {
            "id": "floating-net-id",
            "name": "public",
            "router:external": True
        }
        floatingip = {"id": "floating-ip-id"}
        net = {"id": "net-id"}
        subnet = {"id": "subnet-id"}
        port = {"id": "port-id"}
        router = {"id": "router-id"}

        self.nc.create_floatingip.return_value = {"floatingip": floatingip}
        self.nc.create_network.return_value = {"network": net}
        self.nc.create_subnet.return_value = {"subnet": subnet}
        self.nc.create_port.return_value = {"port": port}
        self.nc.create_router.return_value = {"router": router}
        self.nc.list_networks.return_value = {"networks": [floating_network]}

        network.AssociateAndDissociateFloatingIps(self.context).run(
            floating_network=floating_network["name"])

        self.nc.create_floatingip.assert_called_once_with(
            {"floatingip": {"description": mock.ANY,
                            "floating_network_id": floating_network["id"]}})
        self.nc.create_network.assert_called_once_with(
            {"network": {"name": mock.ANY}}
        )
        self.nc.create_subnet.assert_called_once_with(
            {"subnet": {
                "name": mock.ANY,
                "network_id": net["id"],
                "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
                "ip_version": 4,
                "cidr": mock.ANY
            }}
        )
        self.nc.create_port.assert_called_once_with(
            {"port": {"name": mock.ANY,
                      "network_id": net["id"]}}
        )
        self.nc.add_gateway_router.assert_called_once_with(
            router["id"], {"network_id": floating_network["id"]}
        )
        self.nc.add_interface_router.assert_called_once_with(
            router["id"], {"subnet_id": subnet["id"]}
        )

        self.assertEqual(
            [
                mock.call(
                    floatingip["id"],
                    {"floatingip": {"port_id": port["id"]}}
                ),
                mock.call(
                    floatingip["id"],
                    {"floatingip": {"port_id": None}}
                )
            ],
            self.nc.update_floatingip.call_args_list
        )

    def test_delete_subnets(self):
        # do not guess what user will be used
        self.context["user_choice_method"] = "round_robin"
        # if it is the 4th iteration, the second user from the second tenant
        #   should be taken, which means that the second subnets from each
        #   tenant network should be removed.
        self.context["iteration"] = 4
        # in case of `round_robin` the user will be selected from the list of
        #   available users of particular tenant, not from the list of all
        #   tenants (i.e random choice). BUT to trigger selecting user and
        #   tenant `users` key should present in context dict
        self.context["users"] = []

        self.context["tenants"] = {
            # this should not be used
            "uuid-1": {
                "id": "uuid-1",
                "networks": [{"subnets": ["subnet-1"]}],
                "users": [{"id": "user-1", "credential": mock.MagicMock()},
                          {"id": "user-2", "credential": mock.MagicMock()}]
            },
            # this is expected user
            "uuid-2": {
                "id": "uuid-2",
                "networks": [
                    {"subnets": ["subnet-2", "subnet-3"]},
                    {"subnets": ["subnet-4", "subnet-5"]}],
                "users": [{"id": "user-3", "credential": mock.MagicMock()},
                          {"id": "user-4", "credential": mock.MagicMock()}]
            }
        }

        scenario = network.DeleteSubnets(self.context)
        self.assertEqual("user-4", scenario.context["user"]["id"],
                         "Unexpected user is taken. The wrong subnets can be "
                         "affected(removed).")

        scenario.run()

        self.assertEqual(
            [
                mock.call("subnet-3"),
                mock.call("subnet-5")
            ],
            self.nc.delete_subnet.call_args_list)
