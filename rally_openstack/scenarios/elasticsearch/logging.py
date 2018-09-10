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

import json
import requests

from rally.common import cfg
from rally.common import logging
from rally.common import utils as commonutils
from rally.task import atomic
from rally.task import types
from rally.task import validation

from rally_openstack import consts
from rally_openstack import scenario
from rally_openstack.scenarios.nova import utils as nova_utils

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

"""Scenario for Elasticsearch logging system."""


@types.convert(image={"type": "glance_image"},
               flavor={"type": "nova_flavor"})
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="ElasticsearchLogging.log_instance",
                    platform="openstack")
class ElasticsearchLogInstanceName(nova_utils.NovaScenario):
    """Test logging instance in conjunction with Elasticsearch system.

    Let OpenStack platform already has logging agent (for example, Filebeat),
    which sends nova logs to Elasticsearch through data processing pipeline
    (e.g. Logstash). The test verifies Openstack nova logs stored in logging
    system. It creates nova instance with random name and after instance
    becomes available, checks it's name in Elasticsearch indices by querying.
    """

    @atomic.action_timer("elasticsearch.check_server_log_indexed")
    def _check_server_name(self, server_id, logging_vip, elasticsearch_port,
                           sleep_time, retries_total, additional_query=None):
        request_data = {
            "query": {
                "bool": {
                    "must": [{"match_phrase": {"Payload": server_id}}]
                }
            }
        }
        if additional_query:
            request_data["query"]["bool"].update(additional_query)

        LOG.info("Check server ID %s in elasticsearch" % server_id)
        i = 0
        while i < retries_total:
            LOG.debug("Attempt number %s" % (i + 1))
            resp = requests.get("http://%(ip)s:%(port)s/_search" % {
                "ip": logging_vip, "port": elasticsearch_port},
                data=json.dumps(request_data))
            result = resp.json()
            if result["hits"]["total"] < 1 and i + 1 >= retries_total:
                LOG.debug("No instance data found in Elasticsearch")
                self.assertGreater(result["hits"]["total"], 0)
            elif result["hits"]["total"] < 1:
                i += 1
                commonutils.interruptable_sleep(sleep_time)
            else:
                LOG.debug("Instance data found in Elasticsearch")
                self.assertGreater(result["hits"]["total"], 0)
                break

    def run(self, image, flavor, logging_vip, elasticsearch_port, sleep_time=5,
            retries_total=30, boot_server_kwargs=None, force_delete=False,
            query_by_name=False, additional_query=None):
        """Create nova instance and check it indexed in elasticsearch.

        :param image: image for server
        :param flavor: flavor for server
        :param logging_vip: logging system IP to check server name in
                            elasticsearch index
        :param boot_server_kwargs: special server kwargs for boot
        :param force_delete: force delete server or not
        :param elasticsearch_port: elasticsearch port to use for check server
        :param additional_query: map of additional arguments for scenario
               elasticsearch query to check nova info in els index.
        :param query_by_name: query nova server by name if True otherwise by id
        :param sleep_time: sleep time in seconds between elasticsearch request
        :param retries_total: total number of retries to check server name in
                              elasticsearch
        """
        server = self._boot_server(image, flavor, **(boot_server_kwargs or {}))
        if query_by_name:
            server_id = server.name
        else:
            server_id = server.id
        self._check_server_name(server_id, logging_vip, elasticsearch_port,
                                sleep_time, retries_total,
                                additional_query=additional_query)
        self._delete_server(server, force=force_delete)
