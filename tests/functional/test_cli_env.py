# Copyright 2013: Mirantis Inc.
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

import copy
import unittest

from tests.functional import utils


TEST_ENV = {
    "OS_USERNAME": "admin",
    "OS_PASSWORD": "admin",
    "OS_TENANT_NAME": "admin",
    "OS_AUTH_URL": "http://fake/",
}

RALLY_OPTS = {
    # speed up failures
    "DEFAULT": {"openstack_client_http_timeout": 5}
}


class EnvTestCase(unittest.TestCase):
    def test_check_success(self):
        rally = utils.Rally()
        rally("env check")

    def test_check_wrong_url(self):
        rally = utils.Rally(config_opts=RALLY_OPTS)
        fake_spec = copy.deepcopy(rally.env_spec)
        fake_spec["existing@openstack"]["auth_url"] = "http://example.com:5000"
        spec = utils.JsonTempFile(fake_spec)
        rally("env create --name t_create_env --spec %s" % spec.filename)

        try:
            rally("env check")
        except utils.RallyCliError as e:
            output = e.output.split("\n")
            line_template = "| :-(       | openstack | %s |"
            err1 = "Unable to establish connection to http://example.com:5000"
            err2 = "Request to http://example.com:5000 timed out"
            if (line_template % err1 not in output
                    and line_template % err2 not in output):
                self.fail("The output of `env check` doesn't contain expected"
                          " error. Output:\n" % e.output)
        else:
            self.fail("Check env command should fail!")

    def test_check_wrong_username(self):
        rally = utils.Rally(config_opts=RALLY_OPTS)
        fake_spec = copy.deepcopy(rally.env_spec)
        fake_spec["existing@openstack"]["admin"]["username"] = "MASTER777"
        spec = utils.JsonTempFile(fake_spec)
        rally("env create --name t_create_env --spec %s" % spec.filename)

        try:
            rally("env check")
        except utils.RallyCliError as e:
            line = ("| :-(       | openstack | Failed to authenticate to "
                    "%s for user '%s' in project '%s': The request you have "
                    "made requires authentication. |" %
                    (fake_spec["existing@openstack"]["auth_url"],
                     fake_spec["existing@openstack"]["admin"]["username"],
                     fake_spec["existing@openstack"]["admin"]["project_name"]))
            self.assertIn(line, e.output.split("\n"))
        else:
            self.fail("Check env command should fail!")

    def test_check_wrong_password(self):
        rally = utils.Rally(config_opts=RALLY_OPTS)
        fake_spec = copy.deepcopy(rally.env_spec)
        fake_spec["existing@openstack"]["admin"]["password"] = "MASTER777"
        spec = utils.JsonTempFile(fake_spec)
        rally("env create --name t_create_env --spec %s" % spec.filename)

        try:
            rally("env check")
        except utils.RallyCliError as e:
            line = ("| :-(       | openstack | Failed to authenticate to "
                    "%s for user '%s' in project '%s': The request you have "
                    "made requires authentication. |" %
                    (fake_spec["existing@openstack"]["auth_url"],
                     fake_spec["existing@openstack"]["admin"]["username"],
                     fake_spec["existing@openstack"]["admin"]["project_name"]))
            self.assertIn(line, e.output.split("\n"))
        else:
            self.fail("Check env command should fail!")

    def test_create_from_sysenv(self):
        rally = utils.Rally()
        rally.env.update(TEST_ENV)
        rally("env create --name t_create_env --from-sysenv")
        config = rally("env show --only-spec", getjson=True)
        self.assertIn("existing@openstack", config)
        self.assertEqual(TEST_ENV["OS_USERNAME"],
                         config["existing@openstack"]["admin"]["username"])
        self.assertEqual(TEST_ENV["OS_PASSWORD"],
                         config["existing@openstack"]["admin"]["password"])
        if "project_name" in config["existing@openstack"]["admin"]:
            # keystone v3
            self.assertEqual(
                TEST_ENV["OS_TENANT_NAME"],
                config["existing@openstack"]["admin"]["project_name"])
        else:
            # keystone v2
            self.assertEqual(
                TEST_ENV["OS_TENANT_NAME"],
                config["existing@openstack"]["admin"]["tenant_name"])
        self.assertEqual(
            TEST_ENV["OS_AUTH_URL"],
            config["existing@openstack"]["auth_url"])

    def test_check_api_info_success(self):
        rally = utils.Rally()
        spec = copy.deepcopy(rally.env_spec)
        spec["existing@openstack"]["api_info"] = {
            "fakedummy": {
                "version": "2",
                "service_type": "dummyv2"
            }
        }
        spec = utils.JsonTempFile(spec)
        rally("env create --name t_create_env_with_api_info"
              " --spec %s" % spec.filename)
        plugings = "tests/functional/extra/fake_dir/fake_plugin.py"
        rally("--plugin-paths %s env check" % plugings)

    def test_check_api_info_fail_1(self):
        rally = utils.Rally()
        spec = copy.deepcopy(rally.env_spec)
        spec["existing@openstack"]["api_info"] = {
            "fakedummy": {
                "version": "3",
                "service_type": "dummyv2"
            }
        }
        spec = utils.JsonTempFile(spec)
        rally("env create --name t_create_env_with_api_info"
              " --spec %s" % spec.filename)
        try:
            plugings = "tests/functional/extra/fake_dir/fake_plugin.py"
            rally("--plugin-paths %s env check" % plugings)
        except utils.RallyCliError as e:
            self.assertIn("Invalid setting for 'fakedummy':", e.output)

    def test_check_api_info_fail_2(self):
        rally = utils.Rally()
        spec = copy.deepcopy(rally.env_spec)
        spec["existing@openstack"]["api_info"] = {
            "noneclient": {
                "version": "1",
                "service_type": "none"
            }
        }
        spec = utils.JsonTempFile(spec)
        rally("env create --name t_create_env_with_api_info"
              " --spec %s" % spec.filename)
        try:
            plugings = "tests/functional/extra/fake_dir/fake_plugin.py"
            rally("--plugin-paths %s env check" % plugings)
        except utils.RallyCliError as e:
            self.assertIn("There is no OSClient plugin 'noneclient'",
                          e.output)

    def test_check_api_info_fail_3(self):
        rally = utils.Rally()
        spec = copy.deepcopy(rally.env_spec)
        spec["existing@openstack"]["api_info"] = {
            "faileddummy": {
                "version": "2",
                "service_type": "dummy"
            }
        }
        spec = utils.JsonTempFile(spec)
        rally("env create --name t_create_env_with_api_info"
              " --spec %s" % spec.filename)
        try:
            plugings = "tests/functional/extra/fake_dir/fake_plugin.py"
            rally("--plugin-paths %s env check" % plugings)
        except utils.RallyCliError as e:
            self.assertIn("Can not create 'faileddummy' with 2 version",
                          e.output)
