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

import json
import unittest

from tests.functional import utils


class TaskTestCase(unittest.TestCase):

    def test_specify_version_by_deployment(self):
        rally = utils.Rally()
        deployment = json.loads(rally("deployment config"))
        deployment["openstack"]["api_info"] = {
            "fakedummy": {
                "version": "2",
                "service_type": "dummyv2"
            }
        }
        deployment = utils.JsonTempFile(deployment)
        rally("deployment create --name t_create_with_api_info "
              "--filename %s" % deployment.filename)
        self.assertIn("t_create_with_api_info", rally("deployment list"))

        config = {
            "FakeDummy.openstack_api": [
                {
                    "runner": {
                        "type": "constant",
                        "times": 1,
                        "concurrency": 1
                    }
                }
            ]
        }
        config = utils.TaskConfig(config)
        plugins = "tests/functional/extra/fake_dir/fake_plugin.py"
        rally("--plugin-paths %s task start --task %s" % (
            plugins, config.filename))

    def test_specify_version_by_deployment_with_existing_users(self):
        rally = utils.Rally()
        deployment = json.loads(rally("deployment config"))
        deployment["openstack"]["users"] = [deployment["openstack"]["admin"]]
        deployment["openstack"]["api_info"] = {
            "fakedummy": {
                "version": "2",
                "service_type": "dummyv2"
            }
        }
        deployment = utils.JsonTempFile(deployment)
        rally("deployment create --name t_create_with_api_info "
              "--filename %s" % deployment.filename)
        self.assertIn("t_create_with_api_info", rally("deployment list"))
        config = {
            "FakeDummy.openstack_api": [
                {
                    "runner": {
                        "type": "constant",
                        "times": 1,
                        "concurrency": 1
                    }
                }
            ]
        }
        config = utils.TaskConfig(config)
        plugins = "tests/functional/extra/fake_dir/fake_plugin.py"
        rally("--plugin-paths %s task start --task %s" % (
            plugins, config.filename))
