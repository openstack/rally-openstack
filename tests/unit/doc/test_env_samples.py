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

import json
import os

from rally.env import platform

import rally_openstack
from tests.unit import test


RALLY_PATH = os.path.dirname(os.path.dirname(rally_openstack.__file__))


class EnvSampleTestCase(test.TestCase):
    samples_path = os.path.join(RALLY_PATH, "samples", "envs")

    def test_env_samples_are_valid(self) -> None:
        samples = sorted(f for f in os.listdir(self.samples_path)
                         if f.endswith(".json"))
        self.assertTrue(samples)

        for filename in samples:
            with self.subTest(sample=filename):
                with open(os.path.join(self.samples_path, filename)) as f:
                    spec = json.load(f)

                for p_name, p_spec in spec.items():
                    if "@" not in p_name:
                        p_name = f"existing@{p_name}"
                    errors = platform.Platform.validate(
                        p_name, {}, spec, p_spec)
                    self.assertEqual([], errors)
