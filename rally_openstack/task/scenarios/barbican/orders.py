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

"""Scenarios for Barbican orders."""


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(name="BarbicanOrders.list")
class BarbicanOrdersList(utils.BarbicanBase):
    def run(self):
        """List secrets."""
        self.admin_barbican.orders_list()


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(name="BarbicanOrders.create_key_and_delete")
class BarbicanOrdersCreateKeyAndDelete(utils.BarbicanBase):
    def run(self):
        """Create and delete key orders"""
        keys = self.admin_barbican.create_key()
        self.admin_barbican.orders_delete(keys.order_ref)


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(name="BarbicanOrders.create_certificate_and_delete")
class BarbicanOrdersCreateCertificateAndDelete(utils.BarbicanBase):
    def run(self):
        """Create and delete certificate orders"""
        certificate = self.admin_barbican.create_certificate()
        self.admin_barbican.orders_delete(certificate.order_ref)


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(name="BarbicanOrders.create_asymmetric_and_delete")
class BarbicanOrdersCreateAsymmetricAndDelete(utils.BarbicanBase):
    def run(self):
        """Create and delete asymmetric order."""
        certificate = self.admin_barbican.create_asymmetric()
        self.admin_barbican.orders_delete(certificate.order_ref)
