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

from openstack.network.v2 import quota as sdk_quota

from rally_openstack.task.contexts.quotas import neutron_quotas
from tests.unit import test


class NeutronQuotasTestCase(test.TestCase):
    def setUp(self):
        super().setUp()
        self.quotas = {
            "network": 20,
            "subnet": 20,
            "port": 100,
            "router": 20,
            "floatingip": 100,
            "security_group": 100,
            "security_group_rule": 100,
            "firewall_policy": 100,
            "firewall_group": 100,
            "firewall_rule": 100,
        }

    def test_update(self):
        clients = mock.MagicMock()
        neutron_quo = neutron_quotas.NeutronQuotas(clients)
        tenant_id = mock.MagicMock()
        neutron_quo.update(tenant_id, **self.quotas)
        clients._conn.network.update_quota.assert_called_once_with(
            tenant_id, **self.quotas)

    def test_delete(self):
        clients = mock.MagicMock()
        neutron_quo = neutron_quotas.NeutronQuotas(clients)
        tenant_id = mock.MagicMock()
        neutron_quo.delete(tenant_id)
        clients._conn.network.delete_quota.assert_called_once_with(tenant_id)

    def test_get(self):
        tenant_id = "tenant_id"
        clients = mock.MagicMock()
        # The sdk Quota resource also carries tenant_id/id, which get() must
        # strip so the result can be fed back into update().
        quota_obj = sdk_quota.Quota(tenant_id=tenant_id, **self.quotas)
        clients._conn.network.get_quota.return_value = quota_obj
        neutron_quo = neutron_quotas.NeutronQuotas(clients)

        self.assertEqual(self.quotas, neutron_quo.get(tenant_id))
        clients._conn.network.get_quota.assert_called_once_with(tenant_id)
