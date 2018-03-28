# Copyright 2017 Red Hat, Inc. <http://www.redhat.com>
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


from rally.task import validation

from rally_openstack import consts
from rally_openstack import scenario
from rally_openstack.scenarios.gnocchi import utils as gnocchiutils

"""Scenarios for Gnocchi archive policy."""


@validation.add("required_services", services=[consts.Service.GNOCCHI])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="GnocchiArchivePolicy.list_archive_policy")
class ListArchivePolicy(gnocchiutils.GnocchiBase):

    def run(self):
        """List archive policies."""
        self.gnocchi.list_archive_policy()


@validation.add("required_services", services=[consts.Service.GNOCCHI])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(
    context={"admin_cleanup@openstack": ["gnocchi.archive_policy"]},
    name="GnocchiArchivePolicy.create_archive_policy")
class CreateArchivePolicy(gnocchiutils.GnocchiBase):

    def run(self, definition=None, aggregation_methods=None):
        """Create archive policy.

        :param definition: List of definitions
        :param aggregation_methods: List of aggregation methods
        """
        if definition is None:
            definition = [{"granularity": "0:00:01", "timespan": "1:00:00"}]

        name = self.generate_random_name()
        self.admin_gnocchi.create_archive_policy(
            name, definition=definition,
            aggregation_methods=aggregation_methods)


@validation.add("required_services", services=[consts.Service.GNOCCHI])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(
    context={"admin_cleanup@openstack": ["gnocchi.archive_policy"]},
    name="GnocchiArchivePolicy.create_delete_archive_policy")
class CreateDeleteArchivePolicy(gnocchiutils.GnocchiBase):

    def run(self, definition=None, aggregation_methods=None):
        """Create archive policy and then delete it.

        :param definition: List of definitions
        :param aggregation_methods: List of aggregation methods
        """
        if definition is None:
            definition = [{"granularity": "0:00:01", "timespan": "1:00:00"}]

        name = self.generate_random_name()
        self.admin_gnocchi.create_archive_policy(
            name, definition=definition,
            aggregation_methods=aggregation_methods)
        self.admin_gnocchi.delete_archive_policy(name)
