# Copyright 2014: Mirantis Inc.
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

import inspect
import os
import traceback
import typing as t
from unittest import mock

import yaml

from rally import api
from rally.common import logging
from rally.task import context
from rally.task import engine
from rally.task import scenario
from rally.task import task_cfg

import rally_openstack
from tests.unit import test


RALLY_PATH = os.path.dirname(os.path.dirname(rally_openstack.__file__))


class TaskSampleTestCase(test.TestCase):
    samples_path = os.path.join(RALLY_PATH, "samples", "tasks")

    def setUp(self):
        super(TaskSampleTestCase, self).setUp()
        if os.environ.get("TOX_ENV_NAME") == "cover":
            self.skipTest("There is no need to check samples in coverage job.")

        self.rapi = api.API(skip_db_check=True)

    def iterate_samples(self, merge_pairs=True):
        """Iterates all task samples

        :param merge_pairs: Whether or not to return both json and yaml samples
            of one sample.
        """
        for dirname, dirnames, filenames in os.walk(self.samples_path):
            for filename in filenames:
                # NOTE(hughsaunders): Skip non config files
                # (bug https://bugs.launchpad.net/rally/+bug/1314369)
                if filename.endswith("json") or (
                        not merge_pairs and filename.endswith("yaml")):
                    yield os.path.join(dirname, filename)

    def _load_task(
        self,
        source: str,
        *,
        template: str,
        template_dir: str,
        **args
    ) -> t.Any:
        try:
            rendered_task = self.rapi.task.render_template(
                task_template=template, template_dir=template_dir, **args
            )
        except Exception as e:
            self.fail(f"Failed to render task from '{source}': {e}")

        try:
            return yaml.safe_load(rendered_task)
        except Exception:
            self.fail(f"Invalid JSON/YAML task file '{source}'.")

    def _load_and_validate_task(
        self,
        source: str,
        *,
        template: str,
        template_dir: str,
        validate_syntax: bool = True,
        **args
    ) -> task_cfg.TaskConfig:

        raw_config = self._load_task(
            source=source, template=template, template_dir=template_dir, **args
        )

        try:
            task_config_obj = task_cfg.TaskConfig(raw_config)
        except Exception:
            print(traceback.format_exc())
            self.fail(f"Failed to load task file '{source}'.")

        if validate_syntax:
            eng = engine.TaskEngine(task_config_obj,
                                    mock.MagicMock(), mock.Mock())
            try:
                eng.validate(only_syntax=True)
            except Exception:
                self.fail(f"Task file '{source}' failed syntax validation.")

        return task_config_obj

    def test_check_missing_sla_section(self):
        failures = []
        for path in self.iterate_samples():
            if "tasks/scenarios" not in path:
                continue
            with open(path) as task_file:
                task_template = task_file.read()

            task_config_obj = self._load_and_validate_task(
                path,
                template=task_template,
                template_dir=self.samples_path,
                validate_syntax=False
            )

            # the separate test will fail if there is v1 sample
            if task_config_obj.version != "2":
                continue

            for subtask in task_config_obj.subtasks:
                for workload in subtask["workloads"]:
                    if not workload.get("sla", {}):
                        failures.append(path)
        if failures:
            self.fail("One or several workloads from the list of samples below"
                      " doesn't have SLA section: \n  %s" %
                      "\n  ".join(failures))

    def test_schema_is_valid(self):
        orig = engine.LOG.logger.level
        self.addCleanup(lambda: engine.LOG.setLevel(orig))
        engine.LOG.setLevel(logging.WARNING)

        scenarios = set()

        for path in self.iterate_samples():
            with open(path) as task_file:
                task_template = task_file.read()

            task_config_obj = self._load_and_validate_task(
                path, template=task_template, template_dir=self.samples_path
            )
            for subtask in task_config_obj.subtasks:
                for workload in subtask["workloads"]:
                    scenarios.add(workload["name"])

        missing = set(s.get_name() for s in scenario.Scenario.get_all())
        missing -= scenarios
        # check missing scenario is not from plugin
        missing = [s for s in list(missing)
                   if scenario.Scenario.get(s).__module__.startswith("rally")]
        self.assertEqual(missing, [],
                         "These scenarios don't have samples: %s" % missing)

    def test_task_config_pairs(self):

        not_equal = []
        missed = []
        checked = []

        for path in self.iterate_samples(merge_pairs=False):
            if path.endswith(".json"):
                json_path = path
                yaml_path = json_path.replace(".json", ".yaml")
            else:
                yaml_path = path
                json_path = yaml_path.replace(".yaml", ".json")

            if json_path in checked:
                continue
            else:
                checked.append(json_path)

            if not os.path.exists(yaml_path):
                missed.append(yaml_path)
            elif not os.path.exists(json_path):
                missed.append(json_path)
            else:
                with open(json_path) as json_file:
                    json_config = self._load_task(
                        json_path,
                        template=json_file.read(),
                        template_dir=self.samples_path,
                    )
                with open(yaml_path) as yaml_file:
                    yaml_config = self._load_task(
                        json_path,
                        template=yaml_file.read(),
                        template_dir=self.samples_path,
                    )

                if json_config != yaml_config:
                    not_equal.append(f"'{yaml_path}' and '{json_path}'")

        error = ""
        if not_equal:
            error += ("Sample task configs are not equal:\n\t%s\n"
                      % "\n\t".join(not_equal))
        if missed:
            self.fail("Sample task configs are missing:\n\t%s\n"
                      % "\n\t".join(missed))

        if error:
            self.fail(error)

    def test_no_underscores_in_filename(self):
        bad_filenames = []
        for dirname, dirnames, filenames in os.walk(self.samples_path):
            for filename in filenames:
                if "_" in filename and (filename.endswith(".yaml")
                                        or filename.endswith(".json")):
                    full_path = os.path.join(dirname, filename)
                    bad_filenames.append(full_path)

        self.assertEqual([], bad_filenames,
                         "Following sample task filenames contain "
                         "underscores (_) but must use dashes (-) instead: "
                         "{}".format(bad_filenames))

    def test_context_samples_found(self):
        all_plugins = context.Context.get_all()
        context_samples_path = os.path.join(self.samples_path, "contexts")
        for p in all_plugins:
            # except contexts which belongs to tests module
            if not inspect.getfile(p).startswith(
               os.path.dirname(rally_openstack.__file__)):
                continue
            file_name = p.get_name().replace("_", "-")
            file_path = os.path.join(context_samples_path, file_name)
            if not os.path.exists("%s.json" % file_path):
                self.fail(("There is no json sample file of %s,"
                           "plugin location: %s" %
                           (p.get_name(), p.__module__)))

    def test_certification_task(self):
        cert_dir = os.path.join(RALLY_PATH, "tasks/openstack")

        source = os.path.join(cert_dir, "task.yaml")
        with open(source) as f:
            template = f.read()

        with self.subTest("no any args passed task_arguments.yaml"):
            self._load_and_validate_task(
                source, template=template, template_dir=cert_dir
            )

        args_file = "task_arguments.yaml"
        with open(os.path.join(cert_dir, args_file)) as f:
            args = yaml.safe_load(f)

        with self.subTest(f"args from '{args_file}'"):
            self._load_and_validate_task(
                source, template=template, template_dir=cert_dir, **args
            )

        with self.subTest(f"toggled boolean args from '{args_file}'"):
            args = dict(
                (
                    key,
                    not value if isinstance(value, bool) else value
                )
                for key, value in args.items()
            )

            self._load_and_validate_task(
                source, template=template, template_dir=cert_dir, **args
            )
