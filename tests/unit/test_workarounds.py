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

import importlib.metadata

from tests.unit import test


class WorkaroundTestCase(test.TestCase):

    WORKAROUNDS = []

    def get_min_required_version(self):
        from packaging import requirements

        dist = importlib.metadata.distribution("rally-openstack")

        for p in dist.requires or []:
            req = requirements.Requirement(p)
            if req.name != "rally":
                continue
            for spec in req.specifier:
                if spec.operator in (">=", ">"):
                    version = [int(i) for i in spec.version.split(".")]
                    if spec.operator == ">":
                        version[-1] += 1
                    return version

        self.fail("Failed to get a minimum required version of Rally "
                  "framework.")

    def test_rally_version(self):
        rally_version = self.get_min_required_version()

        for version, workarounds in self.WORKAROUNDS:
            if rally_version >= version:
                self.fail(
                    "After bumping minimum required version of Rally, some "
                    "workarounds become redundant. See the following list and "
                    "update the code: \n\t%s" % "\n\t".join(workarounds))
