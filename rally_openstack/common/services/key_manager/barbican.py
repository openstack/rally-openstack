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

from rally.task import atomic
from rally.task import service


class BarbicanService(service.Service):

    @atomic.action_timer("barbican.list_secrets")
    def list_secrets(self):
        """List Secret"""
        return self._clients.barbican().secrets.list()

    @atomic.action_timer("barbican.create_secret")
    def create_secret(self, name=None, payload=None,
                      payload_content_type=None, payload_content_encoding=None,
                      algorithm=None, bit_length=None, secret_type=None,
                      mode=None, expiration=None):
        """Create Secret

        :param name: A friendly name for the secret
        :param payload: The unecrypted secret data
        :param payload_content_type: the format/type of the secret data
        :param payload_content_encoding: the encoding of the secret data
        :param algorithm: the algorithm associated with this secret key
        :param bit_length: The bit length of this secret key
        :param mode: the algorigthm mode used with this secret key
        :param secret_type: The secret type for this secret key
        :param exipration: the expiration time of the secret in ISO8601
           format
        :returns: a new secret object
        """
        name = name or self.generate_random_name()
        val = self._clients.barbican().secrets.create(
            name=name, payload=payload,
            payload_content_type=payload_content_type,
            payload_content_encoding=payload_content_encoding,
            algorithm=algorithm, bit_length=bit_length, mode=mode,
            secret_type=secret_type, expiration=expiration)
        val.store()
        return val

    @atomic.action_timer("barbican.get_secret")
    def get_secret(self, secret_ref):
        """Get the secret.

        :param secret_name: The name of the secret.
        """
        secret = self._clients.barbican().secrets.get(secret_ref)
        # secret is lazy, its properties would be filled with real
        # values while getting some property.
        try:
            secret.status
        except Exception as e:
            from rally import exceptions
            raise exceptions.GetResourceFailure(resource=secret, err=e)
        return secret

    @atomic.action_timer("barbican.delete_secret")
    def delete_secret(self, secret_name):
        """Delete the secret

        :param secret_name: The name of the secret to delete
        """
        return self._clients.barbican().secrets.delete(secret_name)

    @atomic.action_timer("barbican.list_container")
    def list_container(self):
        """List containers"""
        return self._clients.barbican().containers.list()

    @atomic.action_timer("barbican.container_delete")
    def container_delete(self, container_href):
        """Delete the container

        :param container_href: the container reference
        """
        return self._clients.barbican().containers.delete(container_href)

    @atomic.action_timer("barbican.container_create")
    def container_create(self, name=None, secrets=None):
        """Create a generic container

        :param name: the name of the container
        :param secrets: secrets to populate when creating a container
        """
        name = name or self.generate_random_name()
        val = self._clients.barbican().containers.create(
            name=name, secrets=secrets)
        val.store()
        return val

    @atomic.action_timer("barbican.create_rsa_container")
    def create_rsa_container(self, name=None, public_key=None,
                             private_key=None, private_key_passphrase=None):
        """Create a RSA container

        :param name: a friendly name for the container
        :param public_key: Secret object containing a Public Key
        :param private_key: Secret object containing a Private Key
        :param private_key_passphrase: Secret object containing
            a passphrase
        :returns: RSAContainer
        """
        name = name or self.generate_random_name()
        val = self._clients.barbican().containers.create_rsa(
            name=name, public_key=public_key, private_key=private_key,
            private_key_passphrase=private_key_passphrase)
        val.store()
        return val

    @atomic.action_timer("barbican.create_certificate_container")
    def create_certificate_container(self, name=None, certificate=None,
                                     intermediates=None, private_key=None,
                                     private_key_passphrase=None):
        """Create a certificate container

        :param name: A friendly name for the CertificateContainer
        :param certificate: Secret object containing a Certificate
        :param intermediates: Secret object containing
            Intermediate Certs
        :param private_key: Secret object containing a Private Key
        :param private_key_passphrase: Secret object containing a passphrase
        :returns: CertificateContainer
        """
        name = name or self.generate_random_name()
        val = self._clients.barbican().containers.create_certificate(
            name=name, certificate=certificate, intermediates=intermediates,
            private_key=private_key, private_key_passphrase=None)
        val.store()
        return val

    @atomic.action_timer("barbican.orders_list")
    def orders_list(self):
        """list orders"""
        return self._clients.barbican().orders.list()

    @atomic.action_timer("barbican.orders_delete")
    def orders_delete(self, order_ref):
        """Delete the order

        :param order_ref: The order reference
        """
        return self._clients.barbican().orders.delete(order_ref)

    @atomic.action_timer("barbican.orders_get")
    def orders_get(self, order_ref):
        """Get the order

        :param order_ref: The order reference
        """
        return self._clients.barbican().orders.get(order_ref)

    @atomic.action_timer("barbican.create_key")
    def create_key(self, name=None, algorithm="aes", bit_length=256, mode=None,
                   payload_content_type=None, expiration=None):
        """Create a key order object

        :param name: A friendly name for the secret to be created
        :param algorithm: The algorithm associated with this secret key
        :param bit_length: The bit length of this secret key
        :param mode: The algorithm mode used with this secret key
        :param payload_content_type: The format/type of the secret data
        :param expiration: The expiration time of the secret
            in ISO 8601 format
        :returns: KeyOrder
        """
        name = name or self.generate_random_name()
        order = self._clients.barbican().orders.create_key(
            name=name, algorithm=algorithm, bit_length=bit_length,
            mode=mode, payload_content_type=payload_content_type,
            expiration=expiration)
        order.submit()
        return order

    @atomic.action_timer("barbican.create_asymmetric")
    def create_asymmetric(self, name=None, algorithm="aes", bit_length=256,
                          pass_phrase=None, payload_content_type=None,
                          expiration=None):
        """Create an asymmetric order object

        :param name: A friendly name for the container to be created
        :param algorithm: The algorithm associated with this secret key
        :param bit_length: The bit length of this secret key
        :param pass_phrase: Optional passphrase
        :param payload_content_type: The format/type of the secret data
        :param expiration: The expiration time of the secret
            in ISO 8601 format
        :returns: AsymmetricOrder
        """
        name = name or self.generate_random_name()
        order = self._clients.barbican().orders.create_asymmetric(
            name=name, algorithm=algorithm, bit_length=bit_length,
            pass_phrase=pass_phrase, payload_content_type=payload_content_type,
            expiration=expiration)
        order.submit()
        return order

    @atomic.action_timer("barbican.create_certificate")
    def create_certificate(self, name=None, request_type=None, subject_dn=None,
                           source_container_ref=None, ca_id=None, profile=None,
                           request_data=None):
        """Create a certificate order object

        :param name: A friendly name for the container to be created
        :param request_type: The type of the certificate request
        :param subject_dn: A subject for the certificate
        :param source_container_ref: A container with a
            public/private key pair to use as source for stored-key
            requests
        :param ca_id: The identifier of the CA to use
        :param profile: The profile of certificate to use
        :param request_data: The CSR content
        :returns: CertificateOrder
        """
        name = name or self.generate_random_name()
        order = self._clients.barbican().orders.create_certificate(
            name=name, request_type=request_type, subject_dn=subject_dn,
            source_container_ref=source_container_ref, ca_id=ca_id,
            profile=profile, request_data=request_data)
        order.submit()
        return order
