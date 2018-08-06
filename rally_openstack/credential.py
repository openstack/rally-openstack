# Copyright 2017: Mirantis Inc.
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

from rally.common import logging

LOG = logging.getLogger(__file__)


class OpenStackCredential(dict):
    """Credential for OpenStack."""

    def __init__(self, auth_url, username, password, tenant_name=None,
                 project_name=None,
                 permission=None,
                 region_name=None, endpoint_type=None,
                 domain_name=None, endpoint=None, user_domain_name=None,
                 project_domain_name=None,
                 https_insecure=False, https_cacert=None, https_cert=None,
                 profiler_hmac_key=None, profiler_conn_str=None,
                 api_info=None, **kwargs):
        if kwargs:
            raise TypeError("%s" % kwargs)

        # TODO(andreykurilin): deprecate permission and endpoint

        super(OpenStackCredential, self).__init__([
            ("auth_url", auth_url),
            ("username", username),
            ("password", password),
            ("tenant_name", (tenant_name or project_name)),
            ("permission", permission),
            ("endpoint", endpoint),
            ("region_name", region_name),
            ("endpoint_type", endpoint_type),
            ("domain_name", domain_name),
            ("user_domain_name", user_domain_name),
            ("project_domain_name", project_domain_name),
            ("https_insecure", https_insecure),
            ("https_cacert", https_cacert),
            ("https_cert", https_cert),
            ("profiler_hmac_key", profiler_hmac_key),
            ("profiler_conn_str", profiler_conn_str),
            ("api_info", api_info or {})
        ])

        self._clients_cache = {}

    def __getattr__(self, attr, default=None):
        # TODO(andreykurilin): print warning to force everyone to use this
        #   object as raw dict as soon as we clean over code.
        return self.get(attr, default)

    def to_dict(self):
        return dict(self)

    def __deepcopy__(self, memodict=None):
        import copy
        return self.__class__(**copy.deepcopy(self.to_dict()))

    # this method is mostly used by validation step. let's refactor it and
    # deprecated this
    def clients(self, api_info=None):
        from rally_openstack import osclients

        return osclients.Clients(self, api_info=api_info,
                                 cache=self._clients_cache)
