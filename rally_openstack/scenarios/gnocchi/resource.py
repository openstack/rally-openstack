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

"""Scenarios for Gnocchi resource."""


@validation.add("required_services", services=[consts.Service.GNOCCHI])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["gnocchi.resource"]},
                    name="GnocchiResource.create_resource")
class CreateResource(gnocchiutils.GnocchiBase):

    def run(self, resource_type="generic"):
        """Create resource.

        :param resource_type: Type of the resource
        """
        name = self.generate_random_name()
        self.gnocchi.create_resource(name, resource_type=resource_type)


@validation.add("required_services", services=[consts.Service.GNOCCHI])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["gnocchi.resource"]},
                    name="GnocchiResource.create_delete_resource")
class CreateDeleteResource(gnocchiutils.GnocchiBase):

    def run(self, resource_type="generic"):
        """Create resource and then delete it.

        :param resource_type: Type of the resource
        """
        name = self.generate_random_name()
        resource = self.gnocchi.create_resource(name,
                                                resource_type=resource_type)
        self.gnocchi.delete_resource(resource["id"])
