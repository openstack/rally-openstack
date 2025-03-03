# Copyright 2013: Mirantis Inc.
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

"""
There is a lot of situations when we would like to work with Enum or Const.
E.g. work around Tasks. We would like to use Enum in DB to store status of task
and also in migration that creates DB and in business logic to set some status
so as to avoid copy paste or direct usage of enums values we create singletons
for each enum. (e.g. TaskStatus)
"""

from rally.common import utils


JSON_SCHEMA = "http://json-schema.org/draft-04/schema"


class _EndpointPermission(utils.ImmutableMixin, utils.EnumMixin):
    ADMIN = "admin"
    USER = "user"


class _EndpointType(utils.ImmutableMixin, utils.EnumMixin):
    INTERNAL = "internal"
    ADMIN = "admin"
    PUBLIC = "public"


class _Service(utils.ImmutableMixin, utils.EnumMixin):
    """OpenStack services names, by rally convention."""

    NOVA = "nova"
    NOVA_NET = "nova-network"
    CINDER = "cinder"
    CINDERV2 = "cinderv2"
    CINDERV3 = "cinderv3"
    MANILA = "manila"
    EC2 = "ec2"
    GLANCE = "glance"
    CLOUD = "cloud"
    HEAT = "heat"
    KEYSTONE = "keystone"
    NEUTRON = "neutron"
    DESIGNATE = "designate"
    CEILOMETER = "ceilometer"
    MONASCA = "monasca"
    S3 = "s3"
    SENLIN = "senlin"
    TROVE = "trove"
    SAHARA = "sahara"
    SWIFT = "swift"
    MISTRAL = "mistral"
    MURANO = "murano"
    IRONIC = "ironic"
    GNOCCHI = "gnocchi"
    MAGNUM = "magnum"
    WATCHER = "watcher"
    BARBICAN = "barbican"
    OCTAVIA = "octavia"


class _ServiceType(utils.ImmutableMixin, utils.EnumMixin):
    """OpenStack services types, mapped to service names."""

    BLOCK_STORAGE = "block-storage"
    VOLUME = "volume"
    VOLUMEV2 = "volumev2"
    VOLUMEV3 = "volumev3"
    SHARE = "share"
    EC2 = "ec2"
    IMAGE = "image"
    CLOUD = "cloudformation"
    ORCHESTRATION = "orchestration"
    IDENTITY = "identity"
    CLUSTERING = "clustering"
    COMPUTE = "compute"
    NETWORK = "network"
    DNS = "dns"
    METERING = "metering"
    MONITORING = "monitoring"
    S3 = "s3"
    DATABASE = "database"
    DATA_PROCESSING = "data-processing"
    DATA_PROCESSING_MOS = "data_processing"
    OBJECT_STORE = "object-store"
    WORKFLOW_EXECUTION = "workflowv2"
    APPLICATION_CATALOG = "application-catalog"
    BARE_METAL = "baremetal"
    METRIC = "metric"
    CONTAINER_INFRA = "container-infra"
    INFRA_OPTIM = "infra-optim"
    KEY_MANAGER = "key-manager"
    LOAD_BALANCER = "load-balancer"

    def __init__(self):
        self.__names = {
            self.CLUSTERING: _Service.SENLIN,
            self.COMPUTE: _Service.NOVA,
            # unversioned endpoint of Cinder
            self.BLOCK_STORAGE: _Service.CINDER,
            # legacy versioned endpoints of Cinder
            self.VOLUME: _Service.CINDER,
            self.VOLUMEV2: _Service.CINDER,
            self.VOLUMEV3: _Service.CINDER,
            self.SHARE: _Service.MANILA,
            self.EC2: _Service.EC2,
            self.IMAGE: _Service.GLANCE,
            self.CLOUD: _Service.CLOUD,
            self.ORCHESTRATION: _Service.HEAT,
            self.IDENTITY: _Service.KEYSTONE,
            self.NETWORK: _Service.NEUTRON,
            self.DNS: _Service.DESIGNATE,
            self.METERING: _Service.CEILOMETER,
            self.MONITORING: _Service.MONASCA,
            self.S3: _Service.S3,
            self.DATABASE: _Service.TROVE,
            self.DATA_PROCESSING: _Service.SAHARA,
            self.DATA_PROCESSING_MOS: _Service.SAHARA,
            self.OBJECT_STORE: _Service.SWIFT,
            self.WORKFLOW_EXECUTION: _Service.MISTRAL,
            self.APPLICATION_CATALOG: _Service.MURANO,
            self.BARE_METAL: _Service.IRONIC,
            self.METRIC: _Service.GNOCCHI,
            self.CONTAINER_INFRA: _Service.MAGNUM,
            self.INFRA_OPTIM: _Service.WATCHER,
            self.KEY_MANAGER: _Service.BARBICAN,
            self.LOAD_BALANCER: _Service.OCTAVIA
        }

    def __getitem__(self, service_type):
        """Mapping protocol to service names.

        :param name: str, service name
        :returns: str, service type
        """
        return self.__names[service_type]


EndpointPermission = _EndpointPermission()
ServiceType = _ServiceType()
Service = _Service()
EndpointType = _EndpointType()
