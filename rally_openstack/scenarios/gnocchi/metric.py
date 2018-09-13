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

"""Scenarios for Gnocchi metric."""


@validation.add("required_services", services=[consts.Service.GNOCCHI])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="GnocchiMetric.list_metric")
class ListMetric(gnocchiutils.GnocchiBase):

    def run(self, limit=None):
        """List metrics.

        :param limit: Maximum number of metrics to list
        """
        self.gnocchi.list_metric(limit=limit)


@validation.add("required_services", services=[consts.Service.GNOCCHI])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["gnocchi.metric"]},
                    name="GnocchiMetric.create_metric")
class CreateMetric(gnocchiutils.GnocchiBase):

    def run(self, archive_policy_name="low", resource_id=None, unit=None):
        """Create metric.

        :param archive_policy_name: Archive policy name
        :param resource_id: The resource ID to attach the metric to
        :param unit: The unit of the metric
        """
        name = self.generate_random_name()
        self.gnocchi.create_metric(name,
                                   archive_policy_name=archive_policy_name,
                                   resource_id=resource_id, unit=unit)


@validation.add("required_services", services=[consts.Service.GNOCCHI])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["gnocchi.metric"]},
                    name="GnocchiMetric.create_delete_metric")
class CreateDeleteMetric(gnocchiutils.GnocchiBase):

    def run(self, archive_policy_name="low", resource_id=None, unit=None):
        """Create metric and then delete it.

        :param archive_policy_name: Archive policy name
        :param resource_id: The resource ID to attach the metric to
        :param unit: The unit of the metric
        """
        name = self.generate_random_name()
        metric = self.gnocchi.create_metric(
            name, archive_policy_name=archive_policy_name,
            resource_id=resource_id, unit=unit)
        self.gnocchi.delete_metric(metric["id"])
