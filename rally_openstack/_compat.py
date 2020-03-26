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

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import warnings


class _MoveSpec(object):
    def __init__(self, deprecated, new, release):
        """init moved module info

        :param deprecated: a module name that is deprecated
        :param new: a module name that should be used instead
        :param release: A release when the module was deprecated
        """
        self.deprecated = deprecated
        self.new = new
        self.deprecated_path = self.deprecated.replace(".", "/")
        self.new_path = self.new.replace(".", "/")
        self.release = release

    def get_new_name(self, fullname):
        """Get the new name for deprecated module."""
        return fullname.replace(self.deprecated, self.new)

    def get_deprecated_path(self, path):
        """Get a path to the deprecated module."""
        return path.replace(self.new_path, self.deprecated_path)


_MOVES = [
    _MoveSpec(
        deprecated="rally_openstack.embedcharts",
        new="rally_openstack.task.ui.charts",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.cleanup",
        new="rally_openstack.task.cleanup",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.contexts",
        new="rally_openstack.task.contexts",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.hook",
        new="rally_openstack.task.hooks",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.scenario",
        new="rally_openstack.task.scenario",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.scenarios",
        new="rally_openstack.task.scenarios",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.types",
        new="rally_openstack.task.types",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.platforms",
        new="rally_openstack.environment.platforms",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.service",
        new="rally_openstack.common.service",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.services",
        new="rally_openstack.common.services",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.validators",
        new="rally_openstack.common.validators",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.wrappers",
        new="rally_openstack.common.wrappers",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.credential",
        new="rally_openstack.common.credential",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.osclients",
        new="rally_openstack.common.osclients",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.consts",
        new="rally_openstack.common.consts",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.exceptions",
        new="rally_openstack.common.exceptions",
        release="2.0.0"
    ),
    _MoveSpec(
        deprecated="rally_openstack.cfg",
        new="rally_openstack.common.cfg",
        release="2.0.0"
    ),
]


class ModuleLoader(object):

    def __init__(self, move_spec):
        self.move_spec = move_spec

    def create_module(self, spec):
        # Python interpreter will use the default module creator in case of
        #   None return value.
        return None

    def exec_module(self, module):
        """Module executor."""
        full_name = self.move_spec.get_new_name(module.__name__)

        original_module = importlib.import_module(full_name)

        if original_module.__file__.endswith("__init__.py"):
            # NOTE(andreykurilin): In case we need to list submodules the
            #   next code can be used:
            #
            #       import pkgutil
            #
            #       for m in pkgutil.iter_modules(original_module.__path__):
            #           module.__dict__[m.name] = importlib.import_module(
            #               f"{full_name}.{m.name}")

            module.__path__ = [
                self.move_spec.get_deprecated_path(original_module.__path__[0])
            ]
        for item in dir(original_module):
            if item.startswith("_"):
                continue
            module.__dict__[item] = original_module.__dict__[item]
        module.__file__ = self.move_spec.get_deprecated_path(
            original_module.__file__)

        return module


class ModulesMovementsHandler(importlib.abc.MetaPathFinder):

    @classmethod
    def _process_spec(cls, fullname, spec):
        """Make module spec and print warning message if needed."""
        if spec.deprecated == fullname:
            warnings.warn(
                f"Module {fullname} is deprecated since rally-openstack "
                f"{spec.release}. Use {spec.get_new_name(fullname)} instead.",
                stacklevel=3
            )

        return importlib.machinery.ModuleSpec(fullname, ModuleLoader(spec))

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        """This functions is what gets executed by the loader."""
        for spec in _MOVES:
            if spec.deprecated in fullname:
                return cls._process_spec(fullname, spec)


def init():
    """Adds our custom module loader."""

    sys.meta_path.append(ModulesMovementsHandler())
