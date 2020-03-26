# Copyright 2018 Red Hat, Inc. <http://www.redhat.com>
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

from rally_openstack.common import consts
from rally_openstack.task import scenario
from rally_openstack.task.scenarios.barbican import utils

"""Scenarios for Barbican containers."""


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(name="BarbicanContainers.list")
class BarbicanContainersList(utils.BarbicanBase):
    def run(self):
        """List secrets."""
        self.admin_barbican.list_container()


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(name="BarbicanContainers.create_and_delete")
class BarbicanContainersGenericCreateAndDelete(utils.BarbicanBase):
    def run(self):
        """Create and delete generic container."""
        container = self.admin_barbican.container_create()
        self.admin_barbican.container_delete(container.container_ref)


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(name="BarbicanContainers.create_and_add")
class BarbicanContainersGenericCreateAndAddSecret(utils.BarbicanBase):
    def run(self):
        """Create secret, create generic container, and delete container."""
        secret = self.admin_barbican.create_secret()
        secret = {"secret": secret}
        container = self.admin_barbican.container_create(secrets=secret)
        self.admin_barbican.container_delete(container.container_ref)


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(name="BarbicanContainers.create_certificate_and_delete")
class BarbicanContainersCertificateCreateAndDelete(utils.BarbicanBase):
    def run(self):
        """Create and delete certificate container."""
        container = self.admin_barbican.create_certificate_container()
        self.admin_barbican.container_delete(container.container_ref)


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(name="BarbicanContainers.create_rsa_and_delete")
class BarbicanContainersRSACreateAndDelete(utils.BarbicanBase):
    def run(self):
        """Create and delete certificate container."""
        container = self.admin_barbican.create_rsa_container()
        self.admin_barbican.container_delete(container.container_ref)
