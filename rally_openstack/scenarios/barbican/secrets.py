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

from rally_openstack import consts
from rally_openstack import scenario
from rally_openstack.services.key_manager import barbican

"""Scenarios for Barbican secrets."""


class BarbicanBase(scenario.OpenStackScenario):
    """Base class for Barbican scenarios with basic atomic actions."""

    def __init__(self, context=None, admin_context=None, clients=None):
        super(BarbicanBase, self).__init__(context, admin_context, clients)
        if hasattr(self, "_admin_clients"):
            self.admin_barbican = barbican.BarbicanService(
                self._admin_clients, name_generator=self.generate_random_name,
                atomic_inst=self.atomic_actions())


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(name="BarbicanSecrets.list")
class BarbicanSecretsList(BarbicanBase):
    def run(self):
        """List secrets."""
        self.admin_barbican.list_secrets()


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["barbican"]},
                    name="BarbicanSecrets.create")
class BarbicanSecretsCreate(BarbicanBase):
    def run(self):
        """Create secret."""
        self.admin_barbican.create_secret()


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["barbican"]},
                    name="BarbicanSecrets.create_and_delete")
class BarbicanSecretsCreateAndDelete(BarbicanBase):
    def run(self):
        """Create and Delete secret."""
        secret = self.admin_barbican.create_secret()
        self.admin_barbican.delete_secret(secret.secret_ref)


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["barbican"]},
                    name="BarbicanSecrets.create_and_get")
class BarbicanSecretsCreateAndGet(BarbicanBase):
    def run(self):
        """Create and Get Secret.

        """
        secret = self.admin_barbican.create_secret()
        self.assertTrue(secret)
        secret_info = self.admin_barbican.get_secret(secret.secret_ref)
        self.assertEqual(secret.secret_ref, secret_info.secret_ref)


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["barbican"]},
                    name="BarbicanSecrets.get")
class BarbicanSecretsGet(BarbicanBase):
    def run(self, secret_ref=None):
        """Create and Get Secret.

        :param secret_ref: Name of the secret to get
        """
        if secret_ref is None:
            secret = self.admin_barbican.create_secret()
            self.admin_barbican.get_secret(secret.secret_ref)
        else:
            self.admin_barbican.get_secret(secret_ref)


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["barbican"]},
                    name="BarbicanSecrets.create_and_list")
class BarbicanSecretsCreateAndList(BarbicanBase):
    def run(self):
        """Create and then list all secrets."""
        self.admin_barbican.create_secret()
        self.admin_barbican.list_secrets()
