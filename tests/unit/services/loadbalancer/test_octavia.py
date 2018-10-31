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

from rally.common import cfg
from rally import exceptions
from rally_openstack.services.loadbalancer import octavia
from tests.unit import test

BASE_PATH = "rally_openstack.services.loadbalancer"
CONF = cfg.CONF


class LoadBalancerServiceTestCase(test.TestCase):
    def setUp(self):
        super(LoadBalancerServiceTestCase, self).setUp()
        self.clients = mock.MagicMock()
        self.name_generator = mock.MagicMock()
        self.service = octavia.Octavia(self.clients,
                                       name_generator=self.name_generator)

    def atomic_actions(self):
        return self.service._atomic_actions

    def test_load_balancer_list(self):
        self.service.load_balancer_list(),
        self.service._clients.octavia().load_balancer_list \
            .assert_called_once_with()
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.load_balancer_list")

    def test_load_balancer_show(self):
        self.service.load_balancer_show("fake_lb")
        self.service._clients.octavia().load_balancer_show \
            .assert_called_once_with("fake_lb")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.load_balancer_show")

    def test_load_balancer_create(self):
        self.service.generate_random_name = mock.MagicMock(
            return_value="lb")
        self.service.load_balancer_create("fake_subnet")
        self.assertEqual(
            1, self.service._clients.octavia().load_balancer_create.call_count)
        self.service._clients.octavia().load_balancer_create \
            .assert_called_once_with(
            json={"loadbalancer":
                  {
                      "vip_subnet_id": "fake_subnet",
                      "name": "lb",
                      "admin_state_up": True
                  }})
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.load_balancer_create")

    def test_load_balancer_delete(self):
        self.service.load_balancer_delete("fake_lb")
        self.service._clients.octavia().load_balancer_delete \
            .assert_called_once_with("fake_lb")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.load_balancer_delete")

    def test_load_balancer_set(self):
        self.service.load_balancer_set("fake_lb", params={})
        self.service._clients.octavia().load_balancer_set \
            .assert_called_once_with("fake_lb", {})
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.load_balancer_set")

    def test_load_balancer_stats_show(self):
        self.assertEqual(
            self.service.load_balancer_stats_show(lb_id="fake_lb", kwargs={}),
            self.service._clients.octavia()
                .load_balancer_stats_show.return_value)
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.load_balancer_stats_show")

    def test_load_balancer_failover(self):
        self.service.load_balancer_failover(lb_id="fake_lb")
        self.service._clients.octavia().load_balancer_failover \
            .assert_called_once_with("fake_lb")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.load_balancer_failover")

    def test_listener_list(self):
        self.service.listener_list()
        self.service._clients.octavia().listener_list \
            .assert_called_once_with()
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.listener_list")

    def test_listener_show(self):
        self.service.listener_show(listener_id="listener_id")
        self.service._clients.octavia().listener_show \
            .assert_called_once_with("listener_id")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.listener_show")

    def test_listener_create(self):
        self.service.listener_create()
        self.service._clients.octavia().listener_create \
            .assert_called_once_with()
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.listener_create")

    def test_listener_delete(self):
        self.service.listener_delete(listener_id="listener_id")
        self.service._clients.octavia().listener_delete \
            .assert_called_once_with("listener_id")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.listener_delete")

    def test_listener_set(self):
        self.service.listener_set(listener_id="listener_id")
        self.service._clients.octavia().listener_set \
            .assert_called_once_with("listener_id")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.listener_set")

    def test_listener_stats_show(self):
        self.service.listener_stats_show(listener_id="listener_id")
        self.service._clients.octavia().listener_stats_show \
            .assert_called_once_with("listener_id")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.listener_stats_show")

    def test_pool_list(self):
        self.service.pool_list()
        self.service._clients.octavia().pool_list \
            .assert_called_once_with()
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.pool_list")

    def test_pool_create(self):
        self.service.pool_create()
        self.assertEqual(
            1, self.service._clients.octavia().pool_create.call_count)
        self.service._clients.octavia().pool_create.assert_called_once_with()
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.pool_create")

    def test_pool_delete(self):
        self.service.pool_delete(pool_id="fake_pool")
        self.service._clients.octavia().pool_delete \
            .assert_called_once_with("fake_pool")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.pool_delete")

    def test_pool_show(self):
        self.service.pool_show(pool_id="fake_pool")
        self.service._clients.octavia().pool_show \
            .assert_called_once_with("fake_pool")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.pool_show")

    def test_pool_set(self):
        self.service.pool_set(pool_id="fake_pool")
        self.service._clients.octavia().pool_set \
            .assert_called_once_with("fake_pool")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.pool_set")

    def test_member_list(self):
        self.service.member_list(pool_id="fake_pool")
        self.service._clients.octavia().member_list \
            .assert_called_once_with("fake_pool")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.member_list")

    def test_member_show(self):
        self.service.member_show(pool_id="fake_pool", member_id="fake_member")
        self.service._clients.octavia().member_show \
            .assert_called_once_with("fake_pool", "fake_member")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.member_show")

    def test_member_create(self):
        self.service.member_create(pool_id="fake_pool")
        self.service._clients.octavia().member_create \
            .assert_called_once_with("fake_pool")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.member_create")

    def test_member_delete(self):
        self.service.member_delete(
            pool_id="fake_pool", member_id="fake_member")
        self.service._clients.octavia().member_delete \
            .assert_called_once_with("fake_pool", "fake_member")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.member_delete")

    def test_member_set(self):
        self.service.member_set(pool_id="fake_pool", member_id="fake_member")
        self.service._clients.octavia().member_set \
            .assert_called_once_with("fake_pool", "fake_member")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.member_set")

    def test_l7policy_list(self):
        self.service.l7policy_list()
        self.service._clients.octavia().l7policy_list \
            .assert_called_once_with()
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.l7policy_list")

    def test_l7policy_create(self):
        self.service.l7policy_create()
        self.service._clients.octavia().l7policy_create \
            .assert_called_once_with()
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.l7policy_create")

    def test_l7policy_delete(self):
        self.service.l7policy_delete(l7policy_id="fake_policy")
        self.service._clients.octavia().l7policy_delete \
            .assert_called_once_with("fake_policy")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.l7policy_delete")

    def test_l7policy_show(self):
        self.service.l7policy_show(l7policy_id="fake_policy")
        self.service._clients.octavia().l7policy_show \
            .assert_called_once_with("fake_policy")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.l7policy_show")

    def test_l7policy_set(self):
        self.service.l7policy_set(l7policy_id="fake_policy")
        self.service._clients.octavia().l7policy_set \
            .assert_called_once_with("fake_policy")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.l7policy_set")

    def test_l7rule_list(self):
        self.service.l7rule_list(l7policy_id="fake_policy")
        self.service._clients.octavia().l7rule_list \
            .assert_called_once_with("fake_policy")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.l7rule_list")

    def test_l7rule_create(self):
        self.service.l7rule_create(l7policy_id="fake_policy")
        self.service._clients.octavia().l7rule_create \
            .assert_called_once_with("fake_policy")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.l7rule_create")

    def test_l7rule_delete(self):
        self.service.l7rule_delete(
            l7rule_id="fake_id", l7policy_id="fake_policy")
        self.service._clients.octavia().l7rule_delete \
            .assert_called_once_with("fake_id", "fake_policy")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.l7rule_delete")

    def test_l7rule_show(self):
        self.service.l7rule_show(
            l7rule_id="fake_id", l7policy_id="fake_policy")
        self.service._clients.octavia().l7rule_show \
            .assert_called_once_with("fake_id", "fake_policy")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.l7rule_show")

    def test_l7rule_set(self):
        self.service.l7rule_set(l7rule_id="fake_id", l7policy_id="fake_policy")
        self.service._clients.octavia().l7rule_set \
            .assert_called_once_with("fake_id", "fake_policy")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.l7rule_set")

    def test_health_monitor_list(self):
        self.service.health_monitor_list()
        self.service._clients.octavia().health_monitor_list \
            .assert_called_once_with()
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.health_monitor_list")

    def test_health_monitor_create(self):
        self.service.health_monitor_create()
        self.service._clients.octavia().health_monitor_create \
            .assert_called_once_with()
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.health_monitor_create")

    def test_health_monitor_delete(self):
        self.service.health_monitor_delete(health_monitor_id="fake_monitor_id")
        self.service._clients.octavia().health_monitor_delete \
            .assert_called_once_with("fake_monitor_id")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.health_monitor_delete")

    def test_health_monitor_show(self):
        self.service.health_monitor_show(health_monitor_id="fake_monitor_id")
        self.service._clients.octavia().health_monitor_show \
            .assert_called_once_with("fake_monitor_id")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.health_monitor_show")

    def test_health_monitor_set(self):
        self.service.health_monitor_set(health_monitor_id="fake_monitor_id")
        self.service._clients.octavia().health_monitor_set \
            .assert_called_once_with("fake_monitor_id")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.health_monitor_set")

    def test_quota_list(self):
        self.service.quota_list(params="fake_params")
        self.service._clients.octavia().quota_list\
            .assert_called_once_with("fake_params")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.quota_list")

    def test_quota_show(self):
        self.service.quota_show(project_id="fake_project")
        self.service._clients.octavia().quota_show\
            .assert_called_once_with("fake_project")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.quota_show")

    def test_quota_reset(self):
        self.service.quota_reset(project_id="fake_project")
        self.service._clients.octavia().quota_reset \
            .assert_called_once_with("fake_project")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.quota_reset")

    def test_quota_set(self):
        self.service.quota_set(project_id="fake_project",
                               params="fake_params")
        self.service._clients.octavia().quota_set \
            .assert_called_once_with("fake_project", "fake_params")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.quota_set")

    def test_quota_defaults_show(self):
        self.service.quota_defaults_show()
        self.service._clients.octavia().quota_defaults_show \
            .assert_called_once_with()
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.quota_defaults_show")

    def test_amphora_show(self):
        self.service.amphora_show(amphora_id="fake_amphora")
        self.service._clients.octavia().amphora_show \
            .assert_called_once_with("fake_amphora")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.amphora_show")

    def test_amphora_list(self):
        self.service.amphora_list()
        self.service._clients.octavia().amphora_list \
            .assert_called_once_with()
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.amphora_list")

    def test_update_loadbalancer_resource(self):
        fake_lb = {"id": "fake_lb"}
        self.service.update_loadbalancer_resource(lb=fake_lb)
        self.service._clients.octavia().load_balancer_show. \
            assert_called_once_with("fake_lb")

    def test_update_loadbalancer_resource_fail_404(self):
        fake_lb = {"id": "fake_lb"}
        ex = Exception()
        ex.status_code = 404
        self.service._clients.octavia().load_balancer_show.side_effect = \
            ex
        self.assertRaises(
            exceptions.GetResourceNotFound,
            self.service.update_loadbalancer_resource, fake_lb)

    def test_update_loadbalancer_resource_fail(self):
        fake_lb = {"id": "fake_lb"}
        ex = Exception()
        self.service._clients.octavia().load_balancer_show.side_effect = \
            ex
        self.assertRaises(
            exceptions.GetResourceFailure,
            self.service.update_loadbalancer_resource, fake_lb)

    @mock.patch("%s.Ocvita.wait_for_loadbalancer_prov_status" % BASE_PATH)
    def wait_for_loadbalancer_prov_status(self, mock_wait_for_status):
        fake_lb = {"loadbalancer": {}}
        self.service.wait_for_loadbalancer_prov_status(lb=fake_lb)
        self.assertTrue(mock_wait_for_status.called)
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "octavia.wait_for_loadbalancers")
