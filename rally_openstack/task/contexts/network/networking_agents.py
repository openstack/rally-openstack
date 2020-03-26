# Copyright 2019 Ericsson Software Technology
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from rally.common import logging
from rally.common import validation

from rally_openstack.common import consts
from rally_openstack.common import osclients
from rally_openstack.task import context

LOG = logging.getLogger(__name__)


@validation.add("required_platform", platform="openstack", admin=True)
@context.configure(name="networking_agents", platform="openstack", order=349)
class NetworkingAgents(context.OpenStackContext):
    """This context supports querying Neutron agents in Rally."""

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "additionalProperties": False,
    }

    def setup(self):
        nc = osclients.Clients(self.context["admin"]["credential"]).neutron()
        agents = nc.list_agents()["agents"]
        # NOTE(bence romsics): If you ever add input parameters to this context
        # beware that here we use the same key in self.context as is used for
        # parameter passing, so we'll overwrite it.
        self.context["networking_agents"] = agents

    def cleanup(self):
        """Neutron agents were not created by Rally, so nothing to do."""
