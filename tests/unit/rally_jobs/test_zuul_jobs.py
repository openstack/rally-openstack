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

from rally.common import yamlutils as yaml

import rally_openstack
from tests.unit import test


class RallyJobsTestCase(test.TestCase):
    zuul_jobs_path = os.path.join(
        os.path.dirname(rally_openstack.__file__), "..", ".zuul.d")

    def setUp(self):
        super(RallyJobsTestCase, self).setUp()
        with open(os.path.join(self.zuul_jobs_path, "zuul.yaml")) as f:
            self.zuul_cfg = yaml.safe_load(f)

        self.project_cfg = None
        for item in self.zuul_cfg:
            if "project" in item:
                self.project_cfg = item["project"]
                break

    @staticmethod
    def _get_job_name(job):
        if isinstance(job, dict):
            return list(job)[0]
        return job

    def _check_order_of_jobs(self, jobs, pipeline_name, allow_params=False):
        if not allow_params:
            for job in jobs:
                if isinstance(job, dict):
                    self.fail("Setting parameters of jobs for '%s' pipeline "
                              "is permitted. Please fix '%s' job." %
                              (pipeline_name, self._get_job_name(job)))

        specific_jobs = ["rally-dsvm-tox-functional",
                         "rally-docker-check",
                         "rally-task-basic-with-existing-users",
                         "rally-task-simple-job"]
        error_message = (
            "[%s pipeline] We are trying to display jobs in a specific order "
            "to simplify search and reading. Tox jobs should go first in "
            "alphabetic order. Next several specific jobs are expected (%s). "
            "Next - all other jobs in alphabetic order."
            % (pipeline_name, ", ".join(specific_jobs))
        )
        error_message += "\nPlease place '%s' at the position of '%s'."

        jobs_names = [self._get_job_name(job) for job in jobs]

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
        self._check_order_of_jobs(
            self.project_cfg["check"]["jobs"],
            pipeline_name="check",
            allow_params=True
        )

        self._check_order_of_jobs(
            self.project_cfg["gate"]["jobs"],
            pipeline_name="gate",
            allow_params=False
        )
