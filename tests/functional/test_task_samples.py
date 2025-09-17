# Copyright 2014: Mirantis Inc.
# Copyright 2014: Catalyst IT Ltd.
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
import json
import os
import re
import traceback
import unittest

from rally import api
from rally.cli import yamlutils as yaml
from rally.common import broker
from rally.common import logging
from rally import plugins
from rally.task import engine

import rally_openstack as rally_openstack_module
from rally_openstack.common import consts
from rally_openstack.common import credential
from tests.functional import utils


class TestTaskSamples(unittest.TestCase):

    NUMBER_OF_THREADS = 20

    def _skip(self, validation_output):
        """Help to decide do we want to skip this result or not.

        :param validation_output: string representation of the
        error that we want to check
        :return: True if we want to skip this error
        of task sample validation, otherwise False.
        """

        skip_lst = ["[Ss]ervice is not available",
                    "is not installed. To install it run",
                    "extension.* is not configured"]
        for check_str in skip_lst:
            if re.search(check_str, validation_output) is not None:
                return True
        return False

    @plugins.ensure_plugins_are_loaded
    def test_task_samples_are_valid(self):
        from rally_openstack.task.contexts.keystone import users

        orig = engine.LOG.logger.level
        self.addCleanup(lambda: engine.LOG.setLevel(orig))
        engine.LOG.setLevel(logging.WARNING)

        rally = utils.Rally(force_new_db=True)
        # let's use pre-created users to make TestTaskSamples quicker
        rapi = api.API(config_file=rally.config_filename)
        deployment = rapi.deployment._get("MAIN")

        openstack_platform = deployment.env_obj.data["platforms"]["openstack"]
        admin_creds = credential.OpenStackCredential(
            permission=consts.EndpointPermission.ADMIN,
            **openstack_platform["platform_data"]["admin"])

        ctx = {
            "env": {
                "platforms": {
                    "openstack": {
                        "admin": admin_creds.to_dict(),
                        "users": []}}},
            "task": {"uuid": self.__class__.__name__,
                     "deployment_uuid": deployment["uuid"]}}
        user_ctx = users.UserGenerator(ctx)
        user_ctx.setup()
        self.addCleanup(user_ctx.cleanup)

        os_creds = deployment["config"]["openstack"]

        user = copy.copy(os_creds["admin"])
        user["username"] = ctx["users"][0]["credential"].username
        user["password"] = ctx["users"][0]["credential"].password
        if "project_name" in os_creds["admin"]:
            # it is Keystone
            user["project_name"] = ctx["users"][0]["credential"].tenant_name
        else:
            user["tenant_name"] = ctx["users"][0]["credential"].tenant_name
        os_creds["users"] = [user]

        rally("deployment destroy MAIN", write_report=False)
        deployment_cfg = os.path.join(rally.tmp_dir, "new_deployment.json")
        with open(deployment_cfg, "w") as f:
            f.write(json.dumps({"openstack": os_creds}))
        rally("deployment create --name MAIN --filename %s" % deployment_cfg,
              write_report=False)

        # store all failures and print them at once
        failed_samples = {}

        def publisher(queue):
            """List all samples and render task configs"""
            samples_path = os.path.join(
                os.path.dirname(rally_openstack_module.__file__), os.pardir,
                "samples", "tasks")

            for dirname, dirnames, filenames in os.walk(samples_path):
                # NOTE(rvasilets): Skip by suggest of boris-42 because in
                # future we don't what to maintain this dir
                if dirname.find("tempest-do-not-run-against-production") != -1:
                    continue
                for filename in filenames:
                    full_path = os.path.join(dirname, filename)

                    # NOTE(hughsaunders): Skip non config files
                    # (bug https://bugs.launchpad.net/rally/+bug/1314369)
                    if os.path.splitext(filename)[1] != ".json":
                        continue
                    with open(full_path) as task_file:
                        input_task = task_file.read()
                        rendered_task = rapi.task.render_template(
                            task_template=input_task)
                        queue.append((full_path, rendered_task))

        def consumer(_cache, sample):
            """Validate one sample"""
            full_path, rendered_task = sample
            task_config = yaml.safe_load(rendered_task)
            try:
                rapi.task.validate(deployment="MAIN",
                                   config=task_config)
            except Exception as e:
                if not self._skip(str(e)):
                    failed_samples[full_path] = traceback.format_exc()

        broker.run(publisher, consumer, self.NUMBER_OF_THREADS)

        if failed_samples:
            self.fail("Validation failed on the one or several samples. "
                      "See details below:\n%s" %
                      "".join(["\n======\n%s\n\n%s\n" % (k, v)
                               for k, v in failed_samples.items()]))
