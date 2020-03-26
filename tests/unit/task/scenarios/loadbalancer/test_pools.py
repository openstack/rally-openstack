# Copyright 2018: Red Hat Inc.
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

from rally_openstack.task.scenarios.octavia import pools
from tests.unit import test


class PoolsTestCase(test.ScenarioTestCase):

    def setUp(self):
        super(PoolsTestCase, self).setUp()
        patch = mock.patch(
            "rally_openstack.common.services.loadbalancer.octavia.Octavia")
        self.addCleanup(patch.stop)
        self.mock_loadbalancers = patch.start()

    def _get_context(self):
        context = super(PoolsTestCase, self).get_test_context()
        context.update({
            "user": {
                "id": "fake_user",
                "tenant_id": "fake_tenant",
                "credential": mock.MagicMock()
            },
            "tenant": {"id": "fake_tenant",
                       "networks": [{"id": "fake_net",
                                     "subnets": ["fake_subnet"]}]}})
        return context

    def test_create_and_list_pools(self):
        loadbalancer_service = self.mock_loadbalancers.return_value
        scenario = pools.CreateAndListPools(self._get_context())
        scenario.run(protocol="HTTP", lb_algorithm="ROUND_ROBIN")
        loadbalancer = [{
            "loadbalancer": {
                "id": "loadbalancer-id"
            }
        }]
        subnets = []
        mock_has_calls = []
        networks = self._get_context()["tenant"]["networks"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet in subnets:
            mock_has_calls.append(mock.call(subnet_id="fake_subnet",
                                            project_id="fake_tenant"))
        loadbalancer_service.load_balancer_create.assert_has_calls(
            mock_has_calls)
        for lb in loadbalancer:
            self.assertEqual(
                1, loadbalancer_service.wait_for_loadbalancer_prov_status
                .call_count)
            self.assertEqual(1,
                             loadbalancer_service.pool_create.call_count)
        loadbalancer_service.pool_list.assert_called_once_with()

    def test_create_and_delete_pools(self):
        loadbalancer_service = self.mock_loadbalancers.return_value
        scenario = pools.CreateAndDeletePools(self._get_context())
        scenario.run(protocol="HTTP", lb_algorithm="ROUND_ROBIN")
        loadbalancer = [{
            "loadbalancer": {
                "id": "loadbalancer-id"
            }
        }]
        subnets = []
        mock_has_calls = []
        networks = self._get_context()["tenant"]["networks"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet in subnets:
            mock_has_calls.append(mock.call(subnet_id="fake_subnet",
                                            project_id="fake_tenant"))
        loadbalancer_service.load_balancer_create.assert_has_calls(
            mock_has_calls)
        for lb in loadbalancer:
            self.assertEqual(
                1, loadbalancer_service.wait_for_loadbalancer_prov_status
                .call_count)
            self.assertEqual(1,
                             loadbalancer_service.pool_create.call_count)
            self.assertEqual(1,
                             loadbalancer_service.pool_delete.call_count)

    def test_create_and_update_pools(self):
        loadbalancer_service = self.mock_loadbalancers.return_value
        scenario = pools.CreateAndUpdatePools(self._get_context())
        scenario.run(protocol="HTTP", lb_algorithm="ROUND_ROBIN")
        loadbalancer = [{
            "loadbalancer": {
                "id": "loadbalancer-id"
            }
        }]
        subnets = []
        mock_has_calls = []
        networks = self._get_context()["tenant"]["networks"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet in subnets:
            mock_has_calls.append(mock.call(subnet_id="fake_subnet",
                                            project_id="fake_tenant"))
        loadbalancer_service.load_balancer_create.assert_has_calls(
            mock_has_calls)
        for lb in loadbalancer:
            self.assertEqual(
                1, loadbalancer_service.wait_for_loadbalancer_prov_status
                .call_count)
            self.assertEqual(1,
                             loadbalancer_service.pool_create.call_count)
            self.assertEqual(1,
                             loadbalancer_service.pool_set.call_count)

    def test_create_and_show_pools(self):
        loadbalancer_service = self.mock_loadbalancers.return_value
        scenario = pools.CreateAndShowPools(self._get_context())
        scenario.run(protocol="HTTP", lb_algorithm="ROUND_ROBIN")
        loadbalancer = [{
            "loadbalancer": {
                "id": "loadbalancer-id"
            }
        }]
        subnets = []
        mock_has_calls = []
        networks = self._get_context()["tenant"]["networks"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet in subnets:
            mock_has_calls.append(mock.call(subnet_id="fake_subnet",
                                            project_id="fake_tenant"))
        loadbalancer_service.load_balancer_create.assert_has_calls(
            mock_has_calls)
        for lb in loadbalancer:
            self.assertEqual(
                1, loadbalancer_service.wait_for_loadbalancer_prov_status
                .call_count)
            self.assertEqual(1,
                             loadbalancer_service.pool_create.call_count)
            self.assertEqual(1,
                             loadbalancer_service.pool_show.call_count)
