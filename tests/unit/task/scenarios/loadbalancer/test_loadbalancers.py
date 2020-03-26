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

from rally_openstack.task.scenarios.octavia import loadbalancers
from tests.unit import test


class LoadBalancersTestCase(test.ScenarioTestCase):

    def setUp(self):
        super(LoadBalancersTestCase, self).setUp()
        patch = mock.patch(
            "rally_openstack.common.services.loadbalancer.octavia.Octavia")
        self.addCleanup(patch.stop)
        self.mock_loadbalancers = patch.start()

    def _get_context(self):
        context = super(LoadBalancersTestCase, self).get_test_context()
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

    def test_create_and_list_loadbalancers(self):
        loadbalancer_service = self.mock_loadbalancers.return_value
        scenario = loadbalancers.CreateAndListLoadbalancers(
            self._get_context())
        scenario.run()

        loadbalancer_service.load_balancer_list.assert_called_once_with()

    def test_create_and_delete_loadbalancers(self):
        loadbalancer_service = self.mock_loadbalancers.return_value
        scenario = loadbalancers.CreateAndDeleteLoadbalancers(
            self._get_context())
        scenario.run()
        lb = [{
            "loadbalancer": {
                "id": "loadbalancer-id"
            }
        }]
        loadbalancer_service.load_balancer_create.return_value = lb
        loadbalancer_service.load_balancer_create(
            admin_state=True, description=None, flavor_id=None,
            listeners=None, provider=None,
            subnet_id="fake_subnet", vip_qos_policy_id=None)
        self.assertEqual(1,
                         loadbalancer_service.load_balancer_delete.call_count)

    def test_create_and_update_loadbalancers(self):
        loadbalancer_service = self.mock_loadbalancers.return_value
        scenario = loadbalancers.CreateAndUpdateLoadBalancers(
            self._get_context())
        scenario.run()
        lb = [{
            "loadbalancer": {
                "id": "loadbalancer-id"
            }
        }]
        loadbalancer_service.load_balancer_create.return_value = lb
        loadbalancer_service.load_balancer_create(
            admin_state=True, description=None, flavor_id=None,
            listeners=None, provider=None,
            subnet_id="fake_subnet", vip_qos_policy_id=None)
        self.assertEqual(1,
                         loadbalancer_service.load_balancer_set.call_count)

    def test_create_and_show_stats(self):
        loadbalancer_service = self.mock_loadbalancers.return_value
        scenario = loadbalancers.CreateAndShowStatsLoadBalancers(
            self._get_context())
        scenario.run()
        lb = [{
            "loadbalancer": {
                "id": "loadbalancer-id"
            }
        }]
        loadbalancer_service.load_balancer_create.return_value = lb
        loadbalancer_service.load_balancer_create(
            admin_state=True, description=None, flavor_id=None,
            listeners=None, provider=None,
            subnet_id="fake_subnet", vip_qos_policy_id=None)
        self.assertEqual(
            1, loadbalancer_service.load_balancer_stats_show.call_count)

    def test_create_and_show_loadbalancers(self):
        loadbalancer_service = self.mock_loadbalancers.return_value
        scenario = loadbalancers.CreateAndShowLoadBalancers(
            self._get_context())
        scenario.run()
        lb = [{
            "loadbalancer": {
                "id": "loadbalancer-id"
            }
        }]
        lb_show = {"id": "loadbalancer-id"}
        loadbalancer_service.load_balancer_create.return_value = lb
        loadbalancer_service.load_balancer_show.return_value = lb_show
        loadbalancer_service.load_balancer_create(
            admin_state=True, description=None, flavor_id=None,
            listeners=None, provider=None,
            subnet_id="fake_subnet", vip_qos_policy_id=None)
        self.assertEqual(1,
                         loadbalancer_service.load_balancer_show.call_count)
