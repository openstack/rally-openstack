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

"""
rally-openstack package should not be aligned to one constant version of Rally
framework. It means that some workarounds for compatibility stuff are
provided.
This module should contain historical notes and checks to do not forget remove
these workaround.
"""

import pkg_resources

from tests.unit import test


class WorkaroundTestCase(test.TestCase):
    WORKAROUNDS = [
        ([0, 12], [
            "'rally_openstack.__init__' module contains a hack for loading "
            "configuration options.",

            "'rally_openstack.types' module contains a compatibility layer for"
            " an old interface of ResourceTypes."]
         ),
        ([0, 13], [
            "'rally_openstack.validators' module has a check to do not "
            "register 'required_platforms@openstack' validator for old Rally "
            "releases."
        ]),
        ([1, 2], [
            "'existing@openstack' platform puts 'traceback' in check method "
            "in case of native keystone errors. It is redundant. "
            "See https://review.openstack.org/597197"
        ])
    ]

    def get_min_required_version(self):
        package = pkg_resources.get_distribution("rally-openstack")
        requirement = [p for p in package.requires() if p.name == "rally"][0]

        for statement, version in requirement.specs:
            version = [int(i) for i in version.split(".")]
            if statement == ">=":
                return version
            elif statement == ">":
                version[-1] += 1
                return version
        self.skip("Failed to get a minimum required version of Rally "
                  "framework.")

    def test_rally_version(self):
        rally_version = self.get_min_required_version()

        for version, workarounds in self.WORKAROUNDS:
            if rally_version >= version:
                self.fail(
                    "After bumping minimum required version of Rally, some "
                    "workarounds become redundant. See the following list and "
                    "update the code: \n\t%s" % "\n\t".join(workarounds))
