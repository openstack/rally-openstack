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

from openstack.network.v2 import agent as sdk_agent
from openstack.network.v2 import extension as sdk_extension
from openstack.network.v2 import floating_ip as sdk_fip
from openstack.network.v2 import network as sdk_net
from openstack.network.v2 import port as sdk_port
from openstack.network.v2 import router as sdk_router
from openstack.network.v2 import security_group as sdk_sg
from openstack.network.v2 import security_group_rule as sdk_sgr
from openstack.network.v2 import subnet as sdk_subnet

from rally import exceptions

from rally_openstack.common import credential
from rally_openstack.common.services.network import neutron
from tests.unit import test


PATH = "rally_openstack.common.services.network.neutron"


def _dict(resource):
    return resource.to_dict(
        computed=False, original_names=True, headers=False, ignore_none=True)


class NeutronServiceTestCase(test.TestCase):
    def setUp(self):
        super().setUp()
        self.clients = mock.MagicMock(
            credential=credential.OpenStackCredential(
                auth_url="example.com",
                username="root",
                password="changeme"
            )
        )
        # NeutronService now drives the openstacksdk network proxy exposed
        # through clients._conn.network rather than the legacy neutronclient.
        self.nc = self.clients._conn.network
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
        net_obj = sdk_net.Network(**network)
        subnet_objs = [sdk_subnet.Subnet(**s) for s in subnets]
        self.nc.create_network.return_value = net_obj
        self.nc.create_subnet.side_effect = list(subnet_objs)

        network_create_args = {}
        subnet_create_args = {}

        topo = self.neutron.create_network_topology(
            network_create_args=network_create_args,
            subnet_create_args=subnet_create_args
        )

        expected_network = _dict(net_obj)
        expected_network["subnets"] = [subnets[0]["id"]]
        self.assertEqual(
            {
                "network": expected_network,
                "subnets": [_dict(subnet_objs[0])],
                "routers": []
            },
            topo
        )

        self.nc.create_network.assert_called_once_with(name="s-1")
        self.nc.create_subnet.assert_called_once_with(
            name="s-2", network_id="net-id",
            dns_nameservers=mock.ANY, ip_version=4, cidr=mock.ANY)

        self.assertFalse(self.nc.create_router.called)
        self.assertFalse(self.nc.add_interface_to_router.called)

    def test_create_network_topology(self):
        network = {"id": "net-id", "name": "s-1"}
        subnets = [
            {"id": "subnet1-id", "name": "subnet1-name"},
            {"id": "subnet2-id", "name": "subnet2-name"}
        ]
        router = {"id": "router"}
        net_obj = sdk_net.Network(**network)
        router_obj = sdk_router.Router(**router)
        subnet_objs = [sdk_subnet.Subnet(**s) for s in subnets]
        self.nc.create_network.return_value = net_obj
        self.nc.create_router.return_value = router_obj
        self.nc.create_subnet.side_effect = list(subnet_objs)

        network_create_args = {}
        subnet_create_args = {}

        topo = self.neutron.create_network_topology(
            network_create_args=network_create_args,
            subnet_create_args=subnet_create_args,
            router_create_args={},
            subnets_count=2,
            subnets_dualstack=True
        )

        expected_network = _dict(net_obj)
        expected_network["subnets"] = [subnets[0]["id"], subnets[1]["id"]]
        self.assertEqual(
            {
                "network": expected_network,
                "subnets": [_dict(subnet_objs[0]), _dict(subnet_objs[1])],
                "routers": [_dict(router_obj)]
            },
            topo
        )
        self.nc.create_network.assert_called_once_with(name="s-1")
        self.nc.create_router.assert_called_once_with(name="s-2")
        self.assertEqual(
            [
                mock.call(
                    name=f"s-{i}", network_id="net-id",
                    dns_nameservers=mock.ANY,
                    ip_version=4 if i % 3 == 0 else 6,
                    cidr=mock.ANY)
                for i in range(3, 5)],
            self.nc.create_subnet.call_args_list
        )
        self.assertEqual(
            [
                mock.call(router["id"], subnet_id=subnets[0]["id"]),
                mock.call(router["id"], subnet_id=subnets[1]["id"])
            ],
            self.nc.add_interface_to_router.call_args_list
        )

    def test_delete_network_topology(self):
        topo = {
            "network": {"id": "net-id"},
            "routers": [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}],
            "subnets": [{"id": "s-1"}, {"id": "s-2"}, {"id": "s-3"}]
        }
        self.nc.ports.return_value = iter([
            sdk_port.Port(**{"id": "p1", "device_owner": "1"}),
            sdk_port.Port(**{"id": "p2", "device_owner": "2"})
        ])
        listed_subnets = [{"id": "snet-1"}, {"id": "snet-2"}]
        self.nc.subnets.return_value = iter(
            [sdk_subnet.Subnet(**s) for s in listed_subnets])

        self.neutron.delete_network_topology(topo)

        # remove_gateway_from_router -> update_router(..., None) per router
        self.assertEqual(
            [mock.call(r["id"], external_gateway_info=None)
             for r in topo["routers"]],
            self.nc.update_router.call_args_list
        )
        self.nc.ports.assert_called_once_with(
            network_id=topo["network"]["id"]
        )
        self.assertEqual(
            # subnets from topo object should be ignored and all subnets should
            #   be listed
            [mock.call(s["id"], ignore_missing=False) for s in listed_subnets],
            self.nc.delete_subnet.call_args_list
        )
        self.nc.delete_network.assert_called_once_with(
            topo["network"]["id"], ignore_missing=False)
        self.assertEqual(
            [mock.call(r["id"], ignore_missing=False)
             for r in topo["routers"]],
            self.nc.delete_router.call_args_list
        )

    def test_create_network(self):
        net = {"id": "foo"}
        net_obj = sdk_net.Network(**net)
        self.nc.create_network.return_value = net_obj

        self.assertEqual(
            _dict(net_obj),
            self.neutron.create_network(
                provider_physical_network="ppn",
                **{"router:external": True}
            )
        )
        self.nc.create_network.assert_called_once_with(
            name="s-1",
            **{"provider:physical_network": "ppn", "router:external": True}
        )

    def test_get_network(self):
        net_obj = sdk_net.Network(**{"id": "foo"})
        network = _dict(net_obj)
        self.nc.get_network.return_value = net_obj
        net_id = "net-id"

        self.assertEqual(network, self.neutron.get_network(net_id))
        self.nc.get_network.assert_called_once_with(net_id)

        self.nc.get_network.reset_mock()

        fields = ["a", "b"]
        self.assertEqual(network,
                         self.neutron.get_network(net_id, fields=fields))
        self.nc.get_network.assert_called_once_with(net_id, fields=fields)

    def test_find_network(self):
        net1 = {"id": "net-1", "name": "foo"}
        net2 = {"id": "net-2", "name": "bar"}
        net1_obj = sdk_net.Network(**net1)
        net2_obj = sdk_net.Network(**net2)

        def fake_get_network(network_id, **kwargs):
            for net, net_obj in ((net1, net1_obj), (net2, net2_obj)):
                if network_id == net["id"]:
                    return net_obj
            from openstack import exceptions as sdk_exceptions
            raise sdk_exceptions.ResourceNotFound()

        self.nc.get_network = mock.Mock(side_effect=fake_get_network)
        self.nc.networks.return_value = iter([net1_obj, net2_obj])

        # Lookup by name falls back to list_networks (get_network raises).
        self.assertEqual(_dict(net2_obj), self.neutron.find_network("bar"))
        self.nc.get_network.assert_called_once_with("bar")
        self.nc.networks.assert_called_once_with()

        self.nc.get_network.reset_mock()
        self.nc.networks.reset_mock()
        self.nc.networks.return_value = iter([net1_obj, net2_obj])

        # Lookup by id is served by get_network directly (single call).
        self.assertEqual(_dict(net1_obj),
                         self.neutron.find_network("net-1"))
        self.nc.get_network.assert_called_once_with("net-1")
        self.assertFalse(self.nc.networks.called)

        self.nc.get_network.reset_mock()
        self.nc.networks.reset_mock()
        self.nc.networks.return_value = iter([net1_obj, net2_obj])

        # Unknown id or name raises GetResourceFailure.
        self.assertRaises(exceptions.GetResourceFailure,
                          self.neutron.find_network, "net-3")

    def test_update_network(self):
        net_obj = sdk_net.Network(**{"id": "foo"})
        network = _dict(net_obj)
        self.nc.update_network.return_value = net_obj
        net_id = "net-id"

        self.assertEqual(network, self.neutron.update_network(
            net_id, admin_state_up=False))
        self.nc.update_network.assert_called_once_with(
            net_id, admin_state_up=False)

        self.nc.update_network.reset_mock()

        self.assertRaises(TypeError,
                          self.neutron.update_network, net_id)
        self.assertFalse(self.nc.update_network.called)

    def test_delete_network(self):
        net_id = "net-id"
        self.neutron.delete_network(net_id)
        self.nc.delete_network.assert_called_once_with(
            net_id, ignore_missing=False)

    def test_list_networks(self):
        net1_obj = sdk_net.Network(**{"id": "net-1", "name": "foo"})
        net2_obj = sdk_net.Network(**{"id": "net-2", "name": "bar"})
        self.nc.networks.return_value = iter([net1_obj, net2_obj])

        self.assertEqual([_dict(net1_obj), _dict(net2_obj)],
                         self.neutron.list_networks())
        self.nc.networks.assert_called_once_with()

    def test_list_networks_translates_tenant_id(self):
        net_obj = sdk_net.Network(**{"id": "net-1", "name": "foo"})
        self.nc.networks.return_value = iter([net_obj])

        # tenant_id is a legacy neutronclient filter; openstacksdk expects
        # project_id, so the service layer must translate it.
        self.assertEqual([_dict(net_obj)],
                         self.neutron.list_networks(tenant_id="proj-1"))
        self.nc.networks.assert_called_once_with(project_id="proj-1")

    def test_list_ports_translates_tenant_id(self):
        port_obj = sdk_port.Port(**{"id": "port-1", "name": "foo"})
        self.nc.ports.return_value = iter([port_obj])

        self.assertEqual([_dict(port_obj)],
                         self.neutron.list_ports(tenant_id="proj-1"))
        self.nc.ports.assert_called_once_with(project_id="proj-1")

    @mock.patch("%s.net_utils.generate_cidr" % PATH)
    def test_create_subnet(self, mock_generate_cidr):
        net_id = "net-id"
        router_id = "router-id"
        mock_generate_cidr.return_value = (6, "generated_cidr")
        subnet = {"id": "subnet-id"}
        subnet_obj = sdk_subnet.Subnet(**subnet)
        expected_subnet = _dict(subnet_obj)
        self.nc.create_subnet.return_value = subnet_obj

        # case 1:
        #  - cidr is not specified, so it should be generated
        #  - ip_version equals to 6, so proper dns nameserbers should be used
        #  - router_id is specified, so add_interface_to_router method should
        #    be called
        self.assertEqual(
            expected_subnet,
            self.neutron.create_subnet(network_id=net_id,
                                       router_id=router_id,
                                       ip_version=6)
        )
        self.nc.create_subnet.assert_called_once_with(
            name="s-1",
            network_id=net_id,
            ip_version=6,
            cidr="generated_cidr",
            dns_nameservers=self.neutron.IPv6_DEFAULT_DNS_NAMESERVERS
        )
        mock_generate_cidr.assert_called_once_with(
            ip_version=6,
            start_cidr=None
        )
        self.nc.add_interface_to_router.assert_called_once_with(
            router_id, subnet_id=subnet["id"]
        )

        mock_generate_cidr.reset_mock()
        self.nc.create_subnet.reset_mock()
        self.nc.add_interface_to_router.reset_mock()

        # case 2:
        #  - cidr is specified, so it should not be generated
        #  - ip_version equals to 4, so proper dns nameserbers should be used
        #  - router_id is not specified, so add_interface_to_router method
        #    should not be called
        self.assertEqual(
            expected_subnet,
            self.neutron.create_subnet(network_id=net_id,
                                       cidr="some-cidr",
                                       ip_version=4)
        )
        self.nc.create_subnet.assert_called_once_with(
            name="s-2",
            network_id=net_id,
            ip_version=4,
            cidr="some-cidr",
            dns_nameservers=self.neutron.IPv4_DEFAULT_DNS_NAMESERVERS
        )
        self.assertFalse(mock_generate_cidr.called)
        self.assertFalse(self.nc.add_interface_to_router.called)

        mock_generate_cidr.reset_mock()
        self.nc.create_subnet.reset_mock()
        self.nc.add_interface_to_router.reset_mock()

        # case 3:
        #  - cidr is specified, so it should not be generated
        #  - dns_nameservers equals to None, so default values should not be
        #    applied
        #  - router_id is specified, so add_interface_to_router method should
        #    be called
        self.assertEqual(
            expected_subnet,
            self.neutron.create_subnet(network_id=net_id,
                                       router_id=router_id,
                                       cidr="some-cidr",
                                       dns_nameservers=None,
                                       ip_version=4)
        )
        self.nc.create_subnet.assert_called_once_with(
            name="s-3",
            network_id=net_id,
            ip_version=4,
            cidr="some-cidr",
            dns_nameservers=None
        )
        self.assertFalse(mock_generate_cidr.called)
        self.nc.add_interface_to_router.assert_called_once_with(
            router_id, subnet_id=subnet["id"]
        )

    def test_get_subnet(self):
        subnet_obj = sdk_subnet.Subnet(**{"id": "foo"})
        subnet = _dict(subnet_obj)
        self.nc.get_subnet.return_value = subnet_obj
        subnet_id = "subnet-id"

        self.assertEqual(subnet, self.neutron.get_subnet(subnet_id))
        self.nc.get_subnet.assert_called_once_with(subnet_id)

    def test_update_subnet(self):
        subnet_obj = sdk_subnet.Subnet(**{"id": "foo"})
        subnet = _dict(subnet_obj)
        self.nc.update_subnet.return_value = subnet_obj
        subnet_id = "subnet-id"

        self.assertEqual(subnet, self.neutron.update_subnet(
            subnet_id, enable_dhcp=False))
        self.nc.update_subnet.assert_called_once_with(
            subnet_id, enable_dhcp=False)

        self.nc.update_subnet.reset_mock()

        self.assertRaises(TypeError,
                          self.neutron.update_subnet, subnet_id)
        self.assertFalse(self.nc.update_subnet.called)

    def test_delete_subnet(self):
        subnet_id = "subnet-id"
        self.neutron.delete_subnet(subnet_id)
        self.nc.delete_subnet.assert_called_once_with(
            subnet_id, ignore_missing=False)

    def test_list_subnets(self):
        subnet1_obj = sdk_subnet.Subnet(**{"id": "subnet-1", "name": "foo"})
        subnet2_obj = sdk_subnet.Subnet(**{"id": "subnet-2", "name": "bar"})
        self.nc.subnets.return_value = iter([subnet1_obj, subnet2_obj])

        self.assertEqual([_dict(subnet1_obj), _dict(subnet2_obj)],
                         self.neutron.list_subnets())
        self.nc.subnets.assert_called_once_with()

    def test_create_router(self):
        net1 = {"id": "net-1", "name": "foo"}
        net2 = {"id": "net-2", "name": "bar"}

        router_obj = sdk_router.Router(**{"id": "router-id"})
        router = _dict(router_obj)
        self.nc.create_router.return_value = router_obj

        # case 1: external_gateway_info is specified, networks should
        #   not be called
        self.assertEqual(
            router,
            self.neutron.create_router(
                external_gateway_info={"network_id": "net-id"},
                ha=True
            )
        )
        self.nc.create_router.assert_called_once_with(
            name="s-1",
            external_gateway_info={"network_id": "net-id"},
            ha=True
        )

        self.assertFalse(self.nc.networks.called)

        self.nc.create_router.reset_mock()

        # case 2: external_gateway_info is not specified, but
        #   discover_external_gw is False, so networks should not be
        #   called as well
        self.assertEqual(
            router,
            self.neutron.create_router(
                discover_external_gw=False,
                ha=True
            )
        )
        self.nc.create_router.assert_called_once_with(
            name="s-2",
            ha=True
        )

        self.assertFalse(self.nc.networks.called)

        self.nc.create_router.reset_mock()

        # case 3: external_gateway_info is not specified, so networks
        #   should be called to discover external network
        self.nc.networks.return_value = iter(
            [sdk_net.Network(**net1), sdk_net.Network(**net2)])
        self.assertEqual(
            router,
            self.neutron.create_router(ha=True, discover_external_gw=True)
        )
        self.nc.create_router.assert_called_once_with(
            name="s-3",
            external_gateway_info={"network_id": net1["id"]},
            ha=True
        )

        self.nc.networks.assert_called_once_with(
            **{"router:external": True}
        )

    def test_get_router(self):
        router_obj = sdk_router.Router(**{"id": "foo"})
        router = _dict(router_obj)
        self.nc.get_router.return_value = router_obj
        router_id = "router-id"

        self.assertEqual(router, self.neutron.get_router(router_id))
        self.nc.get_router.assert_called_once_with(router_id)

        self.nc.get_router.reset_mock()

        fields = ["a", "b"]
        self.assertEqual(router,
                         self.neutron.get_router(router_id, fields=fields))
        self.nc.get_router.assert_called_once_with(router_id, fields=fields)

    def test_add_interface_to_router(self):
        router_id = "router-id"
        subnet_id = "subnet-id"
        port_id = "port-id"

        self.neutron.add_interface_to_router(router_id, subnet_id=subnet_id)
        self.nc.add_interface_to_router.assert_called_once_with(
            router_id, subnet_id=subnet_id)
        self.nc.add_interface_to_router.reset_mock()

        self.neutron.add_interface_to_router(router_id, port_id=port_id)
        self.nc.add_interface_to_router.assert_called_once_with(
            router_id, port_id=port_id)
        self.nc.add_interface_to_router.reset_mock()

        self.assertRaises(TypeError,
                          self.neutron.add_interface_to_router, router_id)
        self.assertFalse(self.nc.add_interface_to_router.called)

        self.assertRaises(TypeError,
                          self.neutron.add_interface_to_router, router_id,
                          port_id=port_id, subnet_id=subnet_id)
        self.assertFalse(self.nc.add_interface_to_router.called)

    def test_remove_interface_from_router(self):
        router_id = "router-id"
        subnet_id = "subnet-id"
        port_id = "port-id"

        # case 1: use subnet-id
        self.neutron.remove_interface_from_router(
            router_id, subnet_id=subnet_id)
        self.nc.remove_interface_from_router.assert_called_once_with(
            router_id, subnet_id=subnet_id)
        self.nc.remove_interface_from_router.reset_mock()

        # case 2: use port-id
        self.neutron.remove_interface_from_router(router_id, port_id=port_id)
        self.nc.remove_interface_from_router.assert_called_once_with(
            router_id, port_id=port_id)
        self.nc.remove_interface_from_router.reset_mock()

        # case 3: no port and subnet are specified
        self.assertRaises(TypeError,
                          self.neutron.remove_interface_from_router, router_id)
        self.assertFalse(self.nc.remove_interface_from_router.called)

        # case 4: both port and subnet are specified
        self.assertRaises(TypeError,
                          self.neutron.remove_interface_from_router, router_id,
                          port_id=port_id, subnet_id=subnet_id)
        self.assertFalse(self.nc.remove_interface_from_router.called)

    def test_test_remove_interface_from_router_silent_error(self):
        from openstack import exceptions as sdk_exceptions

        router_id = "router-id"
        subnet_id = "subnet-id"

        for exc in (sdk_exceptions.BadRequestException,
                    sdk_exceptions.NotFoundException):
            self.nc.remove_interface_from_router.side_effect = exc

            self.neutron.remove_interface_from_router(
                router_id, subnet_id=subnet_id)
            self.nc.remove_interface_from_router.assert_called_once_with(
                router_id, subnet_id=subnet_id)

            self.nc.remove_interface_from_router.reset_mock()

    def test_add_gateway_to_router(self):
        router_id = "r-id"
        net_id = "net-id"
        external_fixed_ips = "ex-net-obj"
        self.nc.extensions.return_value = iter(
            [sdk_extension.Extension(**{"alias": "ext-gw-mode"})])

        # case 1
        self.neutron.add_gateway_to_router(
            router_id,
            network_id=net_id,
            external_fixed_ips=external_fixed_ips,
            enable_snat=True
        )
        self.nc.update_router.assert_called_once_with(
            router_id, external_gateway_info={
                "network_id": net_id,
                "enable_snat": True,
                "external_fixed_ips": external_fixed_ips})
        self.nc.update_router.reset_mock()

        # case 2
        self.neutron.add_gateway_to_router(router_id, network_id=net_id)
        self.nc.update_router.assert_called_once_with(
            router_id, external_gateway_info={"network_id": net_id})

    def test_remove_gateway_from_router(self):
        router_id = "r-id"
        self.neutron.remove_gateway_from_router(router_id)
        self.nc.update_router.assert_called_once_with(
            router_id, external_gateway_info=None)

    def test_update_router(self):
        router_obj = sdk_router.Router(**{"id": "foo"})
        router = _dict(router_obj)
        self.nc.update_router.return_value = router_obj
        router_id = "subnet-id"

        self.assertEqual(router, self.neutron.update_router(
            router_id, admin_state_up=False))
        self.nc.update_router.assert_called_once_with(
            router_id, admin_state_up=False)

        self.nc.update_router.reset_mock()

        self.assertRaises(TypeError,
                          self.neutron.update_router, router_id)
        self.assertFalse(self.nc.update_router.called)

    def test_delete_router(self):
        router_id = "r-id"
        self.neutron.delete_router(router_id)
        self.nc.delete_router.assert_called_once_with(
            router_id, ignore_missing=False)

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
        all_routers = [router1, router2, router3, router4, router5]
        router_objs = [sdk_router.Router(**r) for r in all_routers]
        expected_all = [_dict(r) for r in router_objs]

        # case 1: use native neutron api filters
        self.nc.routers.return_value = iter(router_objs)
        self.assertEqual(
            expected_all,
            self.neutron.list_routers(admin_state_up=True)
        )
        self.nc.routers.assert_called_once_with(admin_state_up=True)

        self.nc.routers.reset_mock()

        # case 2: use additional post api filtering by subnet
        self.nc.routers.return_value = iter(
            [sdk_router.Router(**r) for r in all_routers])
        self.assertEqual(
            [expected_all[3], expected_all[4]],
            self.neutron.list_routers(subnet_ids=["s2"])
        )
        self.nc.routers.assert_called_once_with()

    def test_create_port(self):
        net_id = "net-id"
        port_obj = sdk_port.Port(**{"id": "foo"})
        port = _dict(port_obj)
        self.nc.create_port.return_value = port_obj

        self.assertEqual(port, self.neutron.create_port(network_id=net_id))
        self.nc.create_port.assert_called_once_with(
            name="s-1", network_id=net_id
        )

    def test_get_port(self):
        port_obj = sdk_port.Port(**{"id": "foo"})
        port = _dict(port_obj)
        self.nc.get_port.return_value = port_obj
        port_id = "net-id"

        self.assertEqual(port, self.neutron.get_port(port_id))
        self.nc.get_port.assert_called_once_with(port_id)

        self.nc.get_port.reset_mock()

        fields = ["a", "b"]
        self.assertEqual(port,
                         self.neutron.get_port(port_id, fields=fields))
        self.nc.get_port.assert_called_once_with(port_id, fields=fields)

    def test_update_port(self):
        port_obj = sdk_port.Port(**{"id": "foo"})
        port = _dict(port_obj)
        self.nc.update_port.return_value = port_obj
        port_id = "net-id"

        self.assertEqual(port, self.neutron.update_port(
            port_id, admin_state_up=False))
        self.nc.update_port.assert_called_once_with(
            port_id, admin_state_up=False)

        self.nc.update_port.reset_mock()

        self.assertRaises(TypeError, self.neutron.update_port, port_id)
        self.assertFalse(self.nc.update_port.called)

    def test_delete_port(self):
        # case 1: port argument is a string with port ID
        port = "port-id"

        self.neutron.delete_port(port)

        self.nc.delete_port.assert_called_once_with(port, ignore_missing=False)
        self.assertFalse(self.nc.update_router.called)
        self.assertFalse(self.nc.remove_interface_from_router.called)
        self.nc.delete_port.reset_mock()

        # case 2: port argument is a dict with an id and not-special
        #   device_owner
        port = {"id": "port-id", "device_owner": "someone",
                "device_id": "device-id"}

        self.neutron.delete_port(port)

        self.nc.delete_port.assert_called_once_with(
            port["id"], ignore_missing=False)
        self.assertFalse(self.nc.remove_interface_from_router.called)
        self.nc.delete_port.reset_mock()

        # case 3: port argument is a dict with an id and owner is a router
        #   interface
        port = {"id": "port-id",
                "device_id": "device-id",
                "device_owner": "network:router_interface_distributed"}

        self.neutron.delete_port(port)

        self.assertFalse(self.nc.delete_port.called)
        self.assertFalse(self.nc.update_router.called)
        self.nc.remove_interface_from_router.assert_called_once_with(
            port["device_id"], port_id=port["id"]
        )

        self.nc.delete_port.reset_mock()
        self.nc.remove_interface_from_router.reset_mock()

        # case 4: port argument is a dict with an id and owner is a router
        #   gateway
        port = {"id": "port-id",
                "device_id": "device-id",
                "device_owner": "network:router_gateway"}

        self.neutron.delete_port(port)

        self.assertFalse(self.nc.delete_port.called)
        # remove_gateway_from_router -> update_router(..., None)
        self.nc.update_router.assert_called_once_with(
            port["device_id"], external_gateway_info=None
        )
        self.nc.remove_interface_from_router.assert_called_once_with(
            port["device_id"], port_id=port["id"]
        )

    def test_delete_port_silently(self):
        from openstack import exceptions as sdk_exceptions

        self.nc.delete_port.side_effect = sdk_exceptions.NotFoundException

        port = "port-id"

        self.assertFalse(self.neutron.delete_port(port))

        self.nc.delete_port.assert_called_once_with(port, ignore_missing=False)
        self.assertFalse(self.nc.update_router.called)
        self.assertFalse(self.nc.remove_interface_from_router.called)

    def test_list_ports(self):
        port1_obj = sdk_port.Port(**{"id": "port-1", "name": "foo"})
        port2_obj = sdk_port.Port(**{"id": "port-2", "name": "bar"})
        self.nc.ports.return_value = iter([port1_obj, port2_obj])

        self.assertEqual([_dict(port1_obj), _dict(port2_obj)],
                         self.neutron.list_ports())
        self.nc.ports.assert_called_once_with()

    def test_create_floatingip(self):
        fip_obj = sdk_fip.FloatingIP(**{"id": "foo"})
        floatingip = _dict(fip_obj)
        self.nc.create_ip.return_value = fip_obj
        networks = [
            {"id": "net1-id", "name": "net1"},
            {"id": "net2-id", "name": "net2", "router:external": True},
            {"id": "net3-id", "name": "net3", "router:external": False}
        ]

        def fake_get_network(network_id, **kwargs):
            for net in networks:
                if network_id == net["id"]:
                    return sdk_net.Network(**net)
            from openstack import exceptions as sdk_exceptions
            raise sdk_exceptions.ResourceNotFound()

        def fake_networks(**filters):
            # find_network falls back to an unfiltered list_networks when the
            # identifier is a name; create_floatingip (no network) filters on
            # router:external.
            nets = networks
            if filters.get("router:external"):
                nets = [n for n in networks if n.get("router:external")]
            return iter([sdk_net.Network(**net) for net in nets])

        self.nc.get_network = mock.Mock(side_effect=fake_get_network)
        self.nc.networks = mock.Mock(side_effect=fake_networks)

        # case 1: floating_network is a dict with network id
        floating_network = {"id": "net-id"}

        self.assertEqual(
            floatingip,
            self.neutron.create_floatingip(floating_network=floating_network)
        )
        self.nc.create_ip.assert_called_once_with(
            description="s-1",
            floating_network_id=floating_network["id"]
        )
        self.assertFalse(self.nc.get_network.called)
        self.assertFalse(self.nc.networks.called)
        self.nc.create_ip.reset_mock()

        # case 2: floating_network is an external network name
        floating_network = "net2"

        self.assertEqual(
            floatingip,
            self.neutron.create_floatingip(floating_network=floating_network)
        )
        self.nc.create_ip.assert_called_once_with(
            description="s-2",
            floating_network_id="net2-id"
        )
        # Name lookup: get_network raises, then list_networks resolves it.
        self.nc.get_network.assert_called_once_with(floating_network)
        self.nc.networks.assert_called_once_with()
        self.nc.create_ip.reset_mock()
        self.nc.get_network.reset_mock()
        self.nc.networks.reset_mock()

        # case 3: floating_network is an external network name again
        floating_network = "net2"

        self.assertEqual(
            floatingip,
            self.neutron.create_floatingip(floating_network=floating_network)
        )
        self.nc.create_ip.assert_called_once_with(
            description="s-3",
            floating_network_id="net2-id"
        )
        self.nc.get_network.assert_called_once_with(floating_network)
        self.nc.networks.assert_called_once_with()
        self.nc.create_ip.reset_mock()
        self.nc.get_network.reset_mock()
        self.nc.networks.reset_mock()

        # case 4: floating_network is a name of not external network
        floating_network = "net3"

        self.assertRaises(
            exceptions.NotFoundException,
            self.neutron.create_floatingip, floating_network=floating_network
        )
        self.assertFalse(self.nc.create_ip.called)

        self.nc.get_network.assert_called_once_with(floating_network)
        self.nc.networks.assert_called_once_with()
        self.nc.create_ip.reset_mock()
        self.nc.get_network.reset_mock()
        self.nc.networks.reset_mock()

        # case 5: floating_network is not specified
        self.assertEqual(
            floatingip,
            self.neutron.create_floatingip()
        )
        self.nc.create_ip.assert_called_once_with(
            description="s-4",
            floating_network_id=networks[1]["id"]
        )
        self.nc.networks.assert_called_once_with(
            **{"router:external": True})
        self.nc.create_ip.reset_mock()
        self.nc.networks.reset_mock()

    def test_create_floatingip_pre_newton(self):
        self.clients.credential.api_info["neutron"] = {"pre_newton": True}
        fip_obj = sdk_fip.FloatingIP(**{"id": "foo"})
        floatingip = _dict(fip_obj)
        self.nc.create_ip.return_value = fip_obj
        floating_network = {"id": "net-id"}

        self.assertEqual(
            floatingip,
            self.neutron.create_floatingip(floating_network=floating_network)
        )
        self.nc.create_ip.assert_called_once_with(
            floating_network_id=floating_network["id"]
        )
        # generate random name should not be called
        self.assertEqual(0, self.name_generator_count)

    @mock.patch("%s.LOG.info" % PATH)
    def test_create_floatingip_failure(self, mock_log_info):
        from openstack import exceptions as sdk_exceptions

        # case 1: an error which we should not handle
        self.nc.create_ip.side_effect = sdk_exceptions.BadRequestException(
            "oops"
        )
        self.assertRaises(
            sdk_exceptions.BadRequestException,
            self.neutron.create_floatingip, floating_network={"id": "net-id"}
        )
        self.assertFalse(mock_log_info.called)

        # case 2: exception that we should handle
        self.nc.create_ip.side_effect = sdk_exceptions.BadRequestException(
            "Unrecognized attribute: 'description'"
        )
        self.assertRaises(
            sdk_exceptions.BadRequestException,
            self.neutron.create_floatingip, floating_network={"id": "net-id"}
        )
        self.assertTrue(mock_log_info.called)

    def test_get_floatingip(self):
        fip_obj = sdk_fip.FloatingIP(**{"id": "foo"})
        floatingip = _dict(fip_obj)
        self.nc.get_ip.return_value = fip_obj
        floatingip_id = "fip-id"

        self.assertEqual(floatingip,
                         self.neutron.get_floatingip(floatingip_id))
        self.nc.get_ip.assert_called_once_with(floatingip_id)

        self.nc.get_ip.reset_mock()

        fields = ["a", "b"]
        self.assertEqual(
            floatingip,
            self.neutron.get_floatingip(floatingip_id, fields=fields)
        )
        self.nc.get_ip.assert_called_once_with(floatingip_id, fields=fields)

    def test_update_floatingip(self):
        fip_obj = sdk_fip.FloatingIP(**{"id": "foo"})
        floatingip = _dict(fip_obj)
        self.nc.update_ip.return_value = fip_obj
        floatingip_id = "fip-id"

        self.assertEqual(floatingip, self.neutron.update_floatingip(
            floatingip_id, port_id="port-id"))
        self.nc.update_ip.assert_called_once_with(
            floatingip_id, port_id="port-id")

        self.nc.update_ip.reset_mock()

        self.assertRaises(TypeError,
                          self.neutron.update_floatingip, floatingip_id)
        self.assertFalse(self.nc.update_ip.called)

    def test_associate_floatingip(self):
        floatingip_id = "fip-id"
        device_id = "device-id"
        floating_ip_address = "floating_ip_address"

        fip_obj = sdk_fip.FloatingIP(**{"id": "foo"})
        floatingip = _dict(fip_obj)
        self.nc.update_ip.return_value = fip_obj

        port_id = "port-id"

        # case 1:
        #   - port_id is None, so it should be discovered using device_id
        #   - floatingip_id is not None, so nothing should be specified here
        self.nc.ports.return_value = iter(
            [sdk_port.Port(**{"id": port_id, "device_id": device_id})])
        self.nc.ips.return_value = iter(
            [sdk_fip.FloatingIP(**{"id": floatingip_id})])

        self.assertEqual(
            floatingip,
            self.neutron.associate_floatingip(
                device_id=device_id, floatingip_id=floatingip_id))
        self.nc.update_ip.assert_called_once_with(
            floatingip_id, port_id=port_id)
        self.nc.ports.assert_called_once_with(device_id=device_id)
        self.assertFalse(self.nc.ips.called)

        self.nc.update_ip.reset_mock()
        self.nc.ports.reset_mock()

        # case 2:
        #   - port_id is not None, so not discovery should be performed
        #   - floatingip_id is None, so it should be discovered
        self.nc.ips.return_value = iter(
            [sdk_fip.FloatingIP(**{"id": floatingip_id})])

        self.assertEqual(
            floatingip,
            self.neutron.associate_floatingip(
                port_id=port_id, floating_ip_address=floating_ip_address,
                fixed_ip_address="fixed_ip_addr"
            ))
        self.nc.update_ip.assert_called_once_with(
            floatingip_id, port_id=port_id,
            fixed_ip_address="fixed_ip_addr")
        self.assertFalse(self.nc.ports.called)
        self.nc.ips.assert_called_once_with(
            floating_ip_address=floating_ip_address
        )

        self.nc.update_ip.reset_mock()
        self.nc.ports.reset_mock()
        self.nc.ips.reset_mock()

        # case 3:
        #   - port_id is not None, so not discovery should be performed
        #   - floatingip_id is None, so it should be discovered, but error
        #     happens
        self.nc.ips.return_value = iter([])

        self.assertRaises(
            exceptions.GetResourceFailure,
            self.neutron.associate_floatingip,
            port_id=port_id, floating_ip_address=floating_ip_address
        )
        self.assertFalse(self.nc.update_ip.called)
        self.assertFalse(self.nc.ports.called)
        self.nc.ips.assert_called_once_with(
            floating_ip_address=floating_ip_address
        )

        self.nc.update_ip.reset_mock()
        self.nc.ips.reset_mock()

        # case 4:
        #   - port_id is None, so discovery should be performed, but error
        #     happens
        #   - floatingip_id is None, so discovery should not be performed
        #     since port discovery fails first
        self.nc.ips.return_value = iter([])
        self.nc.ports.return_value = iter([])

        self.assertRaises(
            exceptions.GetResourceFailure,
            self.neutron.associate_floatingip,
            device_id=device_id, floating_ip_address=floating_ip_address
        )
        self.nc.ports.assert_called_once_with(device_id=device_id)
        self.assertFalse(self.nc.update_ip.called)
        self.assertFalse(self.nc.ips.called)

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

        fip_obj = sdk_fip.FloatingIP(**{"id": "foo"})
        floatingip = _dict(fip_obj)
        self.nc.update_ip.return_value = fip_obj

        # case 1: floatingip_id is specified
        self.assertEqual(
            floatingip,
            self.neutron.dissociate_floatingip(floatingip_id=floatingip_id))
        self.nc.update_ip.assert_called_once_with(
            floatingip_id, port_id=None)
        self.assertFalse(self.nc.ips.called)

        self.nc.update_ip.reset_mock()

        # case 2: floating_ip_address is specified
        self.nc.ips.return_value = iter(
            [sdk_fip.FloatingIP(**{"id": floatingip_id})])

        self.assertEqual(
            floatingip,
            self.neutron.dissociate_floatingip(
                floating_ip_address=floating_ip_address
            ))
        self.nc.update_ip.assert_called_once_with(
            floatingip_id, port_id=None)
        self.nc.ips.assert_called_once_with(
            floating_ip_address=floating_ip_address
        )

        self.nc.update_ip.reset_mock()
        self.nc.ips.reset_mock()

        # case 3: floating_ip_address is specified but failing to
        #   find floatingip by it
        self.nc.ips.return_value = iter([])

        self.assertRaises(
            exceptions.GetResourceFailure,
            self.neutron.dissociate_floatingip,
            floating_ip_address=floating_ip_address
        )
        self.assertFalse(self.nc.update_ip.called)
        self.nc.ips.assert_called_once_with(
            floating_ip_address=floating_ip_address
        )

    def test_disassociate_floatingip_typeerror(self):
        # no floating_ip_address and floating_ip_id
        self.assertRaises(TypeError, self.neutron.dissociate_floatingip)
        # both args are specified
        self.assertRaises(TypeError, self.neutron.dissociate_floatingip,
                          floating_ip_address="fip", floating_ip_id="fip_id")

    def test_delete_floatingip(self):
        floatingip_id = "fip-id"
        self.neutron.delete_floatingip(floatingip_id)
        self.nc.delete_ip.assert_called_once_with(
            floatingip_id, ignore_missing=False)

    def test_list_floatingips(self):
        fip1_obj = sdk_fip.FloatingIP(**{"id": "fip-1", "name": "foo"})
        fip2_obj = sdk_fip.FloatingIP(**{"id": "fip-2", "name": "bar"})
        self.nc.ips.return_value = iter([fip1_obj, fip2_obj])

        self.assertEqual(
            [_dict(fip1_obj), _dict(fip2_obj)],
            self.neutron.list_floatingips(port_id="port-id")
        )
        self.nc.ips.assert_called_once_with(port_id="port-id")

    def test_create_security_group(self):
        sg_obj = sdk_sg.SecurityGroup(**{"id": "foo"})
        security_group = _dict(sg_obj)
        self.nc.create_security_group.return_value = sg_obj

        self.assertEqual(
            security_group, self.neutron.create_security_group(stateful=True)
        )
        self.nc.create_security_group.assert_called_once_with(
            name="s-1", stateful=True
        )

    def test_get_security_group(self):
        sg_obj = sdk_sg.SecurityGroup(**{"id": "foo"})
        security_group = _dict(sg_obj)
        self.nc.get_security_group.return_value = sg_obj
        security_group_id = "security-group-id"

        self.assertEqual(security_group,
                         self.neutron.get_security_group(security_group_id))
        self.nc.get_security_group.assert_called_once_with(security_group_id)

        self.nc.get_security_group.reset_mock()

        fields = ["a", "b"]
        self.assertEqual(
            security_group,
            self.neutron.get_security_group(security_group_id, fields=fields))
        self.nc.get_security_group.assert_called_once_with(
            security_group_id, fields=fields)

    def test_update_update_security_group(self):
        sg_obj = sdk_sg.SecurityGroup(**{"id": "foo"})
        security_group = _dict(sg_obj)
        self.nc.update_security_group.return_value = sg_obj
        security_group_id = "security-group-id"

        self.assertEqual(
            security_group,
            self.neutron.update_security_group(
                security_group_id, stateful=False))
        self.nc.update_security_group.assert_called_once_with(
            security_group_id, stateful=False)

        self.nc.update_security_group.reset_mock()

        self.assertRaises(
            TypeError,
            self.neutron.update_security_group, security_group_id)
        self.assertFalse(self.nc.update_security_group.called)

    def test_delete_security_group(self):
        security_group_id = "security-group-id"
        self.neutron.delete_security_group(security_group_id)
        self.nc.delete_security_group.assert_called_once_with(
            security_group_id, ignore_missing=False)

    def test_list_security_groups(self):
        sg1_obj = sdk_sg.SecurityGroup(**{"id": "sg-1", "name": "foo"})
        sg2_obj = sdk_sg.SecurityGroup(**{"id": "sg-2", "name": "bar"})
        self.nc.security_groups.return_value = iter([sg1_obj, sg2_obj])

        self.assertEqual([_dict(sg1_obj), _dict(sg2_obj)],
                         self.neutron.list_security_groups())
        self.nc.security_groups.assert_called_once_with()

    def test_create_security_group_rule(self):
        sgr_obj = sdk_sgr.SecurityGroupRule(**{"id": "foo"})
        security_group_rule = _dict(sgr_obj)
        self.nc.create_security_group_rule.return_value = sgr_obj

        self.assertEqual(
            security_group_rule,
            self.neutron.create_security_group_rule(
                security_group_id="sg1", )
        )
        self.nc.create_security_group_rule.assert_called_once_with(
            security_group_id="sg1", direction="ingress", protocol="tcp"
        )

    def test_get_security_group_rule(self):
        sgr_obj = sdk_sgr.SecurityGroupRule(**{"id": "foo"})
        security_group_rule = _dict(sgr_obj)
        self.nc.get_security_group_rule.return_value = sgr_obj
        security_group_rule_id = "security-group-id"

        self.assertEqual(
            security_group_rule,
            self.neutron.get_security_group_rule(security_group_rule_id))
        self.nc.get_security_group_rule.assert_called_once_with(
            security_group_rule_id)

        self.nc.get_security_group_rule.reset_mock()

        fields = ["a", "b"]
        self.assertEqual(
            security_group_rule,
            self.neutron.get_security_group_rule(
                security_group_rule_id, fields=fields))
        self.nc.get_security_group_rule.assert_called_once_with(
            security_group_rule_id, fields=fields)

        self.nc.get_security_group_rule.reset_mock()

        # verbose is unsupported by openstacksdk and must be ignored
        # (not forwarded to the client) while still being accepted.
        self.assertEqual(
            security_group_rule,
            self.neutron.get_security_group_rule(
                security_group_rule_id, verbose=True))
        self.nc.get_security_group_rule.assert_called_once_with(
            security_group_rule_id)

    def test_delete_security_group_rule(self):
        security_group_rule_id = "security-group-rule-id"
        self.neutron.delete_security_group_rule(security_group_rule_id)
        self.nc.delete_security_group_rule.assert_called_once_with(
            security_group_rule_id, ignore_missing=False)

    def test_list_security_groups_rule(self):
        sgr1_obj = sdk_sgr.SecurityGroupRule(**{"id": "sg-1", "name": "foo"})
        sgr2_obj = sdk_sgr.SecurityGroupRule(**{"id": "sg-2", "name": "bar"})
        self.nc.security_group_rules.return_value = iter([sgr1_obj, sgr2_obj])

        self.assertEqual([_dict(sgr1_obj), _dict(sgr2_obj)],
                         self.neutron.list_security_group_rules())
        self.nc.security_group_rules.assert_called_once_with()

    def test_list_agents(self):
        agent1_obj = sdk_agent.Agent(**{"id": "agent-1", "name": "foo"})
        agent2_obj = sdk_agent.Agent(**{"id": "agent-2", "name": "bar"})
        self.nc.agents.return_value = iter([agent1_obj, agent2_obj])

        self.assertEqual([_dict(agent1_obj), _dict(agent2_obj)],
                         self.neutron.list_agents())
        self.nc.agents.assert_called_once_with()

    def test_list_extensions(self):
        ext1_obj = sdk_extension.Extension(**{"alias": "foo"})
        ext2_obj = sdk_extension.Extension(**{"alias": "bar"})
        self.nc.extensions.return_value = iter([ext1_obj, ext2_obj])

        self.assertEqual([_dict(ext1_obj), _dict(ext2_obj)],
                         self.neutron.list_extensions())
        self.nc.extensions.assert_called_once_with()

    def test_cached_supported_extensions(self):
        ext1_obj = sdk_extension.Extension(**{"alias": "foo"})
        ext2_obj = sdk_extension.Extension(**{"alias": "bar"})
        self.nc.extensions.return_value = iter([ext1_obj, ext2_obj])

        self.assertEqual([_dict(ext1_obj), _dict(ext2_obj)],
                         self.neutron.cached_supported_extensions)
        self.nc.extensions.assert_called_once_with()

        self.nc.extensions.reset_mock()
        # another try
        self.assertEqual([_dict(ext1_obj), _dict(ext2_obj)],
                         self.neutron.cached_supported_extensions)
        self.assertFalse(self.nc.extensions.called)

    def test_supports_extension(self):
        ext1_obj = sdk_extension.Extension(**{"alias": "foo"})
        ext2_obj = sdk_extension.Extension(**{"alias": "bar"})
        self.nc.extensions.return_value = iter([ext1_obj, ext2_obj])

        self.assertTrue(self.neutron.supports_extension("foo"))
        self.assertTrue(self.neutron.supports_extension("bar"))
        self.assertFalse(self.neutron.supports_extension("xxx", silent=True))
        self.assertRaises(exceptions.NotFoundException,
                          self.neutron.supports_extension, "xxx")

        # this should be called once
        self.nc.extensions.assert_called_once_with()
