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

from rally_openstack.scenarios.gnocchi import metric
from tests.unit import test


class GnocchiMetricTestCase(test.ScenarioTestCase):

    def get_test_context(self):
        context = super(GnocchiMetricTestCase, self).get_test_context()
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
        super(GnocchiMetricTestCase, self).setUp()
        patch = mock.patch(
            "rally_openstack.services.gnocchi.metric.GnocchiService")
        self.addCleanup(patch.stop)
        self.mock_metric = patch.start()

    def test_list_metric(self):
        metric_service = self.mock_metric.return_value
        scenario = metric.ListMetric(self.context)
        scenario.run(limit=42)
        metric_service.list_metric.assert_called_once_with(limit=42)

    def test_create_metric(self):
        metric_service = self.mock_metric.return_value
        scenario = metric.CreateMetric(self.context)
        scenario.generate_random_name = mock.MagicMock(return_value="name")
        scenario.run(archive_policy_name="foo", resource_id="123", unit="u")
        metric_service.create_metric.assert_called_once_with(
            "name", archive_policy_name="foo", resource_id="123", unit="u")

    def test_create_delete_metric(self):
        metric_service = self.mock_metric.return_value
        scenario = metric.CreateDeleteMetric(self.context)
        scenario.generate_random_name = mock.MagicMock(return_value="name")
        scenario.run(archive_policy_name="bar", resource_id="123", unit="v")
        metric_service.create_metric.assert_called_once_with(
            "name", archive_policy_name="bar", resource_id="123", unit="v")
        self.assertEqual(1, metric_service.delete_metric.call_count)
