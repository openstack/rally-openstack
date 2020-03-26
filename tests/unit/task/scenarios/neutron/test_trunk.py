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

from rally_openstack.task.scenarios.neutron import trunk
from tests.unit import test


class NeutronTrunkTestCase(test.ScenarioTestCase):

    def test_create_and_list_trunks(self):
        subport_count = 10
        network_create_args = {}
        net = mock.MagicMock()
        scenario = trunk.CreateAndListTrunks(self.context)
        scenario._create_network = mock.Mock(return_value=net)
        scenario._create_port = mock.MagicMock()
        scenario._create_trunk = mock.MagicMock()
        scenario._list_subports_by_trunk = mock.MagicMock()
        scenario._update_port = mock.Mock()
        scenario._list_ports_by_device_id = mock.Mock()
        scenario.run(network_create_args=network_create_args,
                     subport_count=subport_count)
        scenario._create_network.assert_called_once_with(
            network_create_args)
        scenario._create_port.assert_has_calls(
            [mock.call(net, {})
             for _ in range(subport_count + 1)])
        self.assertEqual(1, scenario._create_trunk.call_count)
        self.assertEqual(1, scenario._update_port.call_count)
        self.assertEqual(1, scenario._list_subports_by_trunk.call_count)
        self.assertEqual(1, scenario._list_ports_by_device_id.call_count)

    def test_boot_server_with_subports(self):
        img_name = "img"
        flavor_uuid = 0
        subport_count = 10
        network_create_args = {}
        net = mock.MagicMock()
        port = {"port": {"id": "port-id"}}
        kwargs = {"nics": [{"port-id": "port-id"}]}
        subnet = {"subnet": {"id": "subnet-id"}}
        scenario = trunk.BootServerWithSubports(self.context)
        scenario._boot_server = mock.MagicMock()
        scenario._create_port = mock.MagicMock(return_value=port)
        scenario._create_trunk = mock.MagicMock()
        scenario._create_network_and_subnets = mock.MagicMock()
        scenario._create_network_and_subnets.return_value = net, [subnet]
        scenario.run(img_name, flavor_uuid,
                     network_create_args=network_create_args,
                     subport_count=subport_count)
        scenario._create_port.assert_has_calls(
            [mock.call(net, {"fixed_ips": [{"subnet_id":
                                            subnet["subnet"]["id"]}]})
             for _ in range(subport_count + 1)])
        self.assertEqual(1, scenario._create_trunk.call_count)
        self.assertEqual(11, scenario._create_network_and_subnets.call_count)
        scenario._boot_server.assert_called_once_with(img_name, flavor_uuid,
                                                      **kwargs)

    def test_boot_server_and_add_subports(self):
        img_name = "img"
        flavor_uuid = 0
        subport_count = 10
        network_create_args = {}
        net = mock.MagicMock()
        port = {"port": {"id": "port-id"}}
        kwargs = {"nics": [{"port-id": "port-id"}]}
        subnet = {"subnet": {"id": "subnet-id"}}
        scenario = trunk.BootServerAndAddSubports(self.context)
        scenario._boot_server = mock.MagicMock()
        scenario._create_port = mock.MagicMock(return_value=port)
        scenario._create_trunk = mock.MagicMock()
        scenario._add_subports_to_trunk = mock.MagicMock()
        scenario._create_network_and_subnets = mock.MagicMock()
        scenario._create_network_and_subnets.return_value = net, [subnet]
        scenario.run(img_name, flavor_uuid,
                     network_create_args=network_create_args,
                     subport_count=subport_count)
        scenario._create_port.assert_has_calls(
            [mock.call(net, {"fixed_ips": [{"subnet_id":
                                            subnet["subnet"]["id"]}]})
             for _ in range(subport_count + 1)])
        self.assertEqual(1, scenario._create_trunk.call_count)
        scenario._boot_server.assert_called_once_with(img_name, flavor_uuid,
                                                      **kwargs)
        self.assertEqual(10, scenario._add_subports_to_trunk.call_count)
        self.assertEqual(11, scenario._create_network_and_subnets.call_count)

    def test_boot_server_and_batch_add_subports(self):
        img_name = "img"
        flavor_uuid = 0
        subports_per_batch = 10
        batches = 5
        network_create_args = {}
        net = mock.MagicMock()
        port = {"port": {"id": "port-id"}}
        kwargs = {"nics": [{"port-id": "port-id"}]}
        subnet = {"subnet": {"id": "subnet-id"}}
        scenario = trunk.BootServerAndBatchAddSubports(self.context)
        scenario._boot_server = mock.MagicMock()
        scenario._create_port = mock.MagicMock(return_value=port)
        scenario._create_trunk = mock.MagicMock()
        scenario._add_subports_to_trunk = mock.MagicMock()
        scenario._create_network_and_subnets = mock.MagicMock()
        scenario._create_network_and_subnets.return_value = net, [subnet]
        scenario.run(img_name, flavor_uuid,
                     network_create_args=network_create_args,
                     subports_per_batch=10, batches=5)
        scenario._create_port.assert_has_calls(
            [mock.call(net, {"fixed_ips": [{"subnet_id":
                                            subnet["subnet"]["id"]}]})
             for _ in range(subports_per_batch * batches + 1)])
        self.assertEqual(1, scenario._create_trunk.call_count)
        scenario._boot_server.assert_called_once_with(img_name, flavor_uuid,
                                                      **kwargs)
        self.assertEqual(5, scenario._add_subports_to_trunk.call_count)
        self.assertEqual(51, scenario._create_network_and_subnets.call_count)
