# Copyright 2017: GoDaddy Inc.
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

from rally.common import cfg


OPTS = {
    "DEFAULT": [
        cfg.FloatOpt(
            "openstack_client_http_timeout",
            default=180.0,
            help="HTTP timeout for any of OpenStack service in seconds"),
        cfg.IntOpt(
            "openstack_client_token_refresh_margin",
            default=600,
            help="When a token reused across scenario iterations is within "
                 "this many seconds of expiry, it is refreshed once at "
                 "iteration init (before any atomic action) so the refresh "
                 "never pollutes a measured action's duration. Should be "
                 "generously larger than keystoneauth's own ~120s floor.")
    ]
}
