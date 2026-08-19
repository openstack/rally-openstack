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
    rally_jobs_dir = "rally-jobs"
    rally_jobs_path = os.path.join(
        os.path.dirname(rally_openstack.__file__), "..", rally_jobs_dir)

    def setUp(self):
        super().setUp()
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

    def _list_job_files(self) -> list[str]:
        return sorted(
            f for f in os.listdir(self.rally_jobs_path)
            if (os.path.isfile(os.path.join(self.rally_jobs_path, f))
                and f.endswith(".yaml")
                and not f.endswith("_args.yaml"))
        )

    def _load_task_cfg(self, full_path: str) -> task_cfg.TaskConfig:
        args_file = os.path.splitext(full_path)[0] + "_args.yaml"

        args = {}
        if os.path.exists(args_file):
            with open(args_file) as f:
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
        return task_cfg.TaskConfig(yaml.safe_load(task_raw_cfg))

    def _test_schema(self, full_path: str) -> None:
        task = self._load_task_cfg(full_path)
        task_obj = fakes.FakeTask({"uuid": full_path})

        eng = engine.TaskEngine(task, task_obj, mock.Mock())
        eng.validate(only_syntax=True)

        if task.version == "1":
            raise ValueError(
                "Task config still uses format v1. It is deprecated."
            )

    def test_schema_is_valid(self):
        discover.load_plugins(os.path.join(self.rally_jobs_path, "plugins"))

        for filename in self._list_job_files():
            with self.subTest(f"{self.rally_jobs_dir}/{filename}"):
                full_path = os.path.join(self.rally_jobs_path, filename)
                try:
                    self._test_schema(full_path)
                except Exception:
                    self.fail(
                        f"Wrong task input file:\n{traceback.format_exc()}"
                    )

    # These job files are not benchmarks of the target cloud, they exist to
    #   prove that our plugins work against it. So an SLA does not have to
    #   demand a perfect run, it only has to demand that the workload works
    #   at all, which means at least one successful iteration.
    #
    FULL_FAILURE_ALLOWED: dict[str, set[tuple[int, int, str]]] = {
        # both workloads fail due to misconfiguration of import_type
        #   and location
        "glance.yaml": {
            (10, 1, "GlanceImages.import_and_delete_image"),
            (10, 2, "GlanceImages.import_and_delete_image"),
        },
    }

    @staticmethod
    def _format_workloads(workloads: list[tuple[int, int, str]]) -> str:
        return "\n".join(
            f"  subtask #{i} - workload #{j} - {name}"
            for i, j, name in workloads
        )

    def _test_sla(self, filename: str) -> None:
        full_path = os.path.join(self.rally_jobs_path, filename)
        task = self._load_task_cfg(full_path)

        ignorant = []
        for i, subtask in enumerate(task.subtasks, start=1):
            for j, workload in enumerate(subtask["workloads"], start=1):
                failure_rate_sla = workload["sla"].get("failure_rate", {})
                if failure_rate_sla.get("max", 100) == 100:
                    ignorant.append((i, j, workload["name"]))

        allowed = self.FULL_FAILURE_ALLOWED.get(filename, set())
        unexpected = [w for w in ignorant if w not in allowed]
        stale = sorted(allowed - set(ignorant))

        messages = []
        if unexpected:
            messages.append(
                f"{len(unexpected)} workload(s) pass even if every iteration "
                f"fails. Set 'failure_rate.max' below 100:\n"
                f"{self._format_workloads(unexpected)}"
            )
        if stale:
            messages.append(
                f"FULL_FAILURE_ALLOWED lists workloads that already require a "
                f"successful iteration, remove them:\n"
                f"{self._format_workloads(stale)}"
            )
        if messages:
            self.fail("\n".join(messages))

    def test_sla_requires_success(self):
        for filename in self._list_job_files():
            with self.subTest(f"{self.rally_jobs_dir}/{filename}"):
                self._test_sla(filename)

