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

from rally_openstack.common.clients import neutron as neutron_client
from rally_openstack.task.scenarios.neutron import taas
from tests.unit import test


class TaaSScenarioTestCase(test.ScenarioTestCase):
    """Tests for TaaSScenario tunnel ID allocation."""

    def setUp(self):
        super().setUp()
        self.context.update({
            "tenant": {"id": "tenant-uuid"},
            "owner_id": "owner-uuid",
            "iteration": 5,
        })
        self.scenario = taas.TaaSScenario(
            self.context, clients=mock.MagicMock())

    def test_allocate_directions_stable(self):
        directions = self.scenario._allocate_directions(
            ("IN",), neutron_client.MirrorType.GRE)
        again = self.scenario._allocate_directions(
            ("IN",), neutron_client.MirrorType.GRE)

        self.assertEqual(directions, again)
        self.assertEqual(1, len(directions))
        self.assertIn("IN", directions)

    def test_allocate_directions_different_iteration(self):
        first = self.scenario._allocate_directions(
            ("IN",), neutron_client.MirrorType.GRE)
        self.context["iteration"] = 6
        second = self.scenario._allocate_directions(
            ("IN",), neutron_client.MirrorType.GRE)

        self.assertNotEqual(first["IN"], second["IN"])

    def test_allocate_directions_in_and_out_differ(self):
        directions = self.scenario._allocate_directions(
            ("IN", "OUT"), neutron_client.MirrorType.GRE)

        self.assertNotEqual(directions["IN"], directions["OUT"])

    def test_allocate_directions_erspan_range(self):
        directions = self.scenario._allocate_directions(
            ("IN",), neutron_client.MirrorType.ERSPANV1)

        self.assertGreaterEqual(directions["IN"], 1)
        self.assertLessEqual(directions["IN"], 1023)

    def test_allocate_directions_gre_range(self):
        directions = self.scenario._allocate_directions(
            ("IN",), neutron_client.MirrorType.GRE)

        self.assertGreaterEqual(directions["IN"], 1)
        self.assertLessEqual(directions["IN"], 16777215)

    def test_mirror_type_from_string(self):
        result = self.scenario._mirror_type("gre")

        self.assertEqual(neutron_client.MirrorType.GRE, result)

    def test_mirror_type_passthrough(self):
        result = self.scenario._mirror_type(neutron_client.MirrorType.ERSPANV1)

        self.assertEqual(neutron_client.MirrorType.ERSPANV1, result)


@ddt.ddt
class NeutronTaaSTestCase(test.TestCase):

    def _setup_scenario(self, scenario):
        scenario._clients = mock.MagicMock()
        scenario._clients.neutron = mock.MagicMock()
        scenario.generate_random_name = mock.Mock(
            return_value="random_name")
        scenario.context = {
            "tenant": {
                "id": "tenant-uuid",
                "ports": [
                    {"id": "port-0"},
                    {"id": "port-1"},
                    {"id": "port-2"},
                    {"id": "port-3"},
                ],
            },
            "owner_id": "owner-uuid",
            "iteration": 1,
        }

    @ddt.data(
        {"remote_ip": "10.0.0.50"},
        {"remote_ip": "10.0.0.50",
         "mirror_type": neutron_client.MirrorType.ERSPANV1},
        {"remote_ip": "10.0.0.50", "mirror_directions": ("OUT",)},
    )
    @ddt.unpack
    def test_create_and_list_tap_mirrors(
        self, remote_ip, mirror_type=neutron_client.MirrorType.GRE,
        mirror_directions=("IN",),
    ):
        scenario = taas.CreateAndListTapMirrors()
        self._setup_scenario(scenario)

        scenario.run(
            remote_ip=remote_ip,
            mirror_type=mirror_type,
            mirror_directions=mirror_directions,
        )

        scenario._clients.neutron.create_tap_mirror.assert_called_once()
        scenario._clients.neutron.list_tap_mirrors.assert_called_once()
        create_kwargs = (
            scenario._clients.neutron.create_tap_mirror.call_args.kwargs)
        self.assertEqual("port-1", create_kwargs["port_id"])
        self.assertEqual(remote_ip, create_kwargs["remote_ip"])
        self.assertEqual(mirror_type, create_kwargs["mirror_type"])
        self.assertEqual(
            set(mirror_directions), set(create_kwargs["directions"]))

    def test_create_and_list_port_rotation(self):
        scenario = taas.CreateAndListTapMirrors()
        self._setup_scenario(scenario)
        scenario.context["iteration"] = 3

        scenario.run(remote_ip="10.0.0.50")

        create_kwargs = (
            scenario._clients.neutron.create_tap_mirror.call_args.kwargs)
        self.assertEqual("port-3", create_kwargs["port_id"])

    @ddt.data(
        {"remote_ip": "10.0.0.50"},
        {"remote_ip": "10.0.0.50", "mirror_directions": ("IN", "OUT")},
        {"remote_ip": "10.0.0.50", "mirror_type": "erspanv1"},
    )
    @ddt.unpack
    def test_create_and_delete_tap_mirrors(
        self, remote_ip, mirror_directions=("IN",),
        mirror_type=neutron_client.MirrorType.GRE,
    ):
        scenario = taas.CreateAndDeleteTapMirrors()
        self._setup_scenario(scenario)
        tap_mirror = mock.MagicMock(id="mirror-id")
        scenario._clients.neutron.create_tap_mirror.return_value = tap_mirror

        scenario.run(
            remote_ip=remote_ip,
            mirror_directions=mirror_directions,
            mirror_type=mirror_type,
        )

        scenario._clients.neutron.create_tap_mirror.assert_called_once()
        scenario._clients.neutron.delete_tap_mirror.assert_called_once_with(
            "mirror-id")

    @ddt.data(
        {"remote_ip": "10.0.0.50"},
        {"remote_ip": "10.0.0.50", "tap_mirror_update_args": {
            "description": "updated"}},
    )
    @ddt.unpack
    def test_create_and_update_tap_mirrors(
        self, remote_ip, tap_mirror_update_args=None,
    ):
        scenario = taas.CreateAndUpdateTapMirrors()
        self._setup_scenario(scenario)
        tap_mirror = mock.MagicMock(id="mirror-id")
        scenario._clients.neutron.create_tap_mirror.return_value = tap_mirror

        scenario.run(
            remote_ip=remote_ip,
            tap_mirror_update_args=tap_mirror_update_args,
        )

        scenario._clients.neutron.create_tap_mirror.assert_called_once()
        update_kwargs = (
            scenario._clients.neutron.update_tap_mirror.call_args)
        self.assertEqual("mirror-id", update_kwargs.args[0])
        self.assertEqual("random_name", update_kwargs.kwargs["name"])
        expected_desc = (tap_mirror_update_args or {}).get("description")
        self.assertEqual(expected_desc, update_kwargs.kwargs["description"])

    def test_create_and_list_no_name_in_create_args(self):
        """Verify user cannot specify name (breaks cleanup)."""
        scenario = taas.CreateAndListTapMirrors()
        self._setup_scenario(scenario)

        scenario.run(remote_ip="10.0.0.50")

        create_kwargs = (
            scenario._clients.neutron.create_tap_mirror.call_args.kwargs)
        self.assertNotIn("name", create_kwargs)
