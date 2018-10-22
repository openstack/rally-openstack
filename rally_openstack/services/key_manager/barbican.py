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
    def create_secret(self):
        """Create Secret"""
        secret_name = self.generate_random_name()
        val = self._clients.barbican().secrets.create(name=secret_name,
                                                      payload="rally_data")
        val.store()
        return val

    @atomic.action_timer("barbican.get_secret")
    def get_secret(self, secret_ref):
        """Get the secret.

        :param secret_name: The name of the secret.
        """
        return self._clients.barbican().secrets.get(secret_ref)

    @atomic.action_timer("barbican.delete_secret")
    def delete_secret(self, secret_name):
        """Delete the secret

        :param secret_name: The name of the secret to delete
        """
        return self._clients.barbican().secrets.delete(secret_name)
