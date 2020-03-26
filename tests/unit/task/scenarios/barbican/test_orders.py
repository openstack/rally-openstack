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

from rally_openstack.task.scenarios.barbican import orders
from tests.unit import test


class BarbicanOrdersTestCase(test.ScenarioTestCase):

    def get_test_context(self):
        context = super(BarbicanOrdersTestCase, self).get_test_context()
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
        super(BarbicanOrdersTestCase, self).setUp()
        m = "rally_openstack.common.services.key_manager.barbican"
        patch = mock.patch("%s.BarbicanService" % m)
        self.addCleanup(patch.stop)
        self.mock_secrets = patch.start()

    def test_list_orders(self):
        barbican_service = self.mock_secrets.return_value
        scenario = orders.BarbicanOrdersList(self.context)
        scenario.run()
        barbican_service.orders_list.assert_called_once_with()

    def test_key_create_and_delete(self):
        keys = {"order_ref": "fake-key"}
        barbican_service = self.mock_secrets.return_value
        scenario = orders.BarbicanOrdersCreateKeyAndDelete(self.context)
        scenario.run()
        keys = barbican_service.create_key.return_value
        barbican_service.create_key.assert_called_once_with()
        barbican_service.orders_delete.assert_called_once_with(
            keys.order_ref)

    def test_certificate_create_and_delete(self):
        certificate = {"order_ref": "fake-certificate"}
        barbican_service = self.mock_secrets.return_value
        scenario = orders.BarbicanOrdersCreateCertificateAndDelete(
            self.context)
        scenario.run()
        certificate = barbican_service.create_certificate.return_value
        barbican_service.create_certificate.assert_called_once_with()
        barbican_service.orders_delete.assert_called_once_with(
            certificate.order_ref)

    def test_asymmetric_create_and_delete(self):
        certificate = {"order_ref": "fake-certificate"}
        barbican_service = self.mock_secrets.return_value
        scenario = orders.BarbicanOrdersCreateAsymmetricAndDelete(
            self.context)
        scenario.run()
        certificate = barbican_service.create_asymmetric.return_value
        barbican_service.create_asymmetric.assert_called_once_with()
        barbican_service.orders_delete.assert_called_once_with(
            certificate.order_ref)
