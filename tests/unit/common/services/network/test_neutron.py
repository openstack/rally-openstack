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

from rally import exceptions
from rally_openstack.common import credential
from rally_openstack.common.services.network import neutron
from tests.unit import test


PATH = "rally_openstack.common.services.network.neutron"


class NeutronServiceTestCase(test.TestCase):
    def setUp(self):
        super(NeutronServiceTestCase, self).setUp()
        self.clients = mock.MagicMock(
            credential=credential.OpenStackCredential(
                auth_url="example.com",
                username="root",
                password="changeme"
            )
        )
        self.nc = self.clients.neutron.return_value
        self.atomic_inst = []

        self.name_generator_count = 0

        def name_generator():
            self.name_generator_count += 1
            return f"s-{self.name_generator_count}"

        self.neutron = neutron.NeutronService(
            clients=self.clients,
            name_generator=name_generator,
            atomic_inst=self.atomic_inst
        )

    def test_create_network_topology_without_a_router(self):
        network = {"id": "net-id", "name": "s-1"}
        subnets = [
            {"id": "subnet1-id", "name": "subnet1-name"},
            {"id": "subnet2-id", "name": "subnet2-name"}
        ]
        self.nc.create_network.return_value = {"network": network.copy()}
        self.nc.create_subnet.side_effect = [{"subnet": s} for s in subnets]

        network_create_args = {}
        subnet_create_args = {}

        topo = self.neutron.create_network_topology(
            network_create_args=network_create_args,
            subnet_create_args=subnet_create_args
        )

        self.assertEqual(
            {
                "network": dict(subnets=[subnets[0]["id"]], **network),
                "subnets": [subnets[0]],
                "routers": []
            },
            topo
        )

        self.nc.create_network.assert_called_once_with(
            {"network": {"name": "s-1"}})
        self.nc.create_subnet.assert_called_once_with(
            {"subnet": {"name": "s-2", "network_id": "net-id",
                        "dns_nameservers": mock.ANY, "ip_version": 4,
                        "cidr": mock.ANY}}
        )

        self.assertFalse(self.nc.create_router.called)
        self.assertFalse(self.nc.add_interface_router.called)

    def test_create_network_topology(self):
        network = {"id": "net-id", "name": "s-1"}
        subnets = [
            {"id": "subnet1-id", "name": "subnet1-name"},
            {"id": "subnet2-id", "name": "subnet2-name"}
        ]
        router = {"id": "router"}
        self.nc.create_network.return_value = {"network": network.copy()}
        self.nc.create_router.return_value = {"router": router.copy()}
        self.nc.create_subnet.side_effect = [{"subnet": s} for s in subnets]

        network_create_args = {}
        subnet_create_args = {}

        topo = self.neutron.create_network_topology(
            network_create_args=network_create_args,
            subnet_create_args=subnet_create_args,
            router_create_args={},
            subnets_count=2,
            subnets_dualstack=True
        )

        self.assertEqual(
            {
                "network": dict(subnets=[subnets[0]["id"], subnets[1]["id"]],
                                **network),
                "subnets": [subnets[0], subnets[1]],
                "routers": [router]
            },
            topo
        )
        self.nc.create_network.assert_called_once_with(
            {"network": {"name": "s-1"}})
        self.nc.create_router.assert_called_once_with(
            {"router": {"name": "s-2"}})
        self.assertEqual(
            [
                mock.call({"subnet": {
                    "name": f"s-{i}", "network_id": "net-id",
                    "dns_nameservers": mock.ANY,
                    "ip_version": 4 if i % 3 == 0 else 6,
                    "cidr": mock.ANY}})
                for i in range(3, 5)],
            self.nc.create_subnet.call_args_list
        )
        self.assertEqual(
            [
                mock.call(router["id"], {"subnet_id": subnets[0]["id"]}),
                mock.call(router["id"], {"subnet_id": subnets[1]["id"]})
            ],
            self.nc.add_interface_router.call_args_list
        )

    def test_delete_network_topology(self):
        topo = {
            "network": {"id": "net-id"},
            "routers": [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}],
            "subnets": [{"id": "s-1"}, {"id": "s-2"}, {"id": "s-3"}]
        }
        self.nc.list_ports.return_value = {
            "ports": [
                {"id": "p1", "device_owner": "1"},
                {"id": "p2", "device_owner": "2"}
            ]
        }
        self.nc.list_subnets.return_value = {
            "subnets": [{"id": "snet-1"}, {"id": "snet-2"}]
        }

        self.neutron.delete_network_topology(topo)

        self.assertEqual(
            [mock.call(r["id"]) for r in topo["routers"]],
            self.nc.remove_gateway_router.call_args_list
        )
        self.nc.list_ports.assert_called_once_with(
            network_id=topo["network"]["id"]
        )
        self.assertEqual(
            # subnets from topo object should be ignored and all subnets should
            #   be listed
            [mock.call(s["id"])
             for s in self.nc.list_subnets.return_value["subnets"]],
            self.nc.delete_subnet.call_args_list
        )
        self.nc.delete_network.assert_called_once_with(topo["network"]["id"])
        self.assertEqual(
            [mock.call(r["id"]) for r in topo["routers"]],
            self.nc.delete_router.call_args_list
        )

    def test_create_network(self):
        net = "foo"
        self.nc.create_network.return_value = {"network": net}

        self.assertEqual(
            net,
            self.neutron.create_network(
                provider_physical_network="ppn",
                **{"router:external": True}
            )
        )
        self.nc.create_network.assert_called_once_with(
            {"network": {"name": "s-1", "provider:physical_network": "ppn",
                         "router:external": True}}
        )

    def test_get_network(self):
        network = "foo"
        self.nc.show_network.return_value = {"network": network}
        net_id = "net-id"

        self.assertEqual(network, self.neutron.get_network(net_id))
        self.nc.show_network.assert_called_once_with(net_id)

        self.nc.show_network.reset_mock()

        fields = ["a", "b"]
        self.assertEqual(network,
                         self.neutron.get_network(net_id, fields=fields))
        self.nc.show_network.assert_called_once_with(net_id, fields=fields)

    def test_find_network(self):
        net1 = {"id": "net-1", "name": "foo"}
        net2 = {"id": "net-2", "name": "bar"}
        self.nc.list_networks.return_value = {"networks": [net1, net2]}

        self.assertEqual(net2, self.neutron.find_network("bar"))
        self.assertEqual(net1, self.neutron.find_network("net-1"))
        self.assertRaises(exceptions.GetResourceFailure,
                          self.neutron.find_network, "net-3")

    def test_update_network(self):
        network = "foo"
        self.nc.update_network.return_value = {"network": network}
        net_id = "net-id"

        self.assertEqual(network, self.neutron.update_network(
            net_id, admin_state_up=False))
        self.nc.update_network.assert_called_once_with(
            net_id, {"network": {"admin_state_up": False}})

        self.nc.update_network.reset_mock()

        self.assertRaises(TypeError,
                          self.neutron.update_network, net_id)
        self.assertFalse(self.nc.update_network.called)

    def test_delete_network(self):
        net_id = "net-id"
        self.neutron.delete_network(net_id)
        self.nc.delete_network.assert_called_once_with(net_id)

    def test_list_networks(self):
        net1 = {"id": "net-1", "name": "foo"}
        net2 = {"id": "net-2", "name": "bar"}
        self.nc.list_networks.return_value = {"networks": [net1, net2]}

        self.assertEqual([net1, net2], self.neutron.list_networks())
        self.nc.list_networks.assert_called_once_with()

    @mock.patch("%s.net_utils.generate_cidr" % PATH)
    def test_create_subnet(self, mock_generate_cidr):
        net_id = "net-id"
        router_id = "router-id"
        mock_generate_cidr.return_value = (6, "generated_cidr")
        subnet = {"id": "subnet-id"}
        self.nc.create_subnet.return_value = {"subnet": subnet}

        # case 1:
        #  - cidr is not specified, so it should be generated
        #  - ip_version equals to 6, so proper dns nameserbers should be used
        #  - router_id is specified, so add_interface_router method should be
        #    called
        self.assertEqual(
            subnet,
            self.neutron.create_subnet(network_id=net_id,
                                       router_id=router_id,
                                       ip_version=6)
        )
        self.nc.create_subnet.assert_called_once_with({"subnet": {
            "name": "s-1",
            "network_id": net_id,
            "ip_version": 6,
            "cidr": "generated_cidr",
            "dns_nameservers": self.neutron.IPv6_DEFAULT_DNS_NAMESERVERS
        }})
        mock_generate_cidr.assert_called_once_with(
            ip_version=6,
            start_cidr=None
        )
        self.nc.add_interface_router.assert_called_once_with(
            router_id, {"subnet_id": subnet["id"]}
        )

        mock_generate_cidr.reset_mock()
        self.nc.create_subnet.reset_mock()
        self.nc.add_interface_router.reset_mock()

        # case 2:
        #  - cidr is specified, so it should not be generated
        #  - ip_version equals to 4, so proper dns nameserbers should be used
        #  - router_id is not specified, so add_interface_router method should
        #    not be called
        self.assertEqual(
            subnet,
            self.neutron.create_subnet(network_id=net_id,
                                       cidr="some-cidr",
                                       ip_version=4)
        )
        self.nc.create_subnet.assert_called_once_with({"subnet": {
            "name": "s-2",
            "network_id": net_id,
            "ip_version": 4,
            "cidr": "some-cidr",
            "dns_nameservers": self.neutron.IPv4_DEFAULT_DNS_NAMESERVERS
        }})
        self.assertFalse(mock_generate_cidr.called)
        self.assertFalse(self.nc.add_interface_router.called)

        mock_generate_cidr.reset_mock()
        self.nc.create_subnet.reset_mock()
        self.nc.add_interface_router.reset_mock()

        # case 3:
        #  - cidr is specified, so it should not be generated
        #  - dns_nameservers equals to None, so default values should not be
        #    applied
        #  - router_id is specified, so add_interface_router method should
        #    be called
        self.assertEqual(
            subnet,
            self.neutron.create_subnet(network_id=net_id,
                                       router_id=router_id,
                                       cidr="some-cidr",
                                       dns_nameservers=None,
                                       ip_version=4)
        )
        self.nc.create_subnet.assert_called_once_with({"subnet": {
            "name": "s-3",
            "network_id": net_id,
            "ip_version": 4,
            "cidr": "some-cidr",
            "dns_nameservers": None
        }})
        self.assertFalse(mock_generate_cidr.called)
        self.nc.add_interface_router.assert_called_once_with(
            router_id, {"subnet_id": subnet["id"]}
        )

    def test_get_subnet(self):
        subnet = "foo"
        self.nc.show_subnet.return_value = {"subnet": subnet}
        subnet_id = "subnet-id"

        self.assertEqual(subnet, self.neutron.get_subnet(subnet_id))
        self.nc.show_subnet.assert_called_once_with(subnet_id)

    def test_update_subnet(self):
        subnet = "foo"
        self.nc.update_subnet.return_value = {"subnet": subnet}
        subnet_id = "subnet-id"

        self.assertEqual(subnet, self.neutron.update_subnet(
            subnet_id, enable_dhcp=False))
        self.nc.update_subnet.assert_called_once_with(
            subnet_id, {"subnet": {"enable_dhcp": False}})

        self.nc.update_subnet.reset_mock()

        self.assertRaises(TypeError,
                          self.neutron.update_subnet, subnet_id)
        self.assertFalse(self.nc.update_subnet.called)

    def test_delete_subnet(self):
        subnet_id = "subnet-id"
        self.neutron.delete_subnet(subnet_id)
        self.nc.delete_subnet.assert_called_once_with(subnet_id)

    def test_list_subnets(self):
        subnet1 = {"id": "subnet-1", "name": "foo"}
        subnet2 = {"id": "subnet-2", "name": "bar"}
        self.nc.list_subnets.return_value = {"subnets": [subnet1, subnet2]}

        self.assertEqual([subnet1, subnet2], self.neutron.list_subnets())
        self.nc.list_subnets.assert_called_once_with()

    def test_create_router(self):
        net1 = {"id": "net-1", "name": "foo"}
        net2 = {"id": "net-2", "name": "bar"}
        self.nc.list_networks.return_value = {"networks": [net1, net2]}

        router = {"id": "router-id"}
        self.nc.create_router.return_value = {"router": router}

        # case 1: external_gateway_info is specified, list_networks should
        #   not be called
        self.assertEqual(
            router,
            self.neutron.create_router(
                external_gateway_info={"network_id": "net-id"},
                ha=True
            )
        )
        self.nc.create_router.assert_called_once_with({"router": {
            "name": "s-1",
            "external_gateway_info": {"network_id": "net-id"},
            "ha": True
        }})

        self.assertFalse(self.nc.list_networks.called)

        self.nc.create_router.reset_mock()

        # case 2: external_gateway_info is not specified, but
        #   discover_external_gw is False, so list_networks should not be
        #   called as well
        self.assertEqual(
            router,
            self.neutron.create_router(
                discover_external_gw=False,
                ha=True
            )
        )
        self.nc.create_router.assert_called_once_with({"router": {
            "name": "s-2",
            "ha": True
        }})

        self.assertFalse(self.nc.list_networks.called)

        self.nc.create_router.reset_mock()

        # case 3: external_gateway_info is not specified, so list_networks
        #   should be called to discover external network
        self.assertEqual(
            router,
            self.neutron.create_router(ha=True, discover_external_gw=True)
        )
        self.nc.create_router.assert_called_once_with({"router": {
            "name": "s-3",
            "external_gateway_info": {"network_id": net1["id"]},
            "ha": True
        }})

        self.nc.list_networks.assert_called_once_with(
            **{"router:external": True}
        )

    def test_get_router(self):
        router = "foo"
        self.nc.show_router.return_value = {"router": router}
        router_id = "router-id"

        self.assertEqual(router, self.neutron.get_router(router_id))
        self.nc.show_router.assert_called_once_with(router_id)

        self.nc.show_router.reset_mock()

        fields = ["a", "b"]
        self.assertEqual(router,
                         self.neutron.get_router(router_id, fields=fields))
        self.nc.show_router.assert_called_once_with(router_id, fields=fields)

    def test_add_interface_to_router(self):
        router_id = "router-id"
        subnet_id = "subnet-id"
        port_id = "port-id"

        self.neutron.add_interface_to_router(router_id, subnet_id=subnet_id)
        self.nc.add_interface_router.assert_called_once_with(
            router_id, {"subnet_id": subnet_id})
        self.nc.add_interface_router.reset_mock()

        self.neutron.add_interface_to_router(router_id, port_id=port_id)
        self.nc.add_interface_router.assert_called_once_with(
            router_id, {"port_id": port_id})
        self.nc.add_interface_router.reset_mock()

        self.assertRaises(TypeError,
                          self.neutron.add_interface_to_router, router_id)
        self.assertFalse(self.nc.add_interface_router.called)

        self.assertRaises(TypeError,
                          self.neutron.add_interface_to_router, router_id,
                          port_id=port_id, subnet_id=subnet_id)
        self.assertFalse(self.nc.add_interface_router.called)

    def test_remove_interface_from_router(self):
        router_id = "router-id"
        subnet_id = "subnet-id"
        port_id = "port-id"

        # case 1: use subnet-id
        self.neutron.remove_interface_from_router(
            router_id, subnet_id=subnet_id)
        self.nc.remove_interface_router.assert_called_once_with(
            router_id, {"subnet_id": subnet_id})
        self.nc.remove_interface_router.reset_mock()

        # case 2: use port-id
        self.neutron.remove_interface_from_router(router_id, port_id=port_id)
        self.nc.remove_interface_router.assert_called_once_with(
            router_id, {"port_id": port_id})
        self.nc.remove_interface_router.reset_mock()

        # case 3: no port and subnet are specified
        self.assertRaises(TypeError,
                          self.neutron.remove_interface_from_router, router_id)
        self.assertFalse(self.nc.remove_interface_router.called)

        # case 4: both port and subnet are specified
        self.assertRaises(TypeError,
                          self.neutron.remove_interface_from_router, router_id,
                          port_id=port_id, subnet_id=subnet_id)
        self.assertFalse(self.nc.remove_interface_router.called)

    def test_test_remove_interface_from_router_silent_error(self):
        from neutronclient.common import exceptions as neutron_exceptions

        router_id = "router-id"
        subnet_id = "subnet-id"

        for exc in (neutron_exceptions.BadRequest,
                    neutron_exceptions.NotFound):
            self.nc.remove_interface_router.side_effect = exc

            self.neutron.remove_interface_from_router(
                router_id, subnet_id=subnet_id)
            self.nc.remove_interface_router.assert_called_once_with(
                router_id, {"subnet_id": subnet_id})

            self.nc.remove_interface_router.reset_mock()

    def test_add_gateway_to_router(self):
        router_id = "r-id"
        net_id = "net-id"
        external_fixed_ips = "ex-net-obj"
        self.nc.list_extensions.return_value = {
            "extensions": [{"alias": "ext-gw-mode"}]
        }

        # case 1
        self.neutron.add_gateway_to_router(
            router_id,
            network_id=net_id,
            external_fixed_ips=external_fixed_ips,
            enable_snat=True
        )
        self.nc.add_gateway_router.assert_called_once_with(
            router_id, {"network_id": net_id,
                        "enable_snat": True,
                        "external_fixed_ips": external_fixed_ips})
        self.nc.add_gateway_router.reset_mock()

        # case 2
        self.neutron.add_gateway_to_router(router_id, network_id=net_id)
        self.nc.add_gateway_router.assert_called_once_with(
            router_id, {"network_id": net_id})

    def test_remove_gateway_from_router(self):
        router_id = "r-id"
        self.neutron.remove_gateway_from_router(router_id)
        self.nc.remove_gateway_router.assert_called_once_with(router_id)

    def test_update_router(self):
        router = "foo"
        self.nc.update_router.return_value = {"router": router}
        router_id = "subnet-id"

        self.assertEqual(router, self.neutron.update_router(
            router_id, admin_state_up=False))
        self.nc.update_router.assert_called_once_with(
            router_id, {"router": {"admin_state_up": False}})

        self.nc.update_router.reset_mock()

        self.assertRaises(TypeError,
                          self.neutron.update_router, router_id)
        self.assertFalse(self.nc.update_router.called)

    def test_delete_router(self):
        router_id = "r-id"
        self.neutron.delete_router(router_id)
        self.nc.delete_router.assert_called_once_with(router_id)

    def test_list_routers(self):
        router1 = {
            "id": "router-1",
            "name": "r1",
            "external_gateway_info": None
        }
        router2 = {
            "id": "router-2",
            "name": "r2",
            "external_gateway_info": {"external_fixed_ips": []}
        }
        router3 = {
            "id": "router-3",
            "name": "r3",
            "external_gateway_info": {
                "external_fixed_ips": [{"subnet_id": "s1"}]
            }
        }
        router4 = {
            "id": "router-4",
            "name": "r4",
            "external_gateway_info": {
                "external_fixed_ips": [{"subnet_id": "s1"},
                                       {"subnet_id": "s2"}]
            }
        }
        router5 = {
            "id": "router-5",
            "name": "r5",
            "external_gateway_info": {
                "external_fixed_ips": [{"subnet_id": "s2"}]
            }
        }
        self.nc.list_routers.return_value = {"routers": [
            router1, router2, router3, router4, router5]}

        # case 1: use native neutron api filters
        self.assertEqual(
            [router1, router2, router3, router4, router5],
            self.neutron.list_routers(admin_state_up=True)
        )
        self.nc.list_routers.assert_called_once_with(admin_state_up=True)

        self.nc.list_routers.reset_mock()

        # case 2: use additional post api filtering by subnet
        self.assertEqual(
            [router4, router5],
            self.neutron.list_routers(subnet_ids=["s2"])
        )
        self.nc.list_routers.assert_called_once_with()

    def test_create_port(self):
        net_id = "net-id"
        port = "foo"
        self.nc.create_port.return_value = {"port": port}

        self.assertEqual(port, self.neutron.create_port(network_id=net_id))
        self.nc.create_port.assert_called_once_with(
            {"port": {"name": "s-1", "network_id": net_id}}
        )

    def test_get_port(self):
        port = "foo"
        self.nc.show_port.return_value = {"port": port}
        port_id = "net-id"

        self.assertEqual(port, self.neutron.get_port(port_id))
        self.nc.show_port.assert_called_once_with(port_id)

        self.nc.show_port.reset_mock()

        fields = ["a", "b"]
        self.assertEqual(port,
                         self.neutron.get_port(port_id, fields=fields))
        self.nc.show_port.assert_called_once_with(port_id, fields=fields)

    def test_update_port(self):
        port = "foo"
        self.nc.update_port.return_value = {"port": port}
        port_id = "net-id"

        self.assertEqual(port, self.neutron.update_port(
            port_id, admin_state_up=False))
        self.nc.update_port.assert_called_once_with(
            port_id, {"port": {"admin_state_up": False}})

        self.nc.update_port.reset_mock()

        self.assertRaises(TypeError, self.neutron.update_port, port_id)
        self.assertFalse(self.nc.update_port.called)

    def test_delete_port(self):
        # case 1: port argument is a string with port ID
        port = "port-id"

        self.neutron.delete_port(port)

        self.nc.delete_port.assert_called_once_with(port)
        self.assertFalse(self.nc.remove_gateway_router.called)
        self.assertFalse(self.nc.remove_interface_router.called)
        self.nc.delete_port.reset_mock()

        # case 2: port argument is a dict with an id and not-special
        #   device_owner
        port = {"id": "port-id", "device_owner": "someone",
                "device_id": "device-id"}

        self.neutron.delete_port(port)

        self.nc.delete_port.assert_called_once_with(port["id"])
        self.assertFalse(self.nc.remove_interface_router.called)
        self.nc.delete_port.reset_mock()

        # case 3: port argument is a dict with an id and owner is a router
        #   interface
        port = {"id": "port-id",
                "device_id": "device-id",
                "device_owner": "network:router_interface_distributed"}

        self.neutron.delete_port(port)

        self.assertFalse(self.nc.delete_port.called)
        self.assertFalse(self.nc.remove_gateway_router.called)
        self.nc.remove_interface_router.assert_called_once_with(
            port["device_id"], {"port_id": port["id"]}
        )

        self.nc.delete_port.reset_mock()
        self.nc.remove_interface_router.reset_mock()

        # case 4: port argument is a dict with an id and owner is a router
        #   gateway
        port = {"id": "port-id",
                "device_id": "device-id",
                "device_owner": "network:router_gateway"}

        self.neutron.delete_port(port)

        self.assertFalse(self.nc.delete_port.called)
        self.nc.remove_gateway_router.assert_called_once_with(
            port["device_id"]
        )
        self.nc.remove_interface_router.assert_called_once_with(
            port["device_id"], {"port_id": port["id"]}
        )

    def test_delete_port_silently(self):
        from neutronclient.common import exceptions as neutron_exceptions

        self.nc.delete_port.side_effect = neutron_exceptions.PortNotFoundClient

        port = "port-id"

        self.neutron.delete_port(port)

        self.nc.delete_port.assert_called_once_with(port)
        self.assertFalse(self.nc.remove_gateway_router.called)
        self.assertFalse(self.nc.remove_interface_router.called)

    def test_list_ports(self):
        port1 = {"id": "port-1", "name": "foo"}
        port2 = {"id": "port-2", "name": "bar"}
        self.nc.list_ports.return_value = {"ports": [port1, port2]}

        self.assertEqual([port1, port2], self.neutron.list_ports())
        self.nc.list_ports.assert_called_once_with()

    def test_create_floatingip(self):
        floatingip = "foo"
        self.nc.create_floatingip.return_value = {"floatingip": floatingip}
        networks = [
            {"id": "net1-id", "name": "net1"},
            {"id": "net2-id", "name": "net2", "router:external": True},
            {"id": "net3-id", "name": "net3", "router:external": False}
        ]
        self.nc.list_networks.return_value = {"networks": networks}

        # case 1: floating_network is a dict with network id
        floating_network = {"id": "net-id"}

        self.assertEqual(
            floatingip,
            self.neutron.create_floatingip(floating_network=floating_network)
        )
        self.nc.create_floatingip.assert_called_once_with(
            {
                "floatingip": {"description": "s-1",
                               "floating_network_id": floating_network["id"]}
            }
        )
        self.assertFalse(self.nc.list_networks.called)
        self.nc.create_floatingip.reset_mock()

        # case 2: floating_network is an ID
        floating_network = "net2-id"

        self.assertEqual(
            floatingip,
            self.neutron.create_floatingip(floating_network=floating_network)
        )
        self.nc.create_floatingip.assert_called_once_with(
            {
                "floatingip": {"description": "s-2",
                               "floating_network_id": floating_network}
            }
        )
        self.nc.list_networks.assert_called_once_with()
        self.nc.create_floatingip.reset_mock()
        self.nc.list_networks.reset_mock()

        # case 3: floating_network is an ID
        floating_network = "net2-id"

        self.assertEqual(
            floatingip,
            self.neutron.create_floatingip(floating_network=floating_network)
        )
        self.nc.create_floatingip.assert_called_once_with(
            {
                "floatingip": {"description": "s-3",
                               "floating_network_id": floating_network}
            }
        )
        self.nc.list_networks.assert_called_once_with()
        self.nc.create_floatingip.reset_mock()
        self.nc.list_networks.reset_mock()

        # case 4: floating_network is a name of not external network
        floating_network = "net3"

        self.assertRaises(
            exceptions.NotFoundException,
            self.neutron.create_floatingip, floating_network=floating_network
        )
        self.assertFalse(self.nc.create_floatingip.called)

        self.nc.list_networks.assert_called_once_with()
        self.nc.create_floatingip.reset_mock()
        self.nc.list_networks.reset_mock()

        # case 4: floating_network is not specified
        self.assertEqual(
            floatingip,
            self.neutron.create_floatingip()
        )
        self.nc.create_floatingip.assert_called_once_with(
            {
                "floatingip": {"description": "s-4",
                               "floating_network_id": networks[0]["id"]}
            }
        )
        self.nc.list_networks.assert_called_once_with(
            **{"router:external": True})
        self.nc.create_floatingip.reset_mock()
        self.nc.list_networks.reset_mock()

    def test_create_floatingip_pre_newton(self):
        self.clients.credential.api_info["neutron"] = {"pre_newton": True}
        floatingip = "foo"
        self.nc.create_floatingip.return_value = {"floatingip": floatingip}
        floating_network = {"id": "net-id"}

        self.assertEqual(
            floatingip,
            self.neutron.create_floatingip(floating_network=floating_network)
        )
        self.nc.create_floatingip.assert_called_once_with(
            {
                "floatingip": {"floating_network_id": floating_network["id"]}
            }
        )
        # generate random name should not be called
        self.assertEqual(0, self.name_generator_count)

    @mock.patch("%s.LOG.info" % PATH)
    def test_create_floatingip_failure(self, mock_log_info):
        from neutronclient.common import exceptions as neutron_exceptions

        # case 1: an error which we should not handle
        self.nc.create_floatingip.side_effect = neutron_exceptions.BadRequest(
            "oops"
        )
        self.assertRaises(
            neutron_exceptions.BadRequest,
            self.neutron.create_floatingip, floating_network={"id": "net-id"}
        )
        self.assertFalse(mock_log_info.called)

        # case 2: exception that we should handle
        self.nc.create_floatingip.side_effect = neutron_exceptions.BadRequest(
            "Unrecognized attribute: 'description'"
        )
        self.assertRaises(
            neutron_exceptions.BadRequest,
            self.neutron.create_floatingip, floating_network={"id": "net-id"}
        )
        self.assertTrue(mock_log_info.called)

    def test_get_floatingip(self):
        floatingip = "foo"
        self.nc.show_floatingip.return_value = {"floatingip": floatingip}
        floatingip_id = "fip-id"

        self.assertEqual(floatingip,
                         self.neutron.get_floatingip(floatingip_id))
        self.nc.show_floatingip.assert_called_once_with(floatingip_id)

        self.nc.show_floatingip.reset_mock()

        fields = ["a", "b"]
        self.assertEqual(
            floatingip,
            self.neutron.get_floatingip(floatingip_id, fields=fields)
        )
        self.nc.show_floatingip.assert_called_once_with(floatingip_id,
                                                        fields=fields)

    def test_update_floatingip(self):
        floatingip = "foo"
        self.nc.update_floatingip.return_value = {"floatingip": floatingip}
        floatingip_id = "fip-id"

        self.assertEqual(floatingip, self.neutron.update_floatingip(
            floatingip_id, port_id="port-id"))
        self.nc.update_floatingip.assert_called_once_with(
            floatingip_id, {"floatingip": {"port_id": "port-id"}})

        self.nc.update_floatingip.reset_mock()

        self.assertRaises(TypeError,
                          self.neutron.update_floatingip, floatingip_id)
        self.assertFalse(self.nc.update_floatingip.called)

    def test_associate_floatingip(self):
        floatingip_id = "fip-id"
        device_id = "device-id"
        floating_ip_address = "floating_ip_address"

        floatingip = "foo"
        self.nc.update_floatingip.return_value = {"floatingip": floatingip}

        port_id = "port-id"
        self.nc.list_ports.return_value = {
            "ports": [{"id": port_id, "device_id": device_id}]
        }

        self.nc.list_floatingips.return_value = {
            "floatingips": [{"id": floatingip_id}]
        }

        # case 1:
        #   - port_id is None, so it should be discovered using device_id
        #   - floatingip_id is not None, so nothing should be specified here

        self.assertEqual(
            floatingip,
            self.neutron.associate_floatingip(
                device_id=device_id, floatingip_id=floatingip_id))
        self.nc.update_floatingip.assert_called_once_with(
            floatingip_id, {"floatingip": {"port_id": port_id}})
        self.nc.list_ports.assert_called_once_with(device_id=device_id)
        self.assertFalse(self.nc.list_floatingips.called)

        self.nc.update_floatingip.reset_mock()
        self.nc.list_ports.reset_mock()

        # case 2:
        #   - port_id is not None, so not discovery should be performed
        #   - floatingip_id is None, so it should be discovered

        self.assertEqual(
            floatingip,
            self.neutron.associate_floatingip(
                port_id=port_id, floating_ip_address=floating_ip_address,
                fixed_ip_address="fixed_ip_addr"
            ))
        self.nc.update_floatingip.assert_called_once_with(
            floatingip_id,
            {"floatingip": {"port_id": port_id,
                            "fixed_ip_address": "fixed_ip_addr"}})
        self.assertFalse(self.nc.list_ports.called)
        self.nc.list_floatingips.assert_called_once_with(
            floating_ip_address=floating_ip_address
        )

        self.nc.update_floatingip.reset_mock()
        self.nc.list_ports.reset_mock()
        self.nc.list_floatingips.reset_mock()

        # case 3:
        #   - port_id is not None, so not discovery should be performed
        #   - floatingip_id is None, so it should be discovered, but error
        #     happens

        self.nc.list_floatingips.return_value = {"floatingips": []}

        self.assertRaises(
            exceptions.GetResourceFailure,
            self.neutron.associate_floatingip,
            port_id=port_id, floating_ip_address=floating_ip_address
        )
        self.assertFalse(self.nc.update_floatingip.called)
        self.assertFalse(self.nc.list_ports.called)
        self.nc.list_floatingips.assert_called_once_with(
            floating_ip_address=floating_ip_address
        )

        self.nc.update_floatingip.reset_mock()
        self.nc.list_floatingips.reset_mock()

        # case 4:
        #   - port_id is None, so discovery should be performed, but error
        #     happens
        #   - floatingip_id is None, so discovery should not be performed
        #     since port discovery fails first

        self.nc.list_floatingips.return_value = {"floatingips": []}
        self.nc.list_ports.return_value = {"ports": []}

        self.assertRaises(
            exceptions.GetResourceFailure,
            self.neutron.associate_floatingip,
            device_id=device_id, floating_ip_address=floating_ip_address
        )
        self.nc.list_ports.assert_called_once_with(device_id=device_id)
        self.assertFalse(self.nc.update_floatingip.called)
        self.assertFalse(self.nc.list_floatingips.called)

    def test_associate_floatingip_typeerror(self):
        # no device_id and port_id
        self.assertRaises(TypeError, self.neutron.associate_floatingip)
        # both args are specified
        self.assertRaises(TypeError, self.neutron.associate_floatingip,
                          device_id="d-id", port_id="p-id")

        # no floating_ip_address and floating_ip_id
        self.assertRaises(TypeError, self.neutron.associate_floatingip,
                          port_id="p-id")
        # both args are specified
        self.assertRaises(TypeError, self.neutron.associate_floatingip,
                          port_id="p-id",
                          floating_ip_address="fip", floating_ip_id="fip_id")

    def test_disassociate_floatingip(self):
        floatingip_id = "fip-id"
        floating_ip_address = "floating_ip_address"

        floatingip = "foo"
        self.nc.update_floatingip.return_value = {"floatingip": floatingip}

        self.nc.list_floatingips.return_value = {
            "floatingips": [{"id": floatingip_id}]
        }

        # case 1: floatingip_id is specified

        self.assertEqual(
            floatingip,
            self.neutron.dissociate_floatingip(floatingip_id=floatingip_id))
        self.nc.update_floatingip.assert_called_once_with(
            floatingip_id, {"floatingip": {"port_id": None}})
        self.assertFalse(self.nc.list_floatingips.called)

        self.nc.update_floatingip.reset_mock()

        # case 2: floating_ip_address is specified

        self.assertEqual(
            floatingip,
            self.neutron.dissociate_floatingip(
                floating_ip_address=floating_ip_address
            ))
        self.nc.update_floatingip.assert_called_once_with(
            floatingip_id, {"floatingip": {"port_id": None}})
        self.nc.list_floatingips.assert_called_once_with(
            floating_ip_address=floating_ip_address
        )

        self.nc.update_floatingip.reset_mock()
        self.nc.list_floatingips.reset_mock()

        # case 3: floating_ip_address is specified but failing to
        #   find floatingip by it

        self.nc.list_floatingips.return_value = {"floatingips": []}

        self.assertRaises(
            exceptions.GetResourceFailure,
            self.neutron.dissociate_floatingip,
            floating_ip_address=floating_ip_address
        )
        self.assertFalse(self.nc.update_floatingip.called)
        self.nc.list_floatingips.assert_called_once_with(
            floating_ip_address=floating_ip_address
        )

    def test_disassociate_floatingip_typeerror(self):
        # no floating_ip_address and floating_ip_id
        self.assertRaises(TypeError, self.neutron.dissociate_floatingip)
        # both args are specified
        self.assertRaises(TypeError, self.neutron.dissociate_floatingip,
                          floating_ip_address="fip", floating_ip_id="fip_id")

    def delete_floatingip(self):
        floatingip_id = "fip-id"
        self.neutron.delete_floatingip(floatingip_id)
        self.nc.delete_floatingip.assert_called_once_with(floatingip_id)

    def test_list_floatingips(self):
        floatingip_1 = {"id": "fip-1", "name": "foo"}
        floatingip_2 = {"id": "fip-2", "name": "bar"}
        self.nc.list_floatingips.return_value = {
            "floatingips": [floatingip_1, floatingip_2]
        }

        self.assertEqual(
            [floatingip_1, floatingip_2],
            self.neutron.list_floatingips(port_id="port-id")
        )
        self.nc.list_floatingips.assert_called_once_with(port_id="port-id")

    def test_create_security_group(self):
        security_group = "foo"
        self.nc.create_security_group.return_value = {
            "security_group": security_group}

        self.assertEqual(
            security_group, self.neutron.create_security_group(stateful=True)
        )
        self.nc.create_security_group.assert_called_once_with(
            {"security_group": {"name": "s-1", "stateful": True}}
        )

    def test_get_security_group(self):
        security_group = "foo"
        self.nc.show_security_group.return_value = {
            "security_group": security_group}
        security_group_id = "security-group-id"

        self.assertEqual(security_group,
                         self.neutron.get_security_group(security_group_id))
        self.nc.show_security_group.assert_called_once_with(security_group_id)

        self.nc.show_security_group.reset_mock()

        fields = ["a", "b"]
        self.assertEqual(
            security_group,
            self.neutron.get_security_group(security_group_id, fields=fields))
        self.nc.show_security_group.assert_called_once_with(
            security_group_id, fields=fields)

    def test_update_update_security_group(self):
        security_group = "foo"
        self.nc.update_security_group.return_value = {
            "security_group": security_group}
        security_group_id = "security-group-id"

        self.assertEqual(
            security_group,
            self.neutron.update_security_group(
                security_group_id, stateful=False))
        self.nc.update_security_group.assert_called_once_with(
            security_group_id, {"security_group": {"stateful": False}})

        self.nc.update_security_group.reset_mock()

        self.assertRaises(
            TypeError,
            self.neutron.update_security_group, security_group_id)
        self.assertFalse(self.nc.update_security_group.called)

    def test_delete_security_group(self):
        security_group_id = "security-group-id"
        self.neutron.delete_security_group(security_group_id)
        self.nc.delete_security_group.assert_called_once_with(
            security_group_id)

    def test_list_security_groups(self):
        sg1 = {"id": "sg-1", "name": "foo"}
        sg2 = {"id": "sg-2", "name": "bar"}
        self.nc.list_security_groups.return_value = {
            "security_groups": [sg1, sg2]
        }

        self.assertEqual([sg1, sg2], self.neutron.list_security_groups())
        self.nc.list_security_groups.assert_called_once_with()

    def test_create_security_group_rule(self):
        security_group_rule = "foo"
        self.nc.create_security_group_rule.return_value = {
            "security_group_rule": security_group_rule}

        self.assertEqual(
            security_group_rule,
            self.neutron.create_security_group_rule(
                security_group_id="sg1", )
        )
        self.nc.create_security_group_rule.assert_called_once_with(
            {"security_group_rule": {
                "security_group_id": "sg1", "direction": "ingress",
                "protocol": "tcp"
            }}
        )

    def test_get_security_group_rule(self):
        security_group_rule = "foo"
        self.nc.show_security_group_rule.return_value = {
            "security_group_rule": security_group_rule}
        security_group_rule_id = "security-group-id"

        self.assertEqual(
            security_group_rule,
            self.neutron.get_security_group_rule(security_group_rule_id))
        self.nc.show_security_group_rule.assert_called_once_with(
            security_group_rule_id)

        self.nc.show_security_group_rule.reset_mock()

        fields = ["a", "b"]
        self.assertEqual(
            security_group_rule,
            self.neutron.get_security_group_rule(
                security_group_rule_id, fields=fields))
        self.nc.show_security_group_rule.assert_called_once_with(
            security_group_rule_id, fields=fields)

    def test_delete_security_group_rule(self):
        security_group_rule_id = "security-group-rule-id"
        self.neutron.delete_security_group_rule(security_group_rule_id)
        self.nc.delete_security_group_rule.assert_called_once_with(
            security_group_rule_id)

    def test_list_security_groups_rule(self):
        sgr1 = {"id": "sg-1", "name": "foo"}
        sgr2 = {"id": "sg-2", "name": "bar"}
        self.nc.list_security_group_rules.return_value = {
            "security_group_rules": [sgr1, sgr2]
        }

        self.assertEqual([sgr1, sgr2],
                         self.neutron.list_security_group_rules())
        self.nc.list_security_group_rules.assert_called_once_with()

    def test_list_agents(self):
        agent1 = {"id": "agent-1", "name": "foo"}
        agent2 = {"id": "agent-2", "name": "bar"}
        self.nc.list_agents.return_value = {"agents": [agent1, agent2]}

        self.assertEqual([agent1, agent2], self.neutron.list_agents())
        self.nc.list_agents.assert_called_once_with()

    def test_list_extensions(self):
        ext1 = {"alias": "foo"}
        ext2 = {"alias": "bar"}
        self.nc.list_extensions.return_value = {"extensions": [ext1, ext2]}

        self.assertEqual([ext1, ext2], self.neutron.list_extensions())
        self.nc.list_extensions.assert_called_once_with()

    def test_cached_supported_extensions(self):
        ext1 = {"alias": "foo"}
        ext2 = {"alias": "bar"}
        self.nc.list_extensions.return_value = {"extensions": [ext1, ext2]}

        self.assertEqual([ext1, ext2],
                         self.neutron.cached_supported_extensions)
        self.nc.list_extensions.assert_called_once_with()

        self.nc.list_extensions.reset_mock()
        # another try
        self.assertEqual([ext1, ext2],
                         self.neutron.cached_supported_extensions)
        self.assertFalse(self.nc.list_extensions.called)

    def test_supports_extension(self):
        ext1 = {"alias": "foo"}
        ext2 = {"alias": "bar"}
        self.nc.list_extensions.return_value = {"extensions": [ext1, ext2]}

        self.assertTrue(self.neutron.supports_extension("foo"))
        self.assertTrue(self.neutron.supports_extension("bar"))
        self.assertFalse(self.neutron.supports_extension("xxx", silent=True))
        self.assertRaises(exceptions.NotFoundException,
                          self.neutron.supports_extension, "xxx")

        # this should be called once
        self.nc.list_extensions.assert_called_once_with()
