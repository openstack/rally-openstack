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
import re

import yaml

import rally_openstack
from tests.unit import test


class RallyJobsTestCase(test.TestCase):
    root_dir = os.path.dirname(os.path.dirname(rally_openstack.__file__))
    zuul_jobs_path = os.path.join(root_dir, ".zuul.d")

    def setUp(self):
        super(RallyJobsTestCase, self).setUp()
        with open(os.path.join(self.zuul_jobs_path, "zuul.yaml")) as f:
            self.zuul_cfg = yaml.safe_load(f)

        self.project_cfg = None
        for item in self.zuul_cfg:
            if "project" in item:
                self.project_cfg = item["project"]
                break
        if self.project_cfg is None:
            self.fail("Cannot detect project section from zuul config.")

    @staticmethod
    def _parse_job(job):
        if isinstance(job, dict):
            job_name = list(job)[0]
            job_cfg = job[job_name]
            return job_name, job_cfg
        return job, None

    def _check_order_of_jobs(self, pipeline):
        jobs = self.project_cfg[pipeline]["jobs"]

        specific_jobs = ["rally-dsvm-tox-functional",
                         "rally-openstack-docker-build",
                         "rally-task-basic-with-existing-users",
                         "rally-task-simple-job"]
        error_message = (
            f"[{pipeline} pipeline] We are trying to display jobs in a "
            f"specific order to simplify search and reading. Tox jobs should "
            f"go first in alphabetic order. Next several specific jobs are "
            f"expected ({', '.join(specific_jobs)}). "
            f"Next - all other jobs in alphabetic order."
        )
        error_message += "\nPlease place '%s' at the position of '%s'."

        jobs_names = [self._parse_job(job)[0] for job in jobs]

        tox_jobs = sorted(job for job in jobs_names
                          if job.startswith("rally-tox"))
        for i, job in enumerate(tox_jobs):
            if job != jobs[i]:
                self.fail(error_message % (job, jobs[i]))

        for job in specific_jobs:
            if job not in jobs_names:
                continue
            i += 1
            if job != jobs_names[i]:
                self.fail(error_message % (job, jobs_names[i]))

        i += 1
        other_jobs = sorted(jobs_names[i: len(jobs_names)])
        for j, job in enumerate(other_jobs):
            if job != jobs_names[i + j]:
                self.fail(error_message % (job, jobs_names[i + j]))

    def test_order_of_displaying_jobs(self):
        for pipeline in ("check", "gate"):
            self._check_order_of_jobs(pipeline=pipeline)

    JOB_FILES_PARAMS = {"files", "irrelevant-files"}

    def test_job_configs(self):

        file_matchers = {}

        for pipeline in ("check", "gate"):
            for job in self.project_cfg[pipeline]["jobs"]:
                job_name, job_cfg = self._parse_job(job)
                if job_cfg is None:
                    continue

                if pipeline == "gate":
                    params = set(job_cfg) - self.JOB_FILES_PARAMS
                    if params:
                        self.fail(
                            f"Invalid parameter(s) for '{job_name}' job at "
                            f"gate pipeline: {', '.join(params)}.")

                for param in self.JOB_FILES_PARAMS:
                    if param in job_cfg:
                        for file_matcher in job_cfg[param]:
                            file_matchers.setdefault(
                                file_matcher,
                                {
                                    "matcher": re.compile(file_matcher),
                                    "used_by": []
                                }
                            )
                            file_matchers[file_matcher]["used_by"].append(
                                {
                                    "pipeline": pipeline,
                                    "job": job_name,
                                    "param": param
                                }
                            )
        not_matched = set(file_matchers)

        for dir_name, _, files in os.walk(self.root_dir):
            dir_name = os.path.relpath(dir_name, self.root_dir)
            if dir_name in (".tox", ".git"):
                continue
            for f in files:
                full_path = os.path.join(dir_name, f)
                for key in list(not_matched):
                    if file_matchers[key]["matcher"].match(full_path):
                        not_matched.remove(key)
                if not not_matched:
                    # stop iterating files if no more matchers to check
                    break
            if not not_matched:
                # stop iterating files if no more matchers to check
                break

        for key in not_matched:
            user = file_matchers[key]["used_by"][0]
            self.fail(
                f"'{user['job']}' job configuration for "
                f"'{user['pipeline']}' pipeline includes wrong "
                f"matcher '{key}' at '{user['param']}'."
            )
