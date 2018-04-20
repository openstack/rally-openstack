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

from rally_openstack.scenarios.gnocchi import resource
from tests.unit import test


class GnocchiResourceTestCase(test.ScenarioTestCase):

    def get_test_context(self):
        context = super(GnocchiResourceTestCase, self).get_test_context()
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
        super(GnocchiResourceTestCase, self).setUp()
        patch = mock.patch(
            "rally_openstack.services.gnocchi.metric.GnocchiService")
        self.addCleanup(patch.stop)
        self.mock_metric = patch.start()

    def test_create_resource(self):
        resource_service = self.mock_metric.return_value
        scenario = resource.CreateResource(self.context)
        scenario.generate_random_name = mock.MagicMock(return_value="name")
        scenario.run(resource_type="foo")
        resource_service.create_resource.assert_called_once_with(
            "name", resource_type="foo")

    def test_create_delete_resource(self):
        resource_service = self.mock_metric.return_value
        scenario = resource.CreateDeleteResource(self.context)
        scenario.generate_random_name = mock.MagicMock(return_value="name")
        scenario.run(resource_type="foo")
        resource_service.create_resource.assert_called_once_with(
            "name", resource_type="foo")
        self.assertEqual(1, resource_service.delete_resource.call_count)
