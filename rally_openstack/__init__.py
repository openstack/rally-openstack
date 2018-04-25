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

from rally.common import version as _rally_version

_version_tuple = _rally_version.version_info.semantic_version().version_tuple()

if _version_tuple < (0, 12):
    # NOTE(andreykurilin): Rally < 0.12 doesn't care about loading options from
    #   external packages, so we need to handle it manually.

    from rally.common import opts as global_opts

    from rally_openstack.cfg import opts

    # ensure that rally options are registered.
    global_opts.register()
    global_opts.register_opts(opts.list_opts().items())
