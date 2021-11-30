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

from rally_openstack.common.services.network import neutron
from rally_openstack.task.cleanup import manager as resource_manager
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
        "ethertype",
        "direction",
        "port_range_max",
        "port_range_min",
        "protocol",
        "remote_ip_prefix"
    ]
    return "_".join([_normalize_rule_value(x, rule.get(x))
                     for x in comparison_keys])


_RULES_TO_ADD = [
    {
        "ethertype": "IPv4",
        "protocol": "tcp",
        "port_range_max": 65535,
        "port_range_min": 1,
        "remote_ip_prefix": "0.0.0.0/0",
        "direction": "ingress"
    },
    {
        "ethertype": "IPv6",
        "protocol": "tcp",
        "port_range_max": 65535,
        "port_range_min": 1,
        "remote_ip_prefix": "::/0",
        "direction": "ingress"
    },
    {
        "ethertype": "IPv4",
        "protocol": "udp",
        "port_range_max": 65535,
        "port_range_min": 1,
        "remote_ip_prefix": "0.0.0.0/0",
        "direction": "ingress"
    },
    {
        "ethertype": "IPv6",
        "protocol": "udp",
        "port_range_max": 65535,
        "port_range_min": 1,
        "remote_ip_prefix": "::/0",
        "direction": "ingress"
    },
    {
        "ethertype": "IPv4",
        "protocol": "icmp",
        "remote_ip_prefix": "0.0.0.0/0",
        "direction": "ingress"
    },
    {
        "ethertype": "IPv6",
        "protocol": "ipv6-icmp",
        "remote_ip_prefix": "::/0",
        "direction": "ingress"
    }
]


@validation.add("required_platform", platform="openstack", users=True)
@context.configure(name="allow_ssh", platform="openstack", order=320)
class AllowSSH(context.OpenStackContext):
    """Sets up security groups for all users to access VM via SSH."""

    def setup(self):
        client = neutron.NeutronService(
            clients=self.context["users"][0]["credential"].clients(),
            name_generator=self.generate_random_name,
            atomic_inst=self.atomic_actions()
        )

        if not client.supports_extension("security-group", silent=True):
            LOG.info("Security group context is disabled.")
            return

        secgroup_name = self.generate_random_name()
        secgroups_per_tenant = {}
        for user, tenant_id in self._iterate_per_tenants():
            client = neutron.NeutronService(
                clients=user["credential"].clients(),
                name_generator=self.generate_random_name,
                atomic_inst=self.atomic_actions()
            )
            secgroup = client.create_security_group(
                name=secgroup_name,
                description="Allow ssh access to VMs created by Rally")
            secgroups_per_tenant[tenant_id] = secgroup

            existing_rules = set(
                _rule_to_key(rule)
                for rule in secgroup.get("security_group_rules", []))
            for new_rule in _RULES_TO_ADD:
                if _rule_to_key(new_rule) not in existing_rules:
                    secgroup.setdefault("security_group_rules", [])
                    secgroup["security_group_rules"].append(
                        client.create_security_group_rule(
                            security_group_id=secgroup["id"], **new_rule)
                    )

        for user in self.context["users"]:
            user["secgroup"] = secgroups_per_tenant[user["tenant_id"]]

    def cleanup(self):
        resource_manager.cleanup(
            names=["neutron.security_group"],
            admin=self.context.get("admin"),
            users=self.context["users"],
            task_id=self.get_owner_id(),
            superclass=self.__class__
        )
