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

import base64
import datetime as dt
import os

from rally.task import validation
from rally.utils import encodeutils

from rally_openstack.common import consts
from rally_openstack.task import scenario
from rally_openstack.task.scenarios.barbican import utils

"""Scenarios for Barbican secrets."""


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(name="BarbicanSecrets.list")
class BarbicanSecretsList(utils.BarbicanBase):
    def run(self):
        """List secrets."""
        self.admin_barbican.list_secrets()


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["barbican"]},
                    name="BarbicanSecrets.create")
class BarbicanSecretsCreate(utils.BarbicanBase):
    def run(self):
        """Create secret."""
        self.admin_barbican.create_secret()


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["barbican"]},
                    name="BarbicanSecrets.create_and_delete")
class BarbicanSecretsCreateAndDelete(utils.BarbicanBase):
    def run(self):
        """Create and Delete secret."""
        secret = self.admin_barbican.create_secret()
        self.admin_barbican.delete_secret(secret.secret_ref)


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["barbican"]},
                    name="BarbicanSecrets.create_and_get")
class BarbicanSecretsCreateAndGet(utils.BarbicanBase):
    def run(self):
        """Create and Get Secret."""
        secret = self.admin_barbican.create_secret()
        self.assertTrue(secret)
        secret_info = self.admin_barbican.get_secret(secret.secret_ref)
        self.assertEqual(secret.secret_ref, secret_info.secret_ref)


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["barbican"]},
                    name="BarbicanSecrets.get")
class BarbicanSecretsGet(utils.BarbicanBase):
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
class BarbicanSecretsCreateAndList(utils.BarbicanBase):
    def run(self):
        """Create and then list all secrets."""
        self.admin_barbican.create_secret()
        self.admin_barbican.list_secrets()


@validation.add("required_services", services=[consts.Service.BARBICAN])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["barbican"]},
                    name="BarbicanSecrets.create_symmetric_and_delete")
class BarbicanSecretsCreateSymmetricAndDelete(utils.BarbicanBase):
    def run(self, payload, algorithm, bit_length, mode):
        """Create and delete symmetric secret

        :param payload: The unecrypted data
        :param algorithm: the algorithm associated with the secret key
        :param bit_length: the big length of the secret key
        :param mode: the algorithm mode used with the secret key
        """
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        payload = encodeutils.safe_encode(payload)
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt,
            iterations=1000, backend=default_backend())
        payload = base64.b64encode(kdf.derive(payload))
        payload = encodeutils.safe_decode(payload)
        expire_time = (dt.datetime.utcnow() + dt.timedelta(days=5))
        secret = self.admin_barbican.create_secret(
            expiration=expire_time.isoformat(), algorithm=algorithm,
            bit_length=bit_length, mode=mode, payload=payload,
            payload_content_type="application/octet-stream",
            payload_content_encoding="base64")
        self.admin_barbican.delete_secret(secret.secret_ref)
