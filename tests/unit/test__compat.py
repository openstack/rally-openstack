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

import warnings

from tests.unit import test


class CompatibilityTestCase(test.TestCase):
    def test_old_imports_work(self):

        with warnings.catch_warnings(record=True) as ctx:
            warnings.simplefilter("always")

            from rally_openstack import osclients

            if not ctx:
                self.fail("`rally_openstack._compat` should raise a warning.")
            self.assertEqual(1, len(ctx))
            catched_warning = ctx[0]
            self.assertEqual(
                "Module rally_openstack.osclients is deprecated since "
                "rally-openstack 2.0.0. Use rally_openstack.common.osclients "
                "instead.",
                # catched_warning.message is an instance of an exception
                str(catched_warning.message))

        from rally_openstack.common import osclients as right_osclients

        expected = set(o for o in dir(right_osclients)
                       if not o.startswith("_"))
        actual = set(o for o in dir(osclients) if not o.startswith("_"))
        self.assertEqual(expected, actual)
        self.assertEqual(right_osclients.Clients, osclients.Clients)
