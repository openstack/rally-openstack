# Copyright 2013 Huawei Technologies Co.,LTD.
# All Rights Reserved.
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

import random

from rally.common import cfg
from rally.common import logging

from rally_openstack import scenario
from rally_openstack.services.storage import block


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class CinderBasic(scenario.OpenStackScenario):
    def __init__(self, context=None, admin_clients=None, clients=None):
        super(CinderBasic, self).__init__(context, admin_clients, clients)
        if hasattr(self, "_admin_clients"):
            self.admin_cinder = block.BlockStorage(
                self._admin_clients, name_generator=self.generate_random_name,
                atomic_inst=self.atomic_actions())
        if hasattr(self, "_clients"):
            self.cinder = block.BlockStorage(
                self._clients, name_generator=self.generate_random_name,
                atomic_inst=self.atomic_actions())

    def get_random_server(self):
        server_id = random.choice(self.context["tenant"]["servers"])
        return self.clients("nova").servers.get(server_id)
