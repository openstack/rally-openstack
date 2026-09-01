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

from tests.ci import osresources
from tests.unit import test


@ddt.ddt
class NeutronTaaSResourcesTestCase(test.TestCase):

    @ddt.data("tap_services", "tap_flows")
    def test_list_resources(self, kind):
        clients = mock.Mock()
        network = clients._conn.network
        network.extensions.return_value = [mock.Mock(alias="taas")]
        resources = [mock.Mock(id="resource-id")]
        getattr(network, kind).return_value = iter(resources)
        manager = osresources.Neutron(clients)

        self.assertEqual(resources, list(getattr(manager, "list_" + kind)()))
        getattr(network, kind).assert_called_once_with()

    @ddt.data("tap_services", "tap_flows")
    def test_list_resources_without_extension(self, kind):
        clients = mock.Mock()
        network = clients._conn.network
        network.extensions.return_value = []
        manager = osresources.Neutron(clients)

        self.assertEqual([], list(getattr(manager, "list_" + kind)()))
        getattr(network, kind).assert_not_called()
