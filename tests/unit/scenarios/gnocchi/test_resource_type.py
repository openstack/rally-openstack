# Copyright 2017 Red Hat, Inc. <http://www.redhat.com>
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

from rally_openstack.scenarios.gnocchi import resource_type
from tests.unit import test


class GnocchiResourceTypeTestCase(test.ScenarioTestCase):

    def get_test_context(self):
        context = super(GnocchiResourceTypeTestCase, self).get_test_context()
        context.update({
            "admin": {
                "user_id": "fake",
                "credential": mock.MagicMock()
            },
            "user": {
                "user_id": "fake",
                "credential": mock.MagicMock()
            },
            "tenant": {"id": "fake"}
        })
        return context

    def setUp(self):
        super(GnocchiResourceTypeTestCase, self).setUp()
        patch = mock.patch(
            "rally_openstack.services.gnocchi.metric.GnocchiService")
        self.addCleanup(patch.stop)
        self.mock_metric = patch.start()

    def test_list_resource_type(self):
        metric_service = self.mock_metric.return_value
        scenario = resource_type.ListResourceType(self.context)
        scenario.run()
        metric_service.list_resource_type.assert_called_once_with()

    def test_create_resource_type(self):
        metric_service = self.mock_metric.return_value
        scenario = resource_type.CreateResourceType(self.context)
        scenario.generate_random_name = mock.MagicMock(return_value="name")
        attrs = {"foo": {"required": "false", "type": "bool"}}

        scenario.run(attributes=attrs)
        metric_service.create_resource_type.assert_called_once_with(
            "name", attributes=attrs)

    def test_create_delete_resource_type(self):
        metric_service = self.mock_metric.return_value
        scenario = resource_type.CreateDeleteResourceType(self.context)
        scenario.generate_random_name = mock.MagicMock(return_value="name")
        attrs = {"bar": {"required": "true", "type": "number", "max": 7}}

        scenario.run(attributes=attrs)
        metric_service.create_resource_type.assert_called_once_with(
            "name", attributes=attrs)
        metric_service.delete_resource_type.assert_called_once_with(
            "name")
