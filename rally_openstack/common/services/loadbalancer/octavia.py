# Copyright 2018 Red Hat, Inc.
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

from rally.common import cfg
from rally.common import logging
from rally import exceptions
from rally.task import atomic
from rally.task import service
from rally.task import utils

CONF = cfg.CONF

LOG = logging.getLogger(__name__)


class Octavia(service.Service):

    @atomic.action_timer("octavia.load_balancer_list")
    def load_balancer_list(self):
        """List all load balancers

        :return:
            List of load balancers
        """
        return self._clients.octavia().load_balancer_list()

    @atomic.action_timer("octavia.load_balancer_show")
    def load_balancer_show(self, lb_id):
        """Show a load balancer

        :param string lb:
            dict of the load balancer to show
        :return:
            A dict of the specified load balancer's settings
        """
        try:
            new_lb = self._clients.octavia().load_balancer_show(lb_id)
        except Exception as e:
            if getattr(e, "code", 400) == 404:
                raise exceptions.GetResourceNotFound(resource=lb_id)
            raise exceptions.GetResourceFailure(resource=lb_id, err=e)
        return new_lb

    @atomic.action_timer("octavia.load_balancer_create")
    def load_balancer_create(self, subnet_id, description=None,
                             admin_state=None, project_id=None,
                             listeners=None, flavor_id=None,
                             provider=None, vip_qos_policy_id=None):
        """Create a load balancer

        :return:
            A dict of the created load balancer's settings
        """
        args = {
            "name": self.generate_random_name(),
            "description": description,
            "listeners": listeners,
            "provider": provider,
            "admin_state_up": admin_state or True,
            "project_id": project_id,
            "vip_subnet_id": subnet_id,
            "vip_qos_policy_id": vip_qos_policy_id,
        }
        lb = self._clients.octavia().load_balancer_create(
            json={"loadbalancer": args})
        return lb["loadbalancer"]

    @atomic.action_timer("octavia.load_balancer_delete")
    def load_balancer_delete(self, lb_id, cascade=False):
        """Delete a load balancer

        :param string lb:
            The dict of the load balancer to delete
        :return:
            Response Code from the API
        """
        return self._clients.octavia().load_balancer_delete(
            lb_id, cascade=cascade)

    @atomic.action_timer("octavia.load_balancer_set")
    def load_balancer_set(self, lb_id, lb_update_args):
        """Update a load balancer's settings

        :param string lb_id:
            The dict of the load balancer to update
        :param lb_update_args:
            A dict of arguments to update a loadbalancer
        :return:
            Response Code from API
        """
        return self._clients.octavia().load_balancer_set(
            lb_id, json={"loadbalancer": lb_update_args})

    @atomic.action_timer("octavia.load_balancer_stats_show")
    def load_balancer_stats_show(self, lb_id, **kwargs):
        """Shows the current statistics for a load balancer.

        :param string lb:
            dict of the load balancer
        :return:
            A dict of the specified load balancer's statistics
        """
        return self._clients.octavia().load_balancer_stats_show(
            lb_id, **kwargs)

    @atomic.action_timer("octavia.load_balancer_failover")
    def load_balancer_failover(self, lb_id):
        """Trigger load balancer failover

        :param string lb:
            dict of the load balancer to failover
        :return:
            Response Code from the API
        """
        return self._clients.octavia().load_balancer_failover(lb_id)

    @atomic.action_timer("octavia.listener_list")
    def listener_list(self, **kwargs):
        """List all listeners

        :param kwargs:
            Parameters to filter on
        :return:
            List of listeners
        """
        return self._clients.octavia().listener_list(**kwargs)

    @atomic.action_timer("octavia.listener_show")
    def listener_show(self, listener_id):
        """Show a listener

        :param string listener_id:
            ID of the listener to show
        :return:
            A dict of the specified listener's settings
        """
        return self._clients.octavia().listener_show(listener_id)

    @atomic.action_timer("octavia.listener_create")
    def listener_create(self, **kwargs):
        """Create a listener

        :param kwargs:
            Parameters to create a listener with (expects json=)
        :return:
            A dict of the created listener's settings
        """
        return self._clients.octavia().listener_create(**kwargs)

    @atomic.action_timer("octavia.listener_delete")
    def listener_delete(self, listener_id):
        """Delete a listener

        :param stirng listener_id:
            ID of listener to delete
        :return:
            Response Code from the API
        """
        return self._clients.octavia().listener_delete(listener_id)

    @atomic.action_timer("octavia.listener_set")
    def listener_set(self, listener_id, **kwargs):
        """Update a listener's settings

        :param string listener_id:
            ID of the listener to update
        :param kwargs:
            A dict of arguments to update a listener
        :return:
            Response Code from the API
        """
        return self._clients.octavia().listener_set(listener_id, **kwargs)

    @atomic.action_timer("octavia.listener_stats_show")
    def listener_stats_show(self, listener_id, **kwargs):
        """Shows the current statistics for a listener

        :param string listener_id:
            ID of the listener
        :return:
            A dict of the specified listener's statistics
        """
        return self._clients.octavia().listener_stats_show(
            listener_id, **kwargs)

    @atomic.action_timer("octavia.pool_list")
    def pool_list(self, **kwargs):
        """List all pools

        :param kwargs:
            Parameters to filter on
        :return:
            List of pools
        """
        return self._clients.octavia().pool_list(**kwargs)

    def update_pool_resource(self, pool):
        try:
            new_pool = self._clients.octavia().pool_show(pool["id"])
        except Exception as e:
            if getattr(e, "status_code", 400) == 404:
                raise exceptions.GetResourceNotFound(resource=pool)
            raise exceptions.GetResourceFailure(resource=pool, err=e)
        return new_pool

    @atomic.action_timer("octavia.pool_create")
    def pool_create(self, lb_id, protocol, lb_algorithm,
                    listener_id=None, description=None,
                    admin_state_up=True, project_id=None,
                    session_persistence=None):
        """Create a pool

        :param lb_id: ID of the loadbalancer
        :param protocol: protocol of the resource
        :param lb_algorithm: loadbalancing algorithm of the pool
        :param listener_id: ID of the listener
        :param description: a human readable description of the pool
        :param admin_state_up: administrative state of the resource
        :param project_id: project ID of the resource
        :param session_persistence: a json object specifiying the session
            persistence of the pool
        :return:
            A dict of the created pool's settings
        """
        args = {
            "name": self.generate_random_name(),
            "loadbalancer_id": lb_id,
            "protocol": protocol,
            "lb_algorithm": lb_algorithm,
            "listener_id": listener_id,
            "description": description,
            "admin_state_up": admin_state_up,
            "project_id": project_id,
            "session_persistence": session_persistence
        }
        pool = self._clients.octavia().pool_create(
            json={"pool": args})
        pool = pool["pool"]
        pool = utils.wait_for_status(
            pool,
            ready_statuses=["ACTIVE"],
            status_attr="provisioning_status",
            update_resource=self.update_pool_resource,
            timeout=CONF.openstack.octavia_create_loadbalancer_timeout,
            check_interval=(
                CONF.openstack.octavia_create_loadbalancer_poll_interval)
        )
        return pool

    @atomic.action_timer("octavia.pool_delete")
    def pool_delete(self, pool_id):
        """Delete a pool

        :param string pool_id:
            ID of pool to delete
        :return:
            Response Code from the API
        """
        return self._clients.octavia().pool_delete(pool_id)

    @atomic.action_timer("octavia.pool_show")
    def pool_show(self, pool_id):
        """Show a pool's settings

        :param string pool_id:
            ID of the pool to show
        :return:
            Dict of the specified pool's settings
        """
        return self._clients.octavia().pool_show(pool_id)

    @atomic.action_timer("octavia.pool_set")
    def pool_set(self, pool_id, pool_update_args):
        """Update a pool's settings

        :param pool_id:
            ID of the pool to update
        :param pool_update_args:
            A dict of arguments to update a pool
        :return:
            Response Code from the API
        """
        return self._clients.octavia().pool_set(
            pool_id, json={"pool": pool_update_args})

    @atomic.action_timer("octavia.member_list")
    def member_list(self, pool_id, **kwargs):
        """Lists the member from a given pool id

        :param pool_id:
            ID of the pool
        :param kwargs:
            A dict of filter arguments
        :return:
            Response list members
        """
        return self._clients.octavia().member_list(pool_id, **kwargs)

    @atomic.action_timer("octavia.member_show")
    def member_show(self, pool_id, member_id):
        """Showing a member details of a pool

        :param pool_id:
            ID of pool the member is added
        :param member_id:
            ID of the member
        :param kwargs:
            A dict of arguments
        :return:
            Response of member
        """
        return self._clients.octavia().member_show(pool_id, member_id)

    @atomic.action_timer("octavia.member_create")
    def member_create(self, pool_id, **kwargs):
        """Creating a member for the given pool id

        :param pool_id:
            ID of pool to which member is added
        :param kwargs:
            A Dict of arguments
        :return:
            A member details on successful creation
        """
        return self._clients.octavia().member_create(pool_id, **kwargs)

    @atomic.action_timer("octavia.member_delete")
    def member_delete(self, pool_id, member_id):
        """Removing a member from a pool and mark that member as deleted

        :param pool_id:
            ID of the pool
        :param member_id:
            ID of the member to be deleted
        :return:
            Response code from the API
        """
        return self._clients.octavia().member_delete(pool_id, member_id)

    @atomic.action_timer("octavia.member_set")
    def member_set(self, pool_id, member_id, **kwargs):
        """Updating a member settings

        :param pool_id:
            ID of the pool
        :param member_id:
            ID of the member to be updated
        :param kwargs:
            A dict of the values of member to be updated
        :return:
            Response code from the API
        """
        return self._clients.octavia().member_set(pool_id, member_id, **kwargs)

    @atomic.action_timer("octavia.l7policy_list")
    def l7policy_list(self, **kwargs):
        """List all l7policies

        :param kwargs:
            Parameters to filter on
        :return:
            List of l7policies
        """
        return self._clients.octavia().l7policy_list(**kwargs)

    @atomic.action_timer("octavia.l7policy_create")
    def l7policy_create(self, **kwargs):
        """Create a l7policy

        :param kwargs:
            Parameters to create a l7policy with (expects json=)
        :return:
            A dict of the created l7policy's settings
        """
        return self._clients.octavia().l7policy_create(**kwargs)

    @atomic.action_timer("octavia.l7policy_delete")
    def l7policy_delete(self, l7policy_id):
        """Delete a l7policy

        :param string l7policy_id:
            ID of l7policy to delete
        :return:
            Response Code from the API
        """
        return self._clients.octavia().l7policy_delete(l7policy_id)

    @atomic.action_timer("octavia.l7policy_show")
    def l7policy_show(self, l7policy_id):
        """Show a l7policy's settings

        :param string l7policy_id:
            ID of the l7policy to show
        :return:
            Dict of the specified l7policy's settings
        """
        return self._clients.octavia().l7policy_show(l7policy_id)

    @atomic.action_timer("octavia.l7policy_set")
    def l7policy_set(self, l7policy_id, **kwargs):
        """Update a l7policy's settings

        :param l7policy_id:
            ID of the l7policy to update
        :param kwargs:
            A dict of arguments to update a l7policy
        :return:
            Response Code from the API
        """
        return self._clients.octavia().l7policy_set(l7policy_id, **kwargs)

    @atomic.action_timer("octavia.l7rule_list")
    def l7rule_list(self, l7policy_id, **kwargs):
        """List all l7rules for a l7policy

        :param kwargs:
            Parameters to filter on
        :return:
            List of l7policies
        """
        return self._clients.octavia().l7rule_list(l7policy_id, **kwargs)

    @atomic.action_timer("octavia.l7rule_create")
    def l7rule_create(self, l7policy_id, **kwargs):
        """Create a l7rule

        :param string l7policy_id:
            The l7policy to create the l7rule for
        :param kwargs:
            Parameters to create a l7rule with (expects json=)
        :return:
            A dict of the created l7rule's settings
        """
        return self._clients.octavia().l7rule_create(l7policy_id, **kwargs)

    @atomic.action_timer("octavia.l7rule_delete")
    def l7rule_delete(self, l7rule_id, l7policy_id):
        """Delete a l7rule

        :param string l7rule_id:
            ID of listener to delete
        :param string l7policy_id:
            ID of the l7policy for this l7rule
        :return:
            Response Code from the API
        """
        return self._clients.octavia().l7rule_delete(l7rule_id, l7policy_id)

    @atomic.action_timer("octavia.l7rule_show")
    def l7rule_show(self, l7rule_id, l7policy_id):
        """Show a l7rule's settings

        :param string l7rule_id:
            ID of the l7rule to show
        :param string l7policy_id:
            ID of the l7policy for this l7rule
        :return:
            Dict of the specified l7rule's settings
        """
        return self._clients.octavia().l7rule_show(l7rule_id, l7policy_id)

    @atomic.action_timer("octavia.l7rule_set")
    def l7rule_set(self, l7rule_id, l7policy_id, **kwargs):
        """Update a l7rule's settings

        :param l7rule_id:
            ID of the l7rule to update
        :param string l7policy_id:
            ID of the l7policy for this l7rule
        :param kwargs:
            A dict of arguments to update a l7rule
        :return:
            Response Code from the API
        """
        return self._clients.octavia().l7rule_set(l7rule_id, l7policy_id,
                                                  **kwargs)

    @atomic.action_timer("octavia.health_monitor_list")
    def health_monitor_list(self, **kwargs):
        """List all health monitors

        :param kwargs:
            Parameters to filter on
        :return:
            A dict containing a list of health monitors
        """
        return self._clients.octavia().health_monitor_list(**kwargs)

    @atomic.action_timer("octavia.health_monitor_create")
    def health_monitor_create(self, **kwargs):
        """Create a health monitor

        :param kwargs:
            Parameters to create a health monitor with (expects json=)
        :return:
            A dict of the created health monitor's settings
        """
        return self._clients.octavia().health_monitor_create(**kwargs)

    @atomic.action_timer("octavia.health_monitor_delete")
    def health_monitor_delete(self, health_monitor_id):
        """Delete a health_monitor

        :param string health_monitor_id:
            ID of health monitor to delete
        :return:
            Response Code from the API
        """
        return self._clients.octavia().health_monitor_delete(health_monitor_id)

    @atomic.action_timer("octavia.health_monitor_show")
    def health_monitor_show(self, health_monitor_id):
        """Show a health monitor's settings

        :param string health_monitor_id:
            ID of the health monitor to show
        :return:
            Dict of the specified health monitor's settings
        """
        return self._clients.octavia().health_monitor_show(health_monitor_id)

    @atomic.action_timer("octavia.health_monitor_set")
    def health_monitor_set(self, health_monitor_id, **kwargs):
        """Update a health monitor's settings

        :param health_monitor_id:
            ID of the health monitor to update
        :param kwargs:
            A dict of arguments to update a l7policy
        :return:
            Response Code from the API
        """
        return self._clients.octavia().health_monitor_set(health_monitor_id,
                                                          **kwargs)

    @atomic.action_timer("octavia.quota_list")
    def quota_list(self, params):
        """List all quotas

        :param params:
            Parameters to filter on (not implemented)
        :return:
            A ``dict`` representing a list of quotas for the project
        """
        return self._clients.octavia().quota_list(params)

    @atomic.action_timer("octavia.quota_show")
    def quota_show(self, project_id):
        """Show a quota

        :param string project_id:
            ID of the project to show
        :return:
            A ``dict`` representing the quota for the project
        """
        return self._clients.octavia().quota_show(project_id)

    @atomic.action_timer("octavia.quota_reset")
    def quota_reset(self, project_id):
        """Reset a quota

        :param string project_id:
            The ID of the project to reset quotas
        :return:
            ``None``
        """
        return self._clients.octavia().quota_reset(project_id)

    @atomic.action_timer("octavia.quota_set")
    def quota_set(self, project_id, params):
        """Update a quota's settings

        :param string project_id:
            The ID of the project to update
        :param params:
            A ``dict`` of arguments to update project quota
        :return:
            A ``dict`` representing the updated quota
        """
        return self._clients.octavia().quota_set(project_id, params)

    @atomic.action_timer("octavia.quota_defaults_show")
    def quota_defaults_show(self):
        """Show quota defaults

        :return:
            A ``dict`` representing a list of quota defaults
        """
        return self._clients.octavia().quota_defaults_show()

    @atomic.action_timer("octavia.amphora_show")
    def amphora_show(self, amphora_id):
        """Show an amphora

        :param string amphora_id:
            ID of the amphora to show
        :return:
            A ``dict`` of the specified amphora's attributes
        """
        return self._clients.octavia().amphora_show(amphora_id)

    @atomic.action_timer("octavia.amphora_list")
    def amphora_list(self, **kwargs):
        """List all amphorae

        :param kwargs:
            Parameters to filter on
        :return:
            A ``dict`` containing a list of amphorae
        """
        return self._clients.octavia().amphora_list(**kwargs)

    @atomic.action_timer("octavia.wait_for_loadbalancers")
    def wait_for_loadbalancer_prov_status(self, lb, prov_status="ACTIVE"):
        return utils.wait_for_status(
            lb,
            ready_statuses=[prov_status],
            status_attr="provisioning_status",
            update_resource=lambda lb: self.load_balancer_show(lb["id"]),
            timeout=CONF.openstack.octavia_create_loadbalancer_timeout,
            check_interval=(
                CONF.openstack.octavia_create_loadbalancer_poll_interval)
        )
