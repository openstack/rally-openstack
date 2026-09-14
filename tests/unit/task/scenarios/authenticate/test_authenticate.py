# Copyright (C) 2014 Yahoo! Inc. All Rights Reserved.
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

from rally_openstack.task.scenarios.authenticate import authenticate
from tests.unit import test


class AuthenticateTestCase(test.ScenarioTestCase):

    def test_keystone(self):
        scenario_inst = authenticate.Keystone()
        scenario_inst.run()
        self.assertTrue(self.client_created("keystone"))
        self._test_atomic_action_timer(scenario_inst.atomic_actions(),
                                       "authenticate.keystone")

    def test_validate_glance(self):
        clients = mock.Mock()
        scenario_inst = authenticate.ValidateGlance(clients=clients)
        scenario_inst.run(5)

        self.assertEqual(
            [mock.call(name="__intentionally_non_existent_image___")] * 5,
            clients.glance.list_images.call_args_list)
        self._test_atomic_action_timer(scenario_inst.atomic_actions(),
                                       "authenticate.validate_glance")

    def test_validate_nova(self):
        scenario_inst = authenticate.ValidateNova()
        scenario_inst.run(5)
        self.clients("nova").flavors.list.assert_has_calls([mock.call()] * 5)
        self._test_atomic_action_timer(scenario_inst.atomic_actions(),
                                       "authenticate.validate_nova")

    def test_validate_ceilometer(self):
        scenario_inst = authenticate.ValidateCeilometer()
        scenario_inst.run(5)
        self.clients("ceilometer").meters.list.assert_has_calls(
            [mock.call()] * 5)
        self._test_atomic_action_timer(
            scenario_inst.atomic_actions(),
            "authenticate.validate_ceilometer")

    def test_validate_cinder(self):
        scenario_inst = authenticate.ValidateCinder()
        scenario_inst.run(5)
        self.clients("cinder").volume_types.list.assert_has_calls(
            [mock.call()] * 5)
        self._test_atomic_action_timer(scenario_inst.atomic_actions(),
                                       "authenticate.validate_cinder")

    def test_validate_neutron(self):
        scenario_inst = authenticate.ValidateNeutron()
        scenario_inst.run(5)
        self.clients("neutron").list_networks.assert_has_calls(
            [mock.call()] * 5)
        self._test_atomic_action_timer(scenario_inst.atomic_actions(),
                                       "authenticate.validate_neutron")

    def test_validate_octavia(self):
        scenario_inst = authenticate.ValidateOctavia()
        scenario_inst.run(5)
        self.clients("octavia").load_balancer_list.assert_has_calls(
            [mock.call()] * 5)
        self._test_atomic_action_timer(scenario_inst.atomic_actions(),
                                       "authenticate.validate_octavia")

    def test_validate_heat(self):
        scenario_inst = authenticate.ValidateHeat()
        scenario_inst.run(5)
        self.assertCountEqual(
            self.clients("heat").stacks.list.call_args_list,
            [mock.call(limit=0)] * 5)
        self._test_atomic_action_timer(scenario_inst.atomic_actions(),
                                       "authenticate.validate_heat")
