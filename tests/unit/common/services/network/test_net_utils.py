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

from rally_openstack.common.services.network import net_utils
from tests.unit import test


PATH = "rally_openstack.common.services.network.net_utils"


class FunctionsTestCase(test.TestCase):

    def test_generate_cidr(self):
        with mock.patch("%s._IPv4_CIDR_INCR" % PATH, iter(range(1, 4))):
            self.assertEqual((4, "10.2.1.0/24"), net_utils.generate_cidr())
            self.assertEqual((4, "10.2.2.0/24"), net_utils.generate_cidr())
            self.assertEqual((4, "10.2.3.0/24"), net_utils.generate_cidr())

        with mock.patch("%s._IPv4_CIDR_INCR" % PATH, iter(range(1, 4))):
            start_cidr = "1.1.0.0/26"
            self.assertEqual(
                (4, "1.1.0.64/26"),
                net_utils.generate_cidr(start_cidr=start_cidr))
            self.assertEqual(
                (4, "1.1.0.128/26"),
                net_utils.generate_cidr(start_cidr=start_cidr))
            self.assertEqual(
                (4, "1.1.0.192/26"),
                net_utils.generate_cidr(start_cidr=start_cidr))
