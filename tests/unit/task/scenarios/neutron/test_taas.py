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
                "tap_services": [
                    {"id": "service-0", "port_id": "port-0"},
                ],
            },
            "owner_id": "owner-uuid",
            "iteration": 1,
            "user_choice_method": "round_robin",
            "tenants": {"tenant-uuid": {}},
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

    @ddt.data(
        taas.CreateAndListTapServices,
        taas.CreateAndDeleteTapServices,
        taas.CreateAndUpdateTapServices,
    )
    def test_tap_services_use_context_ports(self, scenario_cls):
        scenario = scenario_cls()
        self._setup_scenario(scenario)
        scenario.context["iteration"] = 6

        scenario.run(tap_service_create_args={"description": "created"})

        scenario._clients.neutron.create_tap_service.assert_called_once_with(
            port_id="port-2", description="created")
        scenario._clients.neutron.create_network.assert_not_called()
        scenario._clients.neutron.create_port.assert_not_called()

    def test_create_and_list_tap_services(self):
        scenario = taas.CreateAndListTapServices()
        self._setup_scenario(scenario)

        scenario.run()

        scenario._clients.neutron.list_tap_services.assert_called_once_with()
        scenario._clients.neutron.delete_tap_service.assert_not_called()

    def test_create_and_delete_tap_services(self):
        scenario = taas.CreateAndDeleteTapServices()
        self._setup_scenario(scenario)
        client = scenario._clients.neutron
        client.create_tap_service.return_value = mock.Mock(id="service-id")

        scenario.run()

        client.delete_tap_service.assert_called_once_with("service-id")

    @ddt.data(None, {"description": "updated"}, {"description": ""})
    def test_create_and_update_tap_services(self, update_args):
        scenario = taas.CreateAndUpdateTapServices()
        self._setup_scenario(scenario)
        client = scenario._clients.neutron
        client.create_tap_service.return_value = mock.Mock(id="service-id")

        scenario.run(tap_service_update_args=update_args)

        client.update_tap_service.assert_called_once_with(
            "service-id", name="random_name",
            description=(update_args or {}).get("description"))

    def test_tap_service_names_are_generated(self):
        scenario = taas.CreateAndUpdateTapServices()
        self._setup_scenario(scenario)

        scenario.run(
            tap_service_create_args={"name": "custom-create"},
            tap_service_update_args={"name": "custom-update"})

        create_kwargs = (
            scenario._clients.neutron.create_tap_service.call_args.kwargs)
        self.assertNotIn("name", create_kwargs)
        update_kwargs = (
            scenario._clients.neutron.update_tap_service.call_args.kwargs)
        self.assertEqual("random_name", update_kwargs["name"])

    def test_create_and_list_tap_flows(self):
        scenario = taas.CreateAndListTapFlows()
        self._setup_scenario(scenario)

        scenario.run(description="created")

        scenario._clients.neutron.create_tap_flow.assert_called_once_with(
            tap_service_id="service-0", source_port="port-1",
            direction="IN", description="created")
        scenario._clients.neutron.list_tap_flows.assert_called_once_with()
        scenario._clients.neutron.delete_tap_flow.assert_not_called()

    @ddt.data("IN", "OUT", "BOTH")
    def test_create_and_list_tap_flows_direction(self, direction):
        scenario = taas.CreateAndListTapFlows()
        self._setup_scenario(scenario)

        scenario.run(direction=direction)

        create_kwargs = (
            scenario._clients.neutron.create_tap_flow.call_args.kwargs)
        self.assertEqual(direction, create_kwargs["direction"])

    @ddt.data(None, "created", "")
    def test_create_and_delete_tap_flows(self, description):
        scenario = taas.CreateAndDeleteTapFlows()
        self._setup_scenario(scenario)
        client = scenario._clients.neutron
        client.create_tap_flow.return_value = mock.Mock(id="flow-id")

        scenario.run(description=description)

        client.create_tap_flow.assert_called_once_with(
            tap_service_id="service-0", source_port="port-1",
            direction="IN", description=description)
        client.delete_tap_flow.assert_called_once_with("flow-id")

    @ddt.data(None, {"description": "updated"}, {"description": ""})
    def test_create_and_update_tap_flows(self, update_args):
        scenario = taas.CreateAndUpdateTapFlows()
        self._setup_scenario(scenario)
        client = scenario._clients.neutron
        client.create_tap_flow.return_value = mock.Mock(id="flow-id")

        scenario.run(description="created", tap_flow_update_args=update_args)

        client.create_tap_flow.assert_called_once_with(
            tap_service_id="service-0", source_port="port-1",
            direction="IN", description="created")

        client.update_tap_flow.assert_called_once_with(
            "flow-id", name="random_name",
            description=(update_args or {}).get("description"))

    def test_tap_flow_source_port_distinct_from_destinations(self):
        scenario = taas.CreateAndListTapFlows()
        self._setup_scenario(scenario)
        scenario.context["tenant"]["tap_services"] = [
            {"id": "service-0", "port_id": "port-0"},
            {"id": "service-1", "port_id": "port-1"},
        ]
        dest_ports = {"port-0", "port-1"}

        for iteration in range(4):
            scenario.context["iteration"] = iteration
            scenario._clients.neutron.create_tap_flow.reset_mock()

            scenario.run()

            create_kwargs = (
                scenario._clients.neutron.create_tap_flow.call_args.kwargs)
            self.assertNotIn(create_kwargs["source_port"], dest_ports)

    def test_tap_flow_endpoint_rotation(self):
        scenario = taas.CreateAndListTapFlows()
        self._setup_scenario(scenario)
        scenario.context["tenant"]["tap_services"] = [
            {"id": "service-0", "port_id": "port-0"},
            {"id": "service-1", "port_id": "port-1"},
        ]
        scenario.context["iteration"] = 1

        scenario.run()

        create_kwargs = (
            scenario._clients.neutron.create_tap_flow.call_args.kwargs)
        self.assertEqual("service-0", create_kwargs["tap_service_id"])
        self.assertEqual("port-2", create_kwargs["source_port"])

    @ddt.data(1, 2)
    def test_flow_rotation_with_multiple_projects(self, first_iteration):
        scenario = taas.CreateAndListTapFlows()
        self._setup_scenario(scenario)
        scenario.context["user_choice_method"] = "round_robin"
        scenario.context["tenants"] = {"project-a": {}, "project-b": {}}
        scenario.context["tenant"]["tap_services"] = [
            {"id": "service-0", "port_id": "port-0"},
            {"id": "service-1", "port_id": "port-1"},
        ]
        selected = []
        for iteration in range(first_iteration, first_iteration + 8, 2):
            scenario.context["iteration"] = iteration
            service, port = scenario._select_flow_endpoints()
            selected.append((service["id"], port["id"]))

        self.assertEqual(
            [("service-0", "port-2"), ("service-1", "port-3")] * 2,
            selected)

    def test_flow_selection_with_random_projects(self):
        scenario = taas.CreateAndListTapFlows()
        self._setup_scenario(scenario)
        scenario.context["user_choice_method"] = "random"
        with mock.patch.object(taas.random, "randrange",
                               side_effect=[0, 2]) as mock_randrange:
            service, port = scenario._select_flow_endpoints()

        self.assertEqual("service-0", service["id"])
        self.assertEqual("port-3", port["id"])
        self.assertEqual([mock.call(1), mock.call(3)],
                         mock_randrange.call_args_list)

    def test_flow_selection_without_source_ports(self):
        scenario = taas.CreateAndListTapFlows()
        self._setup_scenario(scenario)
        scenario.context["tenant"]["ports"] = [{"id": "port-0"}]

        self.assertRaises(ValueError, scenario._select_flow_endpoints)

    def test_tap_flow_names_are_generated(self):
        scenario = taas.CreateAndUpdateTapFlows()
        self._setup_scenario(scenario)
        scenario._clients.neutron.create_tap_flow.return_value = mock.Mock(
            id="flow-id")

        scenario.run(
            tap_flow_update_args={"name": "custom-update"})

        create_kwargs = (
            scenario._clients.neutron.create_tap_flow.call_args.kwargs)
        self.assertNotIn("name", create_kwargs)
        update_kwargs = (
            scenario._clients.neutron.update_tap_flow.call_args.kwargs)
        self.assertEqual("random_name", update_kwargs["name"])
