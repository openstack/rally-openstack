# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import requests

from rally.common import logging
from rally.common import utils as commonutils
from rally.task import atomic
from rally.task import service

LOG = logging.getLogger(__name__)


class GrafanaService(service.Service):

    def __init__(self, spec, name_generator=None, atomic_inst=None):
        """Initialization of Grafana service.

        :param spec: param contains monitoring system info: IPs, ports, creds
        """
        super(GrafanaService, self).__init__(None,
                                             name_generator=name_generator,
                                             atomic_inst=atomic_inst)
        self._spec = spec

    @atomic.action_timer("grafana.check_metric")
    def check_metric(self, seed, sleep_time, retries_total):
        """Check metric with seed name in Grafana datasource.

        :param seed: random metric name
        :param sleep_time: sleep time between checking metrics in seconds
        :param retries_total: total number of retries to check metric in
                              Grafana
        :return: True if metric in Grafana datasource and False otherwise
        """
        check_url = ("http://%(vip)s:%(port)s/api/datasources/proxy/:"
                     "%(datasource)s/api/v1/query?query=%(seed)s" % {
                         "vip": self._spec["monitor_vip"],
                         "port": self._spec["grafana"]["port"],
                         "datasource": self._spec["datasource_id"],
                         "seed": seed
                     })
        i = 0
        LOG.info("Check metric %s in Grafana" % seed)
        while i < retries_total:
            LOG.debug("Attempt number %s" % (i + 1))
            resp = requests.get(check_url,
                                auth=(self._spec["grafana"]["user"],
                                      self._spec["grafana"]["password"]))
            result = resp.json()
            LOG.debug("Grafana response code: %s" % resp.status_code)
            if len(result["data"]["result"]) < 1 and i + 1 >= retries_total:
                LOG.debug("No instance metrics found in Grafana")
                return False
            elif len(result["data"]["result"]) < 1:
                i += 1
                commonutils.interruptable_sleep(sleep_time)
            else:
                LOG.debug("Metric instance found in Grafana")
                return True

    @atomic.action_timer("grafana.push_metric")
    def push_metric(self, seed):
        """Push metric by GET request using pushgateway.

        :param seed: random name for metric to push
        """
        push_url = "http://%(ip)s:%(port)s/metrics/job/%(job)s" % {
            "ip": self._spec["monitor_vip"],
            "port": self._spec["pushgateway_port"],
            "job": self._spec["job_name"]
        }
        resp = requests.post(push_url,
                             headers={"Content-type": "text/xml"},
                             data="%s 12345\n" % seed)
        if resp.ok:
            LOG.info("Metric %s pushed" % seed)
        else:
            LOG.error("Error during push metric %s" % seed)
        return resp.ok
