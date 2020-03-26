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

from rally_openstack.common.cfg import cinder
from rally_openstack.common.cfg import glance
from rally_openstack.common.cfg import heat
from rally_openstack.common.cfg import ironic
from rally_openstack.common.cfg import magnum
from rally_openstack.common.cfg import manila
from rally_openstack.common.cfg import mistral
from rally_openstack.common.cfg import monasca
from rally_openstack.common.cfg import murano
from rally_openstack.common.cfg import neutron
from rally_openstack.common.cfg import nova
from rally_openstack.common.cfg import octavia
from rally_openstack.common.cfg import osclients
from rally_openstack.common.cfg import profiler
from rally_openstack.common.cfg import sahara
from rally_openstack.common.cfg import senlin
from rally_openstack.common.cfg import vm
from rally_openstack.common.cfg import watcher

from rally_openstack.common.cfg import tempest

from rally_openstack.common.cfg import keystone_roles
from rally_openstack.common.cfg import keystone_users

from rally_openstack.common.cfg import cleanup

from rally_openstack.task.ui.charts import osprofilerchart


def list_opts():

    opts = {}
    for l_opts in (cinder.OPTS, heat.OPTS, ironic.OPTS, magnum.OPTS,
                   manila.OPTS, mistral.OPTS, monasca.OPTS, murano.OPTS,
                   nova.OPTS, osclients.OPTS, profiler.OPTS, sahara.OPTS,
                   vm.OPTS, glance.OPTS, watcher.OPTS, tempest.OPTS,
                   keystone_roles.OPTS, keystone_users.OPTS, cleanup.OPTS,
                   senlin.OPTS, neutron.OPTS, octavia.OPTS,
                   osprofilerchart.OPTS):
        for category, opt in l_opts.items():
            opts.setdefault(category, [])
            opts[category].extend(opt)
    return [(k, v) for k, v in opts.items()]
