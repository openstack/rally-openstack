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

from importlib.metadata import version as _version

from rally.common import version as __rally_version__

from rally_openstack import _compat


if hasattr(__rally_version__, "__version_tuple__"):
    __rally_version__ = __rally_version__.__version_tuple__
else:
    __rally_version__ = __rally_version__.version_info.semantic_version()
    __rally_version__ = __rally_version__.version_tuple()

try:
    # Try to get version from installed package metadata
    __version__ = _version("rally-openstack")
except Exception:
    # Fallback to setuptools_scm for development installs
    try:
        from setuptools_scm import get_version  # type: ignore[import-untyped]

        __version__ = get_version()
    except Exception:
        # Final fallback - this should rarely happen
        __version__ = "0.0.0"


__version_tuple__ = tuple(
    int(p) if p.isdigit() else p
    for p in __version__.replace("-", ".").split(".")
)


# WARNING: IF YOU ARE LOOKING FOR SOME PHYSICALLY UNEXISTING MODULES THAT CAN
#   BE IMPORTED (FOR BACKWARD COMPATIBILITY), PLEASE CHECK THE NEXT FUNCTION
# HAPPY DEBUGGING!!
_compat.init()
