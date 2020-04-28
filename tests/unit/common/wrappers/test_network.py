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
from neutronclient.common import exceptions as neutron_exceptions

from rally.common import utils

from rally_openstack.common import consts
from rally_openstack.common.wrappers import network
from tests.unit import test


SVC = "rally_openstack.common.wrappers.network."


class Owner(utils.RandomNameGeneratorMixin):
    task = {"uuid": "task-uuid"}


@ddt.ddt
class NeutronWrapperTestCase(test.TestCase):
    def setUp(self):
        super(NeutronWrapperTestCase, self).setUp()
        self.owner = Owner()
        self.owner.generate_random_name = mock.Mock()
        clients = mock.MagicMock()
        clients.credential.permission = consts.EndpointPermission.ADMIN
        self.wrapper = network.NeutronWrapper(
            clients, self.owner, config={})
        self._nc = self.wrapper.neutron.client

    def test_SUBNET_IP_VERSION(self):
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
        self._nc.list_networks.return_value = {"networks": "foo_networks"}
        self.assertEqual("foo_networks", self.wrapper.external_networks)
        self._nc.list_networks.assert_called_once_with(
            **{"router:external": True})

    def test_get_network(self):
        neutron_net = {"id": "foo_id",
                       "name": "foo_name",
                       "tenant_id": "foo_tenant",
                       "status": "foo_status",
                       "router:external": "foo_external",
                       "subnets": "foo_subnets"}
        expected_net = {"id": "foo_id",
                        "name": "foo_name",
                        "tenant_id": "foo_tenant",
                        "status": "foo_status",
                        "external": "foo_external",
                        "router_id": None,
                        "subnets": "foo_subnets"}
        self._nc.show_network.return_value = {"network": neutron_net}
        net = self.wrapper.get_network(net_id="foo_id")
        self.assertEqual(expected_net, net)
        self._nc.show_network.assert_called_once_with("foo_id")

        self._nc.show_network.side_effect = (
            neutron_exceptions.NeutronClientException)
        self.assertRaises(network.NetworkWrapperException,
                          self.wrapper.get_network,
                          net_id="foo_id")

        self._nc.list_networks.return_value = {"networks": [neutron_net]}
        net = self.wrapper.get_network(name="foo_name")
        self.assertEqual(expected_net, net)
        self._nc.list_networks.assert_called_once_with(name="foo_name")

        self._nc.list_networks.return_value = {"networks": []}
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
        self._nc.create_network.return_value = {
            "network": {"id": "foo_id",
                        "name": self.owner.generate_random_name.return_value,
                        "status": "foo_status"}}
        net = self.wrapper.create_network("foo_tenant")
        self._nc.create_network.assert_called_once_with({
            "network": {"tenant_id": "foo_tenant",
                        "name": self.owner.generate_random_name.return_value}})
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
        self._nc.create_subnet.side_effect = lambda i: {
            "subnet": {"id": "subnet-%d" % next(subnets_ids)}}
        self._nc.create_network.return_value = {
            "network": {"id": "foo_id",
                        "name": self.owner.generate_random_name.return_value,
                        "status": "foo_status"}}

        net = self.wrapper.create_network("foo_tenant",
                                          subnets_num=subnets_num)

        self._nc.create_network.assert_called_once_with({
            "network": {"tenant_id": "foo_tenant",
                        "name": self.owner.generate_random_name.return_value}})
        self.assertEqual({"id": "foo_id",
                          "name": self.owner.generate_random_name.return_value,
                          "status": "foo_status",
                          "external": False,
                          "router_id": None,
                          "tenant_id": "foo_tenant",
                          "subnets": ["subnet-%d" % i
                                      for i in range(subnets_num)]}, net)
        self.assertEqual(
            [mock.call({"subnet":
                        {"name": self.owner.generate_random_name.return_value,
                         "network_id": "foo_id",
                         "tenant_id": "foo_tenant",
                         "ip_version": self.wrapper.SUBNET_IP_VERSION,
                         "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
                         "cidr": mock.ANY}})
             for i in range(subnets_num)],
            self.wrapper.client.create_subnet.call_args_list
        )

    def test_create_network_with_router(self):
        self._nc.create_router.return_value = {"router": {"id": "foo_router"}}
        self._nc.create_network.return_value = {
            "network": {"id": "foo_id",
                        "name": self.owner.generate_random_name.return_value,
                        "status": "foo_status"}}
        net = self.wrapper.create_network("foo_tenant", add_router=True)
        self.assertEqual({"id": "foo_id",
                          "name": self.owner.generate_random_name.return_value,
                          "status": "foo_status",
                          "external": False,
                          "tenant_id": "foo_tenant",
                          "router_id": "foo_router",
                          "subnets": []}, net)
        self._nc.create_router.assert_called_once_with({
            "router": {
                "name": self.owner.generate_random_name(),
                "tenant_id": "foo_tenant"
            }
        })

    def test_create_network_with_router_and_subnets(self):
        subnets_num = 4
        self.wrapper._generate_cidr = mock.Mock(return_value="foo_cidr")
        self._nc.create_router.return_value = {"router": {"id": "foo_router"}}
        self._nc.create_subnet.return_value = {"subnet": {"id": "foo_subnet"}}
        self._nc.create_network.return_value = {
            "network": {"id": "foo_id",
                        "name": self.owner.generate_random_name.return_value,
                        "status": "foo_status"}}
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
            {"router": {"name": self.owner.generate_random_name.return_value,
                        "tenant_id": "foo_tenant"}})
        self.assertEqual(
            [
                mock.call(
                    {"subnet": {
                        "name": self.owner.generate_random_name.return_value,
                        "network_id": "foo_id",
                        "tenant_id": "foo_tenant",
                        "ip_version": self.wrapper.SUBNET_IP_VERSION,
                        "dns_nameservers": ["foo_nameservers"],
                        "cidr": mock.ANY
                    }}
                )
            ] * subnets_num,
            self._nc.create_subnet.call_args_list,
        )
        self.assertEqual(self._nc.add_interface_router.call_args_list,
                         [mock.call("foo_router", {"subnet_id": "foo_subnet"})
                          for i in range(subnets_num)])

    def test_delete_v1_pool(self):
        pool = {"pool": {"id": "pool-id"}}
        self.wrapper.delete_v1_pool(pool["pool"]["id"])
        self.wrapper.client.delete_pool.assert_called_once_with("pool-id")

    def test_delete_network(self):
        self._nc.list_ports.return_value = {"ports": []}
        self._nc.list_subnets.return_value = {"subnets": []}
        self._nc.delete_network.return_value = "foo_deleted"
        self.wrapper.delete_network(
            {"id": "foo_id", "router_id": None, "subnets": [], "name": "x",
             "status": "y", "external": False})
        self.assertFalse(self._nc.remove_gateway_router.called)
        self.assertFalse(self._nc.remove_interface_router.called)
        self.assertFalse(self._nc.client.delete_router.called)
        self.assertFalse(self._nc.client.delete_subnet.called)
        self._nc.delete_network.assert_called_once_with("foo_id")

    def test_delete_network_with_router_and_ports_and_subnets(self):

        subnets = ["foo_subnet", "bar_subnet"]
        ports = [{"id": "foo_port", "device_owner": "network:router_interface",
                  "device_id": "rounttter"},
                 {"id": "bar_port", "device_owner": "network:dhcp"}]
        self._nc.list_ports.return_value = ({"ports": ports})
        self._nc.list_subnets.return_value = (
            {"subnets": [{"id": id_} for id_ in subnets]})

        self.wrapper.delete_network(
            {"id": "foo_id", "router_id": "foo_router", "subnets": subnets,
             "lb_pools": [], "name": "foo", "status": "x", "external": False})

        self.assertEqual(self._nc.remove_gateway_router.mock_calls,
                         [mock.call("foo_router")])
        self._nc.delete_port.assert_called_once_with(ports[1]["id"])
        self._nc.remove_interface_router.assert_called_once_with(
            ports[0]["device_id"], {"port_id": ports[0]["id"]})
        self.assertEqual(
            [mock.call(subnet_id) for subnet_id in subnets],
            self._nc.delete_subnet.call_args_list
        )
        self._nc.delete_network.assert_called_once_with("foo_id")

    @ddt.data({"exception_type": neutron_exceptions.NotFound,
               "should_raise": False},
              {"exception_type": neutron_exceptions.BadRequest,
               "should_raise": False},
              {"exception_type": KeyError,
               "should_raise": True})
    @ddt.unpack
    def test_delete_network_with_router_throw_exception(
            self, exception_type, should_raise):
        # Ensure cleanup context still move forward even
        # remove_interface_router throw NotFound/BadRequest exception

        self._nc.remove_interface_router.side_effect = exception_type
        subnets = ["foo_subnet", "bar_subnet"]
        ports = [{"id": "foo_port", "device_owner": "network:router_interface",
                  "device_id": "rounttter"},
                 {"id": "bar_port", "device_owner": "network:dhcp"}]
        self._nc.list_ports.return_value = {"ports": ports}
        self._nc.list_subnets.return_value = {"subnets": [
            {"id": id_} for id_ in subnets]}

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

            self._nc.delete_port.assert_called_once_with(ports[1]["id"])
            self._nc.remove_interface_router.assert_called_once_with(
                ports[0]["device_id"], {"port_id": ports[0]["id"]})
            self.assertEqual(
                [mock.call(subnet_id) for subnet_id in subnets],
                self._nc.delete_subnet.call_args_list
            )
            self._nc.delete_network.assert_called_once_with("foo_id")

            self._nc.remove_gateway_router.assert_called_once_with(
                "foo_router")

    def test_list_networks(self):
        self._nc.list_networks.return_value = {"networks": "foo_nets"}
        self.assertEqual("foo_nets", self.wrapper.list_networks())
        self._nc.list_networks.assert_called_once_with()

    def test_create_floating_ip(self):
        self._nc.create_port.return_value = {"port": {"id": "port_id"}}
        self._nc.create_floatingip.return_value = {
            "floatingip": {"id": "fip_id", "floating_ip_address": "fip_ip"}}

        self.assertRaises(ValueError, self.wrapper.create_floating_ip)

        self._nc.list_networks.return_value = {"networks": []}
        self.assertRaises(network.NetworkWrapperException,
                          self.wrapper.create_floating_ip,
                          tenant_id="foo_tenant")

        self._nc.list_networks.return_value = {"networks": [{"id": "ext_id"}]}
        fip = self.wrapper.create_floating_ip(
            tenant_id="foo_tenant", port_id="port_id")
        self.assertEqual({"id": "fip_id", "ip": "fip_ip"}, fip)

        self._nc.list_networks.return_value = {"networks": [
            {"id": "ext_net_id", "name": "ext_net", "router:external": True}]}
        self.wrapper.create_floating_ip(
            tenant_id="foo_tenant", ext_network="ext_net", port_id="port_id")

        self.assertRaises(
            network.NetworkWrapperException,
            self.wrapper.create_floating_ip, tenant_id="foo_tenant",
            ext_network="ext_net_2")

    def test_delete_floating_ip(self):
        self.wrapper.delete_floating_ip("fip_id")
        self.wrapper.delete_floating_ip("fip_id", ignored_kwarg="bar")
        self.assertEqual([mock.call("fip_id")] * 2,
                         self._nc.delete_floatingip.call_args_list)

    def test_create_router(self):
        self._nc.create_router.return_value = {"router": "foo_router"}
        self._nc.list_extensions.return_value = {
            "extensions": [{"alias": "ext-gw-mode"}]}
        self._nc.list_networks.return_value = {"networks": [{"id": "ext_id"}]}

        router = self.wrapper.create_router()
        self._nc.create_router.assert_called_once_with(
            {"router": {"name": self.owner.generate_random_name.return_value}})
        self.assertEqual("foo_router", router)

        self.wrapper.create_router(external=True, flavor_id="bar")
        self._nc.create_router.assert_called_with(
            {"router": {"name": self.owner.generate_random_name.return_value,
                        "external_gateway_info": {
                            "network_id": "ext_id",
                            "enable_snat": True},
                        "flavor_id": "bar"}})

    def test_create_router_without_ext_gw_mode_extension(self):
        self._nc.create_router.return_value = {"router": "foo_router"}
        self._nc.list_extensions.return_value = {"extensions": []}
        self._nc.list_networks.return_value = {"networks": [{"id": "ext_id"}]}

        router = self.wrapper.create_router()
        self._nc.create_router.assert_called_once_with(
            {"router": {"name": self.owner.generate_random_name.return_value}})
        self.assertEqual(router, "foo_router")

        self.wrapper.create_router(external=True, flavor_id="bar")
        self._nc.create_router.assert_called_with(
            {"router": {"name": self.owner.generate_random_name.return_value,
                        "external_gateway_info": {"network_id": "ext_id"},
                        "flavor_id": "bar"}})

    def test_create_port(self):
        self._nc.create_port.return_value = {"port": "foo_port"}

        port = self.wrapper.create_port("foo_net")
        self._nc.create_port.assert_called_once_with(
            {"port": {"network_id": "foo_net",
                      "name": self.owner.generate_random_name.return_value}})
        self.assertEqual("foo_port", port)

        port = self.wrapper.create_port("foo_net", foo="bar")
        self.wrapper.client.create_port.assert_called_with(
            {"port": {"network_id": "foo_net",
                      "name": self.owner.generate_random_name.return_value,
                      "foo": "bar"}})

    def test_supports_extension(self):
        self._nc.list_extensions.return_value = (
            {"extensions": [{"alias": "extension"}]})
        self.assertTrue(self.wrapper.supports_extension("extension")[0])

        self.wrapper.neutron._cached_supported_extensions = None
        self._nc.list_extensions.return_value = (
            {"extensions": [{"alias": "extension"}]})
        self.assertFalse(self.wrapper.supports_extension("dummy-group")[0])

        self.wrapper.neutron._cached_supported_extensions = None
        self._nc.list_extensions.return_value = {"extensions": []}
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
