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

from rally.common import logging
from rally.common import validation

from rally_openstack.common import osclients
from rally_openstack.common.wrappers import network
from rally_openstack.task import context


LOG = logging.getLogger(__name__)


# This method is simplified version to what neutron has
def _rule_to_key(rule):
    def _normalize_rule_value(key, value):
        # This string is used as a placeholder for str(None), but shorter.
        none_char = "+"

        default = {
            "port_range_min": "1",
            "port_range_max": "65535"
        }

        if key == "remote_ip_prefix":
            all_address = ["0.0.0.0/0", "::/0", None]
            if value in all_address:
                return none_char
        elif value is None:
            return default.get(key, none_char)
        return str(value)

    # NOTE(andreykurilin): there are more actual comparison keys, but this set
    #   should be enough for us.
    comparison_keys = [
        "direction",
        "port_range_max",
        "port_range_min",
        "protocol",
        "remote_ip_prefix",
        "security_group_id"
    ]
    return "_".join([_normalize_rule_value(x, rule.get(x))
                     for x in comparison_keys])


def _prepare_open_secgroup(credential, secgroup_name):
    """Generate secgroup allowing all tcp/udp/icmp access.

    In order to run tests on instances it is necessary to have SSH access.
    This function generates a secgroup which allows all tcp/udp/icmp access.

    :param credential: clients credential
    :param secgroup_name: security group name

    :returns: dict with security group details
    """
    neutron = osclients.Clients(credential).neutron()
    security_groups = neutron.list_security_groups()["security_groups"]
    rally_open = [sg for sg in security_groups if sg["name"] == secgroup_name]
    if not rally_open:
        descr = "Allow ssh access to VMs created by Rally"
        rally_open = neutron.create_security_group(
            {"security_group": {"name": secgroup_name,
                                "description": descr}})["security_group"]
    else:
        rally_open = rally_open[0]

    rules_to_add = [
        {
            "protocol": "tcp",
            "port_range_max": 65535,
            "port_range_min": 1,
            "remote_ip_prefix": "0.0.0.0/0",
            "direction": "ingress",
            "security_group_id": rally_open["id"]
        },
        {
            "protocol": "udp",
            "port_range_max": 65535,
            "port_range_min": 1,
            "remote_ip_prefix": "0.0.0.0/0",
            "direction": "ingress",
            "security_group_id": rally_open["id"]
        },
        {
            "protocol": "icmp",
            "remote_ip_prefix": "0.0.0.0/0",
            "direction": "ingress",
            "security_group_id": rally_open["id"]
        }
    ]

    existing_rules = set(
        _rule_to_key(r) for r in rally_open.get("security_group_rules", []))
    for new_rule in rules_to_add:
        if _rule_to_key(new_rule) not in existing_rules:
            neutron.create_security_group_rule(
                {"security_group_rule": new_rule})

    return rally_open


@validation.add("required_platform", platform="openstack", users=True)
@context.configure(name="allow_ssh", platform="openstack", order=320)
class AllowSSH(context.OpenStackContext):
    """Sets up security groups for all users to access VM via SSH."""

    def setup(self):
        admin_or_user = (self.context.get("admin")
                         or self.context.get("users")[0])

        net_wrapper = network.wrap(
            osclients.Clients(admin_or_user["credential"]),
            self, config=self.config)
        use_sg, msg = net_wrapper.supports_extension("security-group")
        if not use_sg:
            LOG.info("Security group context is disabled: %s" % msg)
            return

        secgroup_name = self.generate_random_name()
        for user in self.context["users"]:
            user["secgroup"] = _prepare_open_secgroup(user["credential"],
                                                      secgroup_name)

    def cleanup(self):
        for user, tenant_id in self._iterate_per_tenants():
            with logging.ExceptionLogger(
                    LOG,
                    "Unable to delete security group: %s."
                    % user["secgroup"]["name"]):
                clients = osclients.Clients(user["credential"])
                clients.neutron().delete_security_group(user["secgroup"]["id"])
