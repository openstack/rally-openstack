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
from openstack import exceptions as sdk_exceptions
from openstack.network.v2 import extension as sdk_extension
from openstack.network.v2 import floating_ip as sdk_fip
from openstack.network.v2 import network as sdk_net
from openstack.network.v2 import port as sdk_port
from openstack.network.v2 import router as sdk_router
from openstack.network.v2 import subnet as sdk_subnet

from rally.common import utils

from rally_openstack.common import consts
from rally_openstack.common.wrappers import network
from tests.unit import test


SVC = "rally_openstack.common.wrappers.network."


def _dict(resource):
    return resource.to_dict(
        computed=False, original_names=True, headers=False, ignore_none=True)


class Owner(utils.RandomNameGeneratorMixin):
    task = {"uuid": "task-uuid"}


@ddt.ddt
class NeutronWrapperTestCase(test.TestCase):
    def setUp(self):
        super().setUp()
        self.owner = Owner()
        self.owner.generate_random_name = mock.Mock()
        clients = mock.MagicMock()
        clients.credential.permission = consts.EndpointPermission.ADMIN
        self.wrapper = network.NeutronWrapper(
            clients, self.owner, config={})
        self._nc = self.wrapper.neutron.client

    def test_SUBNET_IP_VERSION(self):  # noqa: N802
        self.assertEqual(4, network.NeutronWrapper.SUBNET_IP_VERSION)

    @mock.patch(
        "rally_openstack.common.services.network.net_utils.generate_cidr")
    def test__generate_cidr(self, mock_generate_cidr):
        cidrs = iter(range(5))

        def fake_gen_cidr(ip_version=None, start_cidr=None):
            return 4, 3 + next(cidrs)

        mock_generate_cidr.side_effect = fake_gen_cidr

        self.assertEqual(3, self.wrapper._generate_cidr())
        self.assertEqual(4, self.wrapper._generate_cidr())
        self.assertEqual(5, self.wrapper._generate_cidr())
        self.assertEqual(6, self.wrapper._generate_cidr())
        self.assertEqual(7, self.wrapper._generate_cidr())
        self.assertEqual([mock.call(start_cidr=self.wrapper.start_cidr)] * 5,
                         mock_generate_cidr.call_args_list)

    def test_external_networks(self):
        net_obj = sdk_net.Network(**{"id": "foo_net", "name": "foo_networks"})
        self._nc.networks.return_value = iter([net_obj])
        self.assertEqual([_dict(net_obj)], self.wrapper.external_networks)
        self._nc.networks.assert_called_once_with(
            **{"router:external": True})

    def test_get_network(self):
        neutron_net = {"id": "foo_id",
                       "name": "foo_name",
                       "tenant_id": "foo_tenant",
                       "status": "foo_status",
                       "router:external": True,
                       "subnets": ["foo_subnet_id"]}
        expected_net = {"id": "foo_id",
                        "name": "foo_name",
                        "tenant_id": "foo_tenant",
                        "status": "foo_status",
                        "external": True,
                        "router_id": None,
                        "subnets": ["foo_subnet_id"]}
        self._nc.get_network.return_value = sdk_net.Network(**neutron_net)
        net = self.wrapper.get_network(net_id="foo_id")
        self.assertEqual(expected_net, net)
        self._nc.get_network.assert_called_once_with("foo_id")

        self._nc.get_network.side_effect = (
            sdk_exceptions.NotFoundException)
        self.assertRaises(network.NetworkWrapperException,
                          self.wrapper.get_network,
                          net_id="foo_id")

        self._nc.networks.return_value = iter(
            [sdk_net.Network(**neutron_net)])
        net = self.wrapper.get_network(name="foo_name")
        self.assertEqual(expected_net, net)
        self._nc.networks.assert_called_once_with(name="foo_name")

        self._nc.networks.return_value = iter([])
        self.assertRaises(network.NetworkWrapperException,
                          self.wrapper.get_network,
                          name="foo_name")

    def test_create_v1_pool(self):
        subnet = "subnet_id"
        tenant = "foo_tenant"
        expected_pool = {"pool": {
            "id": "pool_id",
            "name": self.owner.generate_random_name.return_value,
            "subnet_id": subnet,
            "tenant_id": tenant}}
        self.wrapper.client.create_pool.return_value = expected_pool
        resultant_pool = self.wrapper.create_v1_pool(tenant, subnet)
        self.wrapper.client.create_pool.assert_called_once_with({
            "pool": {"lb_method": "ROUND_ROBIN",
                     "subnet_id": subnet,
                     "tenant_id": tenant,
                     "protocol": "HTTP",
                     "name": self.owner.generate_random_name.return_value}})
        self.assertEqual(expected_pool, resultant_pool)

    def test_create_network(self):
        self._nc.create_network.return_value = sdk_net.Network(
            **{"id": "foo_id",
               "name": self.owner.generate_random_name.return_value,
               "status": "foo_status"})
        net = self.wrapper.create_network("foo_tenant")
        self._nc.create_network.assert_called_once_with(
            name=self.owner.generate_random_name.return_value,
            tenant_id="foo_tenant")
        self.assertEqual({"id": "foo_id",
                          "name": self.owner.generate_random_name.return_value,
                          "status": "foo_status",
                          "external": False,
                          "tenant_id": "foo_tenant",
                          "router_id": None,
                          "subnets": []}, net)

    def test_create_network_with_subnets(self):
        subnets_num = 4
        subnets_ids = iter(range(subnets_num))

        def fake_create_subnet(**kwargs):
            return sdk_subnet.Subnet(**{"id": "subnet-%d" % next(subnets_ids)})

        self._nc.create_subnet.side_effect = fake_create_subnet
        self._nc.create_network.return_value = sdk_net.Network(
            **{"id": "foo_id",
               "name": self.owner.generate_random_name.return_value,
               "status": "foo_status"})

        net = self.wrapper.create_network("foo_tenant",
                                          subnets_num=subnets_num)

        self._nc.create_network.assert_called_once_with(
            name=self.owner.generate_random_name.return_value,
            tenant_id="foo_tenant")
        self.assertEqual({"id": "foo_id",
                          "name": self.owner.generate_random_name.return_value,
                          "status": "foo_status",
                          "external": False,
                          "router_id": None,
                          "tenant_id": "foo_tenant",
                          "subnets": ["subnet-%d" % i
                                      for i in range(subnets_num)]}, net)
        self.assertEqual(
            [mock.call(name=self.owner.generate_random_name.return_value,
                       network_id="foo_id",
                       tenant_id="foo_tenant",
                       ip_version=self.wrapper.SUBNET_IP_VERSION,
                       dns_nameservers=mock.ANY,
                       cidr=mock.ANY)
             for i in range(subnets_num)],
            self._nc.create_subnet.call_args_list
        )

    def test_create_network_with_router(self):
        self._nc.create_router.return_value = sdk_router.Router(
            **{"id": "foo_router"})
        self._nc.create_network.return_value = sdk_net.Network(
            **{"id": "foo_id",
               "name": self.owner.generate_random_name.return_value,
               "status": "foo_status"})
        net = self.wrapper.create_network("foo_tenant", add_router=True)
        self.assertEqual({"id": "foo_id",
                          "name": self.owner.generate_random_name.return_value,
                          "status": "foo_status",
                          "external": False,
                          "tenant_id": "foo_tenant",
                          "router_id": "foo_router",
                          "subnets": []}, net)
        self._nc.create_router.assert_called_once_with(
            name=self.owner.generate_random_name.return_value,
            tenant_id="foo_tenant")

    def test_create_network_with_router_and_subnets(self):
        subnets_num = 4
        self.wrapper._generate_cidr = mock.Mock(return_value="foo_cidr")
        self._nc.create_router.return_value = sdk_router.Router(
            **{"id": "foo_router"})
        self._nc.create_subnet.return_value = sdk_subnet.Subnet(
            **{"id": "foo_subnet"})
        self._nc.create_network.return_value = sdk_net.Network(
            **{"id": "foo_id",
               "name": self.owner.generate_random_name.return_value,
               "status": "foo_status"})
        net = self.wrapper.create_network(
            "foo_tenant", add_router=True, subnets_num=subnets_num,
            dns_nameservers=["foo_nameservers"])
        self.assertEqual({"id": "foo_id",
                          "name": self.owner.generate_random_name.return_value,
                          "status": "foo_status",
                          "external": False,
                          "tenant_id": "foo_tenant",
                          "router_id": "foo_router",
                          "subnets": ["foo_subnet"] * subnets_num}, net)
        self._nc.create_router.assert_called_once_with(
            name=self.owner.generate_random_name.return_value,
            tenant_id="foo_tenant")
        self.assertEqual(
            [
                mock.call(
                    name=self.owner.generate_random_name.return_value,
                    network_id="foo_id",
                    tenant_id="foo_tenant",
                    ip_version=self.wrapper.SUBNET_IP_VERSION,
                    dns_nameservers=["foo_nameservers"],
                    cidr=mock.ANY)
            ] * subnets_num,
            self._nc.create_subnet.call_args_list,
        )
        self.assertEqual(
            self._nc.add_interface_to_router.call_args_list,
            [mock.call("foo_router", subnet_id="foo_subnet")
             for i in range(subnets_num)])

    def test_delete_v1_pool(self):
        pool = {"pool": {"id": "pool-id"}}
        self.wrapper.delete_v1_pool(pool["pool"]["id"])
        self.wrapper.client.delete_pool.assert_called_once_with("pool-id")

    def test_delete_network(self):
        self._nc.ports.return_value = iter([])
        self._nc.subnets.return_value = iter([])
        self._nc.delete_network.return_value = "foo_deleted"
        self.wrapper.delete_network(
            {"id": "foo_id", "router_id": None, "subnets": [], "name": "x",
             "status": "y", "external": False})
        self.assertFalse(self._nc.update_router.called)
        self.assertFalse(self._nc.remove_interface_from_router.called)
        self.assertFalse(self._nc.delete_router.called)
        self.assertFalse(self._nc.delete_subnet.called)
        self._nc.delete_network.assert_called_once_with(
            "foo_id", ignore_missing=False)

    def test_delete_network_with_router_and_ports_and_subnets(self):

        subnets = ["foo_subnet", "bar_subnet"]
        ports = [{"id": "foo_port",
                  "device_owner": "network:router_interface",
                  "device_id": "rounttter"},
                 {"id": "bar_port", "device_owner": "network:dhcp",
                  "device_id": "dhcp-id"}]
        self._nc.ports.return_value = iter(
            [sdk_port.Port(**p) for p in ports])
        self._nc.subnets.return_value = iter(
            [sdk_subnet.Subnet(**{"id": id_}) for id_ in subnets])

        self.wrapper.delete_network(
            {"id": "foo_id", "router_id": "foo_router", "subnets": subnets,
             "lb_pools": [], "name": "foo", "status": "x", "external": False})

        # remove_gateway_from_router -> update_router(..., None)
        self.assertEqual(
            [mock.call("foo_router", external_gateway_info=None)],
            self._nc.update_router.call_args_list)
        self._nc.delete_port.assert_called_once_with(
                ports[1]["id"], ignore_missing=False)
        self._nc.remove_interface_from_router.assert_called_once_with(
            ports[0]["device_id"], port_id=ports[0]["id"])
        self.assertEqual(
            [mock.call(subnet_id, ignore_missing=False)
             for subnet_id in subnets],
            self._nc.delete_subnet.call_args_list
        )
        self._nc.delete_network.assert_called_once_with(
            "foo_id", ignore_missing=False)
        self._nc.delete_router.assert_called_once_with(
            "foo_router", ignore_missing=False)

    @ddt.data({"exception_type": sdk_exceptions.NotFoundException,
               "should_raise": False},
              {"exception_type": sdk_exceptions.BadRequestException,
               "should_raise": False},
              {"exception_type": KeyError,
               "should_raise": True})
    @ddt.unpack
    def test_delete_network_with_router_throw_exception(
            self, exception_type, should_raise):
        # Ensure cleanup context still moves forward even when
        # remove_interface_from_router throws NotFound/BadRequest exception.
        # NotFound/BadRequest are swallowed inside the service, while a
        # KeyError propagates and aborts the cleanup.

        self._nc.remove_interface_from_router.side_effect = exception_type
        subnets = ["foo_subnet", "bar_subnet"]
        ports = [{"id": "foo_port",
                  "device_owner": "network:router_interface",
                  "device_id": "rounttter"},
                 {"id": "bar_port", "device_owner": "network:dhcp",
                  "device_id": "dhcp-id"}]
        self._nc.ports.return_value = iter(
            [sdk_port.Port(**p) for p in ports])
        self._nc.subnets.return_value = iter(
            [sdk_subnet.Subnet(**{"id": id_}) for id_ in subnets])

        if should_raise:
            self.assertRaises(
                exception_type, self.wrapper.delete_network,
                {"id": "foo_id", "name": "foo", "router_id": "foo_router",
                 "subnets": subnets, "lb_pools": [], "status": "xxx",
                 "external": False})
            self.assertFalse(self._nc.delete_subnet.called)
            self.assertFalse(self._nc.delete_network.called)
        else:
            self.wrapper.delete_network(
                {"id": "foo_id", "name": "foo", "status": "xxx",
                 "router_id": "foo_router", "subnets": subnets,
                 "lb_pools": [], "external": False})

            self._nc.delete_port.assert_called_once_with(
                ports[1]["id"], ignore_missing=False)
            self._nc.remove_interface_from_router.assert_called_once_with(
                ports[0]["device_id"], port_id=ports[0]["id"])
            self.assertEqual(
                [mock.call(subnet_id, ignore_missing=False)
                 for subnet_id in subnets],
                self._nc.delete_subnet.call_args_list
            )
            self._nc.delete_network.assert_called_once_with(
                "foo_id", ignore_missing=False)

            # remove_gateway_from_router -> update_router(..., None)
            self._nc.update_router.assert_called_once_with(
                "foo_router", external_gateway_info=None)

    def test_list_networks(self):
        net1_obj = sdk_net.Network(**{"id": "net-1", "name": "foo"})
        net2_obj = sdk_net.Network(**{"id": "net-2", "name": "bar"})
        self._nc.networks.return_value = iter([net1_obj, net2_obj])
        self.assertEqual([_dict(net1_obj), _dict(net2_obj)],
                         self.wrapper.list_networks())
        self._nc.networks.assert_called_once_with()

    def test_create_floating_ip(self):
        self._nc.create_ip.return_value = sdk_fip.FloatingIP(
            **{"id": "fip_id", "floating_ip_address": "fip_ip"})

        self.assertRaises(ValueError, self.wrapper.create_floating_ip)

        self._nc.networks.return_value = iter([])
        self.assertRaises(network.NetworkWrapperException,
                          self.wrapper.create_floating_ip,
                          tenant_id="foo_tenant")

        self._nc.networks.return_value = iter(
            [sdk_net.Network(**{"id": "ext_id"})])
        fip = self.wrapper.create_floating_ip(
            tenant_id="foo_tenant", port_id="port_id")
        self.assertEqual({"id": "fip_id", "ip": "fip_ip"}, fip)

        ext_net = {"id": "ext_net_id", "name": "ext_net",
                   "router:external": True}
        # ext_network is passed by name: find_network's get_network (by id)
        # misses and it resolves the network through list_networks.
        self._nc.get_network.side_effect = sdk_exceptions.ResourceNotFound()
        self._nc.networks.return_value = iter([sdk_net.Network(**ext_net)])
        self.wrapper.create_floating_ip(
            tenant_id="foo_tenant", ext_network="ext_net", port_id="port_id")
        self._nc.get_network.assert_called_with("ext_net")
        self._nc.networks.assert_called_with()

        self._nc.networks.return_value = iter([])
        self.assertRaises(
            network.NetworkWrapperException,
            self.wrapper.create_floating_ip, tenant_id="foo_tenant",
            ext_network="ext_net_2")

    def test_delete_floating_ip(self):
        self.wrapper.delete_floating_ip("fip_id")
        self.wrapper.delete_floating_ip("fip_id", ignored_kwarg="bar")
        self.assertEqual(
            [mock.call("fip_id", ignore_missing=False)] * 2,
            self._nc.delete_ip.call_args_list)

    def test_create_router(self):
        router_obj = sdk_router.Router(**{"id": "foo_router"})
        self._nc.create_router.return_value = router_obj
        self._nc.extensions.return_value = iter(
            [sdk_extension.Extension(**{"alias": "ext-gw-mode"})])
        self._nc.networks.return_value = iter(
            [sdk_net.Network(**{"id": "ext_id"})])

        router = self.wrapper.create_router()
        self._nc.create_router.assert_called_once_with(
            name=self.owner.generate_random_name.return_value)
        self.assertEqual(_dict(router_obj), router)

        self.wrapper.create_router(external=True, flavor_id="bar")
        self._nc.create_router.assert_called_with(
            name=self.owner.generate_random_name.return_value,
            external_gateway_info={
                "network_id": "ext_id",
                "enable_snat": True},
            flavor_id="bar")

    def test_create_router_without_ext_gw_mode_extension(self):
        router_obj = sdk_router.Router(**{"id": "foo_router"})
        self._nc.create_router.return_value = router_obj
        self._nc.extensions.return_value = iter([])
        self._nc.networks.return_value = iter(
            [sdk_net.Network(**{"id": "ext_id"})])

        router = self.wrapper.create_router()
        self._nc.create_router.assert_called_once_with(
            name=self.owner.generate_random_name.return_value)
        self.assertEqual(router, _dict(router_obj))

        self.wrapper.create_router(external=True, flavor_id="bar")
        self._nc.create_router.assert_called_with(
            name=self.owner.generate_random_name.return_value,
            external_gateway_info={"network_id": "ext_id"},
            flavor_id="bar")

    def test_create_port(self):
        port_obj = sdk_port.Port(**{"id": "foo_port"})
        self._nc.create_port.return_value = port_obj

        port = self.wrapper.create_port("foo_net")
        self._nc.create_port.assert_called_once_with(
            network_id="foo_net",
            name=self.owner.generate_random_name.return_value)
        self.assertEqual(_dict(port_obj), port)

        port = self.wrapper.create_port("foo_net", foo="bar")
        self._nc.create_port.assert_called_with(
            network_id="foo_net",
            name=self.owner.generate_random_name.return_value,
            foo="bar")

    def test_supports_extension(self):
        self._nc.extensions.return_value = iter(
            [sdk_extension.Extension(**{"alias": "extension"})])
        self.assertTrue(self.wrapper.supports_extension("extension")[0])

        self.wrapper.neutron._cached_supported_extensions = None
        self._nc.extensions.return_value = iter(
            [sdk_extension.Extension(**{"alias": "extension"})])
        self.assertFalse(self.wrapper.supports_extension("dummy-group")[0])

        self.wrapper.neutron._cached_supported_extensions = None
        self._nc.extensions.return_value = iter([])
        self.assertFalse(self.wrapper.supports_extension("extension")[0])


class FunctionsTestCase(test.TestCase):

    def test_wrap(self):
        mock_clients = mock.Mock()
        config = {"fakearg": "fake"}
        owner = Owner()

        mock_clients.services.return_value = {"foo": consts.Service.NEUTRON}
        wrapper = network.wrap(mock_clients, owner, config)
        self.assertIsInstance(wrapper, network.NeutronWrapper)
        self.assertEqual(wrapper.owner, owner)
        self.assertEqual(wrapper.config, config)
