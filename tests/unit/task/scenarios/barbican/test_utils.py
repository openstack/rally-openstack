# Copyright 2018 Red Hat Inc
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

from rally_openstack.task.scenarios.barbican import utils
from tests.unit import test


class BarbicanBaseTestCase(test.ScenarioTestCase):

    def setUp(self):
        super(BarbicanBaseTestCase, self).setUp()
        self.context = super(BarbicanBaseTestCase, self).get_test_context()
        self.context.update({
            "admin": {
                "id": "fake_user_id",
                "credential": mock.MagicMock()
            },
            "user": {
                "id": "fake_user_id",
                "credential": mock.MagicMock()
            },
            "tenant": {"id": "fake_tenant_id",
                       "name": "fake_tenant_name"}
        })
        m = "rally_openstack.common.services.key_manager.barbican"
        patch = mock.patch("%s.BarbicanService" % m)
        self.addCleanup(patch.stop)
        self.mock_service = patch.start()

    def test_barbican_base(self):
        base = utils.BarbicanBase(self.context)
        self.assertEqual(base.admin_barbican,
                         self.mock_service.return_value)
