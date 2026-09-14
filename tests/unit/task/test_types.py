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

import ddt

from rally import exceptions
from rally.task import scenario

from rally_openstack.common.clients import glance
from rally_openstack.task import types
from tests.unit import fakes
from tests.unit import test


class FlavorTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.clients = fakes.FakeClients()
        self.clients.nova().flavors._cache(fakes.FakeResource(name="m1.tiny",
                                                              id="1"))
        self.clients.nova().flavors._cache(fakes.FakeResource(name="m1.nano",
                                                              id="42"))
        self.clients.nova().flavors._cache(fakes.FakeResource(name="m1.large",
                                                              id="44"))
        self.clients.nova().flavors._cache(fakes.FakeResource(name="m1.large",
                                                              id="45"))
        self.type_cls = types.Flavor(
            context={"admin": {"credential": mock.Mock()}},
            scenario_cls=scenario.Scenario)
        self.type_cls._clients = self.clients

    def test_preprocess_by_id(self):
        resource_spec = {"id": "42"}
        flavor_id = self.type_cls.pre_process(
            resource_spec=resource_spec, config={}, output_type=str)
        self.assertEqual("42", flavor_id)

    def test_preprocess_by_name(self):
        resource_spec = {"name": "m1.nano"}
        flavor_id = self.type_cls.pre_process(
            resource_spec=resource_spec, config={}, output_type=str)
        self.assertEqual("42", flavor_id)

    def test_preprocess_by_name_no_match(self):
        resource_spec = {"name": "m1.medium"}
        self.assertRaises(exceptions.InvalidScenarioArgument,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)

    def test_preprocess_by_name_multiple_match(self):
        resource_spec = {"name": "m1.large"}
        self.assertRaises(exceptions.InvalidScenarioArgument,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)

    def test_preprocess_by_regex(self):
        resource_spec = {"regex": r"m(1|2)\.nano"}
        flavor_id = self.type_cls.pre_process(
            resource_spec=resource_spec, config={}, output_type=str)
        self.assertEqual("42", flavor_id)

    def test_preprocess_by_regex_multiple_match(self):
        resource_spec = {"regex": "^m1"}
        self.assertRaises(exceptions.InvalidScenarioArgument,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)

    def test_preprocess_by_regex_no_match(self):
        resource_spec = {}
        self.assertRaises(exceptions.InvalidScenarioArgument,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)


class GlanceImageTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.clients = mock.Mock()
        self.glance = self.clients.glance
        self.type_cls = types.GlanceImage(
            context={"admin": {"credential": mock.Mock()}},
            scenario_cls=scenario.Scenario)
        self.type_cls._clients = self.clients

    def pre_process(self, resource_spec):
        return self.type_cls.pre_process(
            resource_spec=resource_spec, config={}, output_type=str)

    def test_preprocess_by_id(self):
        self.assertEqual("100", self.pre_process({"id": "100"}))
        self.assertFalse(self.glance.find_image.called)

    def test_preprocess_by_name(self):
        self.glance.find_image.return_value = mock.Mock(id="100")
        self.assertEqual("100", self.pre_process({"name": "cirros"}))
        self.glance.find_image.assert_called_once_with(name="cirros")

    def test_preprocess_passes_every_filter_on(self):
        self.glance.find_image.return_value = mock.Mock(id="100")
        self.pre_process({"regex": "^cirros", "accurate": True,
                          "status": "active", "visibility": "public",
                          "owner": "tenant-id"})
        self.glance.find_image.assert_called_once_with(
            regex="^cirros", accurate=True, status="active",
            visibility="public", owner="tenant-id")

    def test_preprocess_list_kwargs_drops_unknowns_and_maps_is_public(self):
        self.glance.find_image.return_value = mock.Mock(id="100")

        self.pre_process({"name": "cirros",
                          "list_kwargs": {"is_public": True,
                                          "owner": "tenant-id",
                                          "multiple": True}})
        self.glance.find_image.assert_called_once_with(
            name="cirros", owner="tenant-id",
            visibility=glance.Visibility.PUBLIC)

        self.glance.find_image.reset_mock()
        self.pre_process({"name": "cirros", "visibility": "shared",
                          "list_kwargs": {"is_public": True}})
        self.glance.find_image.assert_called_once_with(
            name="cirros", visibility="shared")

    def test_preprocess_by_the_deprecated_list_kwargs(self):
        self.glance.find_image.return_value = mock.Mock(id="100")
        for spec, expected in (
            ({"name": "cirros",
              "list_kwargs": {"status": "active", "owner": "tenant-id"}},
             {"name": "cirros", "status": "active", "owner": "tenant-id"}),
            # a filter of its own wins over its list_kwargs twin
            ({"name": "cirros", "owner": "mine",
              "list_kwargs": {"owner": "theirs"}},
             {"name": "cirros", "owner": "mine"}),
        ):
            with self.subTest(spec["list_kwargs"]):
                self.glance.find_image.reset_mock()
                self.pre_process(spec)
                self.glance.find_image.assert_called_once_with(**expected)

    def test_preprocess_not_found(self):
        # the client speaks of resources, a resource type of task arguments
        self.glance.find_image.side_effect = exceptions.GetResourceNotFound(
            resource="image named 'cirros'")
        e = self.assertRaises(exceptions.InvalidScenarioArgument,
                              self.pre_process, {"name": "cirros"})
        self.assertIn("image named 'cirros' is not found", e.format_message())

    def test_preprocess_caches_the_lookup(self):
        self.glance.find_image.return_value = mock.Mock(id="100")

        self.assertEqual("100", self.pre_process({"name": "cirros"}))
        self.assertEqual("100", self.pre_process({"name": "cirros"}))
        self.glance.find_image.assert_called_once_with(name="cirros")

        self.glance.find_image.return_value = mock.Mock(id="101")
        self.assertEqual("101", self.pre_process({"name": "other"}))


@ddt.ddt
class GlanceImageArgsTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.type_cls = types.GlanceImageArguments(
            {}, scenario_cls=scenario.Scenario)

    @ddt.data(
        {"resource_spec": {}, "expected": {}},
        {"resource_spec": {"visibility": "public"},
         "expected": {"visibility": "public"}},
        {"resource_spec": {"visibility": "public", "is_public": False},
         "expected": {"visibility": "public"}},
        {"resource_spec": {"is_public": False},
         "expected": {"visibility": "private"}},
        {"resource_spec": {"is_public": True},
         "expected": {"visibility": "public"}},
    )
    @ddt.unpack
    def test_preprocess(self, resource_spec, expected):
        self.assertEqual(
            expected,
            self.type_cls.pre_process(resource_spec=resource_spec, config={},
                                      output_type=dict))


class EC2ImageTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.clients = fakes.FakeClients()
        image1 = fakes.FakeResource(name="cirros-0.5.2-uec", id="100")
        self.clients.glance().images._cache(image1)
        image2 = fakes.FakeResource(name="cirros-0.5.2-uec-ramdisk", id="102")
        self.clients.glance().images._cache(image2)
        image3 = fakes.FakeResource(name="cirros-0.5.2-uec-ramdisk-copy",
                                    id="102")
        self.clients.glance().images._cache(image3)
        image4 = fakes.FakeResource(name="cirros-0.5.2-uec-ramdisk-copy",
                                    id="103")
        self.clients.glance().images._cache(image4)

        ec2_image1 = fakes.FakeResource(name="cirros-0.5.2-uec", id="200")
        ec2_image2 = fakes.FakeResource(name="cirros-0.5.2-uec-ramdisk",
                                        id="201")
        ec2_image3 = fakes.FakeResource(name="cirros-0.5.2-uec-ramdisk-copy",
                                        id="202")
        ec2_image4 = fakes.FakeResource(name="cirros-0.5.2-uec-ramdisk-copy",
                                        id="203")

        self.clients.ec2().get_all_images = mock.Mock(
            return_value=[ec2_image1, ec2_image2, ec2_image3, ec2_image4])

        self.type_cls = types.EC2Image(
            context={"admin": {"credential": mock.Mock()}},
            scenario_cls=scenario.Scenario)
        self.type_cls._clients = self.clients

    def test_preprocess_by_name(self):
        resource_spec = {"name": "^cirros-0.5.2-uec$"}
        ec2_image_id = self.type_cls.pre_process(resource_spec=resource_spec,
                                                 config={}, output_type=str)
        self.assertEqual("200", ec2_image_id)

    def test_preprocess_by_id(self):
        resource_spec = {"id": "100"}
        ec2_image_id = self.type_cls.pre_process(resource_spec=resource_spec,
                                                 config={}, output_type=str)
        self.assertEqual("200", ec2_image_id)

    def test_preprocess_by_id_no_match(self):
        resource_spec = {"id": "101"}
        self.assertRaises(exceptions.InvalidScenarioArgument,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)

    def test_preprocess_by_name_no_match(self):
        resource_spec = {"name": "cirros-0.5.2-uec-boot"}
        self.assertRaises(exceptions.InvalidScenarioArgument,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)

    def test_preprocess_by_name_match_multiple(self):
        resource_spec = {"name": "cirros-0.5.2-uec-ramdisk-copy"}
        self.assertRaises(exceptions.InvalidScenarioArgument,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)

    def test_preprocess_by_regex(self):
        resource_spec = {"regex": "-uec$"}
        ec2_image_id = self.type_cls.pre_process(resource_spec=resource_spec,
                                                 config={}, output_type=str)
        self.assertEqual("200", ec2_image_id)

    def test_preprocess_by_regex_match_multiple(self):
        resource_spec = {"regex": "^cirros"}
        self.assertRaises(exceptions.InvalidScenarioArgument,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)

    def test_preprocess_by_regex_no_match(self):
        resource_spec = {"regex": "-boot$"}
        self.assertRaises(exceptions.InvalidScenarioArgument,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)


class VolumeTypeTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        cinder = mock.patch("rally_openstack.task.types.block.BlockStorage")
        self.service = cinder.start().return_value
        self.addCleanup(cinder.stop)

        volume_type1 = fakes.FakeResource(name="lvmdriver-1", id=100)

        self.type_cls = types.VolumeType(
            context={"admin": {"credential": mock.Mock()}},
            scenario_cls=scenario.Scenario)
        self.service.list_types.return_value = [volume_type1]

    def test_preprocess_by_id(self):
        resource_spec = {"id": 100}
        volumetype_id = self.type_cls.pre_process(resource_spec=resource_spec,
                                                  config={}, output_type=str)
        self.assertEqual(100, volumetype_id)

    def test_preprocess_by_name(self):
        resource_spec = {"name": "lvmdriver-1"}
        volumetype_id = self.type_cls.pre_process(resource_spec=resource_spec,
                                                  config={}, output_type=str)
        self.assertEqual(100, volumetype_id)

    def test_preprocess_by_name_no_match(self):
        resource_spec = {"name": "nomatch-1"}
        self.assertRaises(exceptions.InvalidScenarioArgument,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)

    def test_preprocess_by_regex(self):
        resource_spec = {"regex": "^lvm.*-1"}
        volumetype_id = self.type_cls.pre_process(resource_spec=resource_spec,
                                                  config={}, output_type=str)
        self.assertEqual(100, volumetype_id)

    def test_preprocess_by_regex_no_match(self):
        resource_spec = {"regex": "dd"}
        self.assertRaises(exceptions.InvalidScenarioArgument,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)


class NeutronNetworkTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.clients = fakes.FakeClients()
        net1_data = {"network": {
            "name": "net1"
        }}
        network1 = self.clients.neutron().create_network(net1_data)
        self.net1_id = network1["network"]["id"]
        self.type_cls = types.NeutronNetwork(
            context={"admin": {"credential": mock.Mock()}},
            scenario_cls=scenario.Scenario)
        self.type_cls._clients = self.clients

    def test_preprocess_by_id(self):
        resource_spec = {"id": self.net1_id}
        network_id = self.type_cls.pre_process(resource_spec=resource_spec,
                                               config={}, output_type=str)
        self.assertEqual(network_id, self.net1_id)

    def test_preprocess_by_name(self):
        resource_spec = {"name": "net1"}
        network_id = self.type_cls.pre_process(resource_spec=resource_spec,
                                               config={}, output_type=str)
        self.assertEqual(network_id, self.net1_id)

    def test_preprocess_by_name_no_match(self):
        resource_spec = {"name": "nomatch-1"}
        self.assertRaises(exceptions.InvalidScenarioArgument,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)


class WatcherStrategyTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.clients = fakes.FakeClients()
        self.strategy = self.clients.watcher().strategy._cache(
            fakes.FakeResource(name="dummy", id="1"))

        self.type_cls = types.WatcherStrategy(
            context={"admin": {"credential": mock.Mock()}},
            scenario_cls=scenario.Scenario)
        self.type_cls._clients = self.clients

    def test_preprocess_by_name(self):
        resource_spec = {"name": "dummy"}
        strategy_id = self.type_cls.pre_process(resource_spec=resource_spec,
                                                config={}, output_type=str)
        self.assertEqual(self.strategy.uuid, strategy_id)

    def test_preprocess_by_name_no_match(self):
        resource_spec = {"name": "dummy-1"}
        self.assertRaises(exceptions.RallyException,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)


class WatcherGoalTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.clients = fakes.FakeClients()
        self.goal = self.clients.watcher().goal._cache(
            fakes.FakeResource(name="dummy", id="1"))
        self.type_cls = types.WatcherGoal(
            context={"admin": {"credential": mock.Mock()}},
            scenario_cls=scenario.Scenario)
        self.type_cls._clients = self.clients

    def test_preprocess_by_name(self):
        resource_spec = {"name": "dummy"}
        goal_id = self.type_cls.pre_process(resource_spec=resource_spec,
                                            config={}, output_type=str)
        self.assertEqual(self.goal.uuid, goal_id)

    def test_preprocess_by_name_no_match(self):
        resource_spec = {"name": "dummy-1"}
        self.assertRaises(exceptions.RallyException,
                          self.type_cls.pre_process,
                          resource_spec=resource_spec, config={},
                          output_type=str)
