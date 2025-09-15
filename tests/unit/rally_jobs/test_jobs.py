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

import os
import shutil
import tempfile
import traceback
from unittest import mock

from rally import api
from rally.cli import yamlutils as yaml
from rally.common.plugin import discover
from rally.task import engine
from rally.task import task_cfg

import rally_openstack
from tests.unit import fakes
from tests.unit import test


class RallyJobsTestCase(test.TestCase):
    rally_jobs_path = os.path.join(
        os.path.dirname(rally_openstack.__file__), "..", "rally-jobs")

    def setUp(self):
        super(RallyJobsTestCase, self).setUp()
        self.tmp_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp_dir, ".rally"))
        shutil.copytree(os.path.join(self.rally_jobs_path, "extra"),
                        os.path.join(self.tmp_dir, ".rally", "extra"))

        self.original_home = os.environ["HOME"]
        os.environ["HOME"] = self.tmp_dir

        def return_home():
            os.environ["HOME"] = self.original_home
        self.addCleanup(shutil.rmtree, self.tmp_dir)

        self.addCleanup(return_home)

        self.task_api = api._Task(api.API(skip_db_check=True))

    def _test_schema(self, filename: str, full_path: str) -> None:
        args_file = os.path.join(
            self.rally_jobs_path,
            filename.rsplit(".", 1)[0] + "_args.yaml")

        args = {}
        if os.path.exists(args_file):
            with open(args_file, "r") as f:
                args = yaml.safe_load(f)
            if not isinstance(args, dict):
                raise TypeError(
                    f"args file {args_file} must be dict in yaml or json "
                    "presentation"
                )

        with open(full_path) as f:
            task_raw_cfg = self.task_api.render_template(
                task_template=f.read(), **args
            )
        task = task_cfg.TaskConfig(yaml.safe_load(task_raw_cfg))
        task_obj = fakes.FakeTask({"uuid": full_path})

        eng = engine.TaskEngine(task, task_obj, mock.Mock())
        eng.validate(only_syntax=True)

        if task.version == "1":
            raise ValueError(
                "Task config still uses format v1. It is deprecated."
            )

    def test_schema_is_valid(self):
        discover.load_plugins(os.path.join(self.rally_jobs_path, "plugins"))

        files = {f for f in os.listdir(self.rally_jobs_path)
                 if (os.path.isfile(os.path.join(self.rally_jobs_path, f))
                     and f.endswith(".yaml")
                     and not f.endswith("_args.yaml"))}

        for filename in files:
            full_path = os.path.join(self.rally_jobs_path, filename)
            try:
                self._test_schema(filename, full_path)
            except Exception:
                print(traceback.format_exc())
                self.fail(f"Wrong task input file: {full_path}")
