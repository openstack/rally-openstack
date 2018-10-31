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

import mock

from rally_openstack.scenarios.octavia import loadbalancers
from tests.unit import test


class LoadBalancersTestCase(test.ScenarioTestCase):

    def get_test_context(self):
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

    def setUp(self):
        super(LoadBalancersTestCase, self).setUp()
        patch = mock.patch(
            "rally_openstack.services.loadbalancer.octavia.Octavia")
        self.addCleanup(patch.stop)
        self.mock_loadbalancers = patch.start()

    def test_loadbalancers(self):
        loadbalancer_service = self.mock_loadbalancers.return_value
        scenario = loadbalancers.CreateAndListLoadbalancers(self.context)
        scenario.run()

        networks = self.context["tenant"]["networks"]
        subnets = []
        mock_has_calls = []
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet_id in subnets:
            mock_has_calls.append(mock.call(subnet_id))
        loadbalancer_service.load_balancer_create.assert_called_once_with(
            subnet_id)
        self.assertEqual(1, loadbalancer_service.load_balancer_list.call_count)
