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

from __future__ import annotations

import enum
import typing as t

from rally.task import atomic

from rally_openstack.common.clients import base


class MirrorType(enum.StrEnum):
    """Tap mirror encapsulation type."""

    GRE = "gre"
    ERSPANV1 = "erspanv1"


MirrorDirection = t.Literal["IN", "OUT"]

TapFlowDirection = t.Literal["IN", "OUT", "BOTH"]


class FirewallAction(enum.StrEnum):
    """What a firewall rule does with the traffic it matches."""

    ALLOW = "allow"
    DENY = "deny"
    REJECT = "reject"


class FirewallProtocol(enum.StrEnum):
    """IP protocol a firewall rule matches."""

    # The API expresses "any protocol" as null, which this client reserves
    # for "leave the field alone".
    ANY = "any"
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    IPV6_ICMP = "ipv6-icmp"
    SCTP = "sctp"
    DCCP = "dccp"


IPVersion = t.Literal[4, 6]

# A single port or a "min:max" range.
PortRange = int | str

# neutron-fwaas creates a group with this name, two policies and four rules
# for every project that touches the FWaaS API, and only admin may delete it.
DEFAULT_FIREWALL_GROUP_NAME = "default"


def _clean_dict(**kwargs: t.Any) -> dict[str, t.Any]:
    """Build a dict from keyword arguments, dropping the ones set to None."""
    return {k: v for k, v in kwargs.items() if v is not None}


if t.TYPE_CHECKING:
    import typing_extensions as te
    from openstack.network.v2._proxy import Proxy as NetworkProxy
    from openstack.network.v2.extension import Extension
    from openstack.network.v2.firewall_group import FirewallGroup
    from openstack.network.v2.firewall_policy import FirewallPolicy
    from openstack.network.v2.firewall_rule import FirewallRule
    from openstack.network.v2.network import Network
    from openstack.network.v2.port import Port
    from openstack.network.v2.security_group import SecurityGroup
    from openstack.network.v2.tap_flow import TapFlow
    from openstack.network.v2.tap_mirror import TapMirror
    from openstack.network.v2.tap_service import TapService
    from openstack.network.v2.trunk import Trunk


@base.configure(
    "neutron",
    sdk_service_type="network",
    default_version="2.0",
    default_service_type="network",
    supported_versions=["2.0"],
)
class Neutron(base.LegacyClientCompat):
    """Network (neutron) client backed by openstacksdk.

    Legacy ``python-neutronclient`` access remains via ``clients.neutron()``.
    Operations implemented on this class use openstacksdk and record
    ``neutron.<op>`` atomic actions.
    """

    @property
    def _network(self) -> NetworkProxy:
        """Return the openstacksdk network v2 proxy."""
        return self._conn.network

    def create_client(
        self,
        version: str | int | None = None,
        service_type: str | None = None,
    ) -> t.Any:
        """Return a neutronclient instance."""
        from neutronclient.neutron import client as neutron

        kw_args: dict[str, t.Any] = {}
        if self.credential.endpoint_type:
            kw_args["endpoint_type"] = self.credential.endpoint_type

        return neutron.Client(
            self.choose_version(version),
            session=self.keystone.get_session()[0],
            endpoint_override=self._get_endpoint(service_type),
            **kw_args,
        )

    @t.overload
    def __call__(
        self,
        version: str | int | None = ...,
        *,
        legacy: t.Literal[False],
    ) -> te.Self: ...

    @t.overload
    def __call__(
        self,
        version: str | int | None = ...,
        *,
        legacy: t.Literal[True] = ...,
    ) -> t.Any: ...

    def __call__(
        self,
        version: str | int | None = None,
        *,
        legacy: bool = True,
    ) -> t.Any:
        """Return a neutron client.

        :param version: API version (default ``2.0``).
        :param legacy: when true (default), return ``python-neutronclient``.
            Pass ``legacy=False`` to return this client for openstacksdk
            operations defined on this class.
        """
        if legacy:
            key = f"{self.get_name()}{version or ''}"
            if key not in self._cache:
                self._cache[key] = self.create_client(version)
            return self._cache[key]
        return self

    @atomic.action_timer("neutron.create_network")
    def create_network(
        self,
        name: str | None = None,
        **kwargs: t.Any,
    ) -> Network:
        if name is None:
            kwargs.setdefault("name", self.generate_random_name())
        else:
            kwargs["name"] = name
        return self._network.create_network(**kwargs)

    @atomic.action_timer("neutron.list_networks")
    def list_networks(self, **filters: t.Any) -> list[Network]:
        return list(self._network.networks(**filters))

    @atomic.action_timer("neutron.show_network")
    def get_network(self, network_id: str) -> Network:
        return self._network.get_network(network_id)

    @atomic.action_timer("neutron.delete_network")
    def delete_network(self, network_id: str) -> None:
        self._network.delete_network(network_id, ignore_missing=False)

    @atomic.action_timer("neutron.create_port")
    def create_port(
        self,
        network_id: str,
        name: str | None = None,
        **kwargs: t.Any,
    ) -> Port:
        return self._network.create_port(
            network_id=network_id,
            name=name or self.generate_random_name(),
            **kwargs,
        )

    @atomic.action_timer("neutron.list_ports")
    def list_ports(self, **filters: t.Any) -> list[Port]:
        return list(self._network.ports(**filters))

    @atomic.action_timer("neutron.show_port")
    def get_port(self, port_id: str) -> Port:
        return self._network.get_port(port_id)

    @atomic.action_timer("neutron.delete_port")
    def delete_port(self, port_id: str) -> None:
        self._network.delete_port(port_id, ignore_missing=False)

    @atomic.action_timer("neutron.create_tap_mirror")
    def create_tap_mirror(
        self,
        port_id: str,
        directions: dict[str, int],
        remote_ip: str,
        mirror_type: MirrorType = MirrorType.GRE,
        description: str | None = None,
    ) -> TapMirror:
        return self._network.create_tap_mirror(**_clean_dict(
            name=self.generate_random_name(),
            port_id=port_id,
            directions=directions,
            remote_ip=remote_ip,
            mirror_type=mirror_type.value,
            description=description,
        ))

    @atomic.action_timer("neutron.list_tap_mirrors")
    def list_tap_mirrors(self, **filters: t.Any) -> list[TapMirror]:
        return list(self._network.tap_mirrors(**filters))

    @atomic.action_timer("neutron.show_tap_mirror")
    def get_tap_mirror(self, tap_mirror_id: str) -> TapMirror:
        return self._network.get_tap_mirror(tap_mirror_id)

    @atomic.action_timer("neutron.update_tap_mirror")
    def update_tap_mirror(
        self,
        tap_mirror_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> TapMirror:
        update_args = _clean_dict(name=name, description=description)
        if not update_args:
            raise ValueError(
                "update_tap_mirror requires at least name or description")
        return self._network.update_tap_mirror(
            tap_mirror_id, **update_args)

    @atomic.action_timer("neutron.delete_tap_mirror")
    def delete_tap_mirror(self, tap_mirror_id: str) -> None:
        self._network.delete_tap_mirror(tap_mirror_id, ignore_missing=False)

    @atomic.action_timer("neutron.create_tap_service")
    def create_tap_service(
        self,
        port_id: str,
        description: str | None = None,
    ) -> TapService:
        return self._network.create_tap_service(**_clean_dict(
            name=self.generate_random_name(),
            port_id=port_id,
            description=description,
        ))

    @atomic.action_timer("neutron.list_tap_services")
    def list_tap_services(self) -> list[TapService]:
        return list(self._network.tap_services())

    @atomic.action_timer("neutron.show_tap_service")
    def get_tap_service(self, tap_service_id: str) -> TapService:
        return self._network.get_tap_service(tap_service_id)

    @atomic.action_timer("neutron.update_tap_service")
    def update_tap_service(
        self,
        tap_service_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> TapService:
        update_args = _clean_dict(name=name, description=description)
        if not update_args:
            raise ValueError(
                "update_tap_service requires at least name or description")
        return self._network.update_tap_service(
            tap_service_id, **update_args)

    @atomic.action_timer("neutron.delete_tap_service")
    def delete_tap_service(self, tap_service_id: str) -> None:
        self._network.delete_tap_service(
            tap_service_id, ignore_missing=False)

    @atomic.action_timer("neutron.list_security_groups")
    def list_security_groups(
        self,
        project_id: str | None = None,
        name: str | None = None,
    ) -> list[SecurityGroup]:
        return list(self._network.security_groups(
            **_clean_dict(project_id=project_id, name=name)))

    @atomic.action_timer("neutron.delete_security_group")
    def delete_security_group(self, security_group_id: str) -> None:
        self._network.delete_security_group(
            security_group_id, ignore_missing=False)

    def list_extensions(self) -> list[Extension]:
        """Return the extensions neutron has loaded."""
        key = "neutron:extensions"
        if key not in self._cache:
            self._cache[key] = list(self._network.extensions())
        return self._cache[key]

    def supports_extension(self, alias: str) -> bool:
        """Tell whether neutron has the extension with this alias loaded."""
        return any(ext.alias == alias for ext in self.list_extensions())

    @atomic.action_timer("neutron.create_firewall_rule")
    def create_firewall_rule(
        self,
        *,
        protocol: FirewallProtocol = FirewallProtocol.ANY,
        action: FirewallAction | None = None,
        ip_version: IPVersion | None = None,
        source_ip_address: str | None = None,
        destination_ip_address: str | None = None,
        source_port: PortRange | None = None,
        destination_port: PortRange | None = None,
        enabled: bool | None = None,
        shared: bool | None = None,
        description: str | None = None,
    ) -> FirewallRule:
        """Create a firewall rule with a generated name.

        Arguments left as None are not sent, so neutron applies its own
        defaults (IPv4, ``deny``, enabled, not shared).
        """
        attrs = _clean_dict(
            action=action,
            ip_version=ip_version,
            source_ip_address=source_ip_address,
            destination_ip_address=destination_ip_address,
            source_port=source_port,
            destination_port=destination_port,
            enabled=enabled,
            shared=shared,
            description=description,
        )
        attrs["protocol"] = (
            None if protocol == FirewallProtocol.ANY else protocol)
        return self._network.create_firewall_rule(
            name=self.generate_random_name(), **attrs)

    @atomic.action_timer("neutron.list_firewall_rules")
    def list_firewall_rules(
        self, project_id: str | None = None
    ) -> list[FirewallRule]:
        return list(self._network.firewall_rules(
            **_clean_dict(project_id=project_id)))

    @atomic.action_timer("neutron.update_firewall_rule")
    def update_firewall_rule(
        self,
        rule_id: str,
        *,
        name: str | None = None,
        protocol: FirewallProtocol | None = None,
        action: FirewallAction | None = None,
        ip_version: IPVersion | None = None,
        source_ip_address: str | None = None,
        destination_ip_address: str | None = None,
        source_port: PortRange | None = None,
        destination_port: PortRange | None = None,
        enabled: bool | None = None,
        shared: bool | None = None,
        description: str | None = None,
    ) -> FirewallRule:
        """Update a firewall rule. Only the arguments given are changed.

        :param protocol: new protocol, ``any`` to match every protocol
        """
        attrs = _clean_dict(
            name=name,
            action=action,
            ip_version=ip_version,
            source_ip_address=source_ip_address,
            destination_ip_address=destination_ip_address,
            source_port=source_port,
            destination_port=destination_port,
            enabled=enabled,
            shared=shared,
            description=description,
        )
        if protocol is not None:
            attrs["protocol"] = (
                None if protocol == FirewallProtocol.ANY else protocol)
        if not attrs:
            raise ValueError("update_firewall_rule requires something to "
                             "change")
        return self._network.update_firewall_rule(rule_id, **attrs)

    @atomic.action_timer("neutron.delete_firewall_rule")
    def delete_firewall_rule(self, rule_id: str) -> None:
        self._network.delete_firewall_rule(rule_id, ignore_missing=False)

    @atomic.action_timer("neutron.create_firewall_policy")
    def create_firewall_policy(
        self,
        *,
        firewall_rules: list[str] | None = None,
        audited: bool | None = None,
        shared: bool | None = None,
        description: str | None = None,
    ) -> FirewallPolicy:
        """Create a firewall policy with a generated name.

        :param firewall_rules: ids of the rules, in the order they apply
        """
        return self._network.create_firewall_policy(**_clean_dict(
            name=self.generate_random_name(),
            firewall_rules=firewall_rules,
            audited=audited,
            shared=shared,
            description=description,
        ))

    @atomic.action_timer("neutron.list_firewall_policies")
    def list_firewall_policies(
        self, project_id: str | None = None
    ) -> list[FirewallPolicy]:
        return list(self._network.firewall_policies(
            **_clean_dict(project_id=project_id)))

    @atomic.action_timer("neutron.show_firewall_policy")
    def get_firewall_policy(self, policy_id: str) -> FirewallPolicy:
        return self._network.get_firewall_policy(policy_id)

    @atomic.action_timer("neutron.update_firewall_policy")
    def update_firewall_policy(
        self,
        policy_id: str,
        *,
        name: str | None = None,
        firewall_rules: list[str] | None = None,
        audited: bool | None = None,
        shared: bool | None = None,
        description: str | None = None,
    ) -> FirewallPolicy:
        """Update a firewall policy. Only the arguments given are changed.

        :param firewall_rules: ids of the rules replacing the current ones
        """
        attrs = _clean_dict(
            name=name,
            firewall_rules=firewall_rules,
            audited=audited,
            shared=shared,
            description=description,
        )
        if not attrs:
            raise ValueError("update_firewall_policy requires something to "
                             "change")
        return self._network.update_firewall_policy(policy_id, **attrs)

    @atomic.action_timer("neutron.delete_firewall_policy")
    def delete_firewall_policy(self, policy_id: str) -> None:
        self._network.delete_firewall_policy(policy_id, ignore_missing=False)

    @atomic.action_timer("neutron.insert_firewall_rule_in_policy")
    def insert_firewall_rule_in_policy(
        self,
        policy_id: str,
        rule_id: str,
        *,
        insert_before: str | None = None,
        insert_after: str | None = None,
    ) -> FirewallPolicy:
        """Insert a rule into a policy.

        :param insert_before: id of a policy rule to place the new one before
        :param insert_after: id of a policy rule to place the new one after;
            ignored when ``insert_before`` is given
        """
        return self._network.insert_rule_into_policy(
            policy_id, rule_id,
            insert_after=insert_after, insert_before=insert_before)

    @atomic.action_timer("neutron.remove_firewall_rule_from_policy")
    def remove_firewall_rule_from_policy(
        self, policy_id: str, rule_id: str
    ) -> FirewallPolicy:
        return self._network.remove_rule_from_policy(policy_id, rule_id)

    @atomic.action_timer("neutron.create_firewall_group")
    def create_firewall_group(
        self,
        *,
        ingress_firewall_policy_id: str | None = None,
        egress_firewall_policy_id: str | None = None,
        ports: list[str] | None = None,
        admin_state_up: bool | None = None,
        shared: bool | None = None,
        description: str | None = None,
    ) -> FirewallGroup:
        """Create a firewall group with a generated name.

        :param ports: ids of the router or VM ports to protect
        """
        return self._network.create_firewall_group(**_clean_dict(
            name=self.generate_random_name(),
            ingress_firewall_policy_id=ingress_firewall_policy_id,
            egress_firewall_policy_id=egress_firewall_policy_id,
            ports=ports,
            admin_state_up=admin_state_up,
            shared=shared,
            description=description,
        ))

    @atomic.action_timer("neutron.list_firewall_groups")
    def list_firewall_groups(
        self,
        project_id: str | None = None,
        name: str | None = None,
    ) -> list[FirewallGroup]:
        return list(self._network.firewall_groups(
            **_clean_dict(project_id=project_id, name=name)))

    @atomic.action_timer("neutron.update_firewall_group")
    def update_firewall_group(
        self,
        group_id: str,
        *,
        name: str | None = None,
        ingress_firewall_policy_id: str | None = None,
        egress_firewall_policy_id: str | None = None,
        admin_state_up: bool | None = None,
        shared: bool | None = None,
        description: str | None = None,
    ) -> FirewallGroup:
        """Update a firewall group. Only the arguments given are changed.

        Ports are changed with :meth:`associate_firewall_group_ports` and
        :meth:`disassociate_firewall_group_ports`.
        """
        attrs = _clean_dict(
            name=name,
            ingress_firewall_policy_id=ingress_firewall_policy_id,
            egress_firewall_policy_id=egress_firewall_policy_id,
            admin_state_up=admin_state_up,
            shared=shared,
            description=description,
        )
        if not attrs:
            raise ValueError("update_firewall_group requires something to "
                             "change")
        return self._network.update_firewall_group(group_id, **attrs)

    @atomic.action_timer("neutron.associate_firewall_group_port")
    def associate_firewall_group_ports(
        self, group_id: str, port_ids: list[str]
    ) -> FirewallGroup:
        """Make these ports the ones the group protects."""
        return self._network.update_firewall_group(group_id, ports=port_ids)

    @atomic.action_timer("neutron.disassociate_firewall_group_port")
    def disassociate_firewall_group_ports(
        self, group_id: str
    ) -> FirewallGroup:
        """Detach every port from the group."""
        return self._network.update_firewall_group(group_id, ports=[])

    @atomic.action_timer("neutron.delete_firewall_group")
    def delete_firewall_group(self, group_id: str) -> None:
        self._network.delete_firewall_group(group_id, ignore_missing=False)

    @atomic.action_timer("neutron.list_trunks")
    def list_trunks(self, **filters: t.Any) -> list[Trunk]:
        return list(self._network.trunks(**filters))

    @atomic.action_timer("neutron.delete_trunk")
    def delete_trunk(self, trunk_id: str) -> None:
        self._network.delete_trunk(trunk_id)

    @atomic.action_timer("neutron.create_tap_flow")
    def create_tap_flow(
        self,
        tap_service_id: str,
        source_port: str,
        direction: TapFlowDirection = "IN",
        description: str | None = None,
    ) -> TapFlow:
        kwargs: dict[str, t.Any] = {
            "name": self.generate_random_name(),
            "tap_service_id": tap_service_id,
            "source_port": source_port,
            "direction": direction,
        }
        if description is not None:
            kwargs["description"] = description
        return self._network.create_tap_flow(**kwargs)

    @atomic.action_timer("neutron.list_tap_flows")
    def list_tap_flows(
        self,
        project_id: str | None = None,
        name: str | None = None,
    ) -> list[TapFlow]:
        """List tap flows matching the supplied filters."""
        return list(self._network.tap_flows(
            **_clean_dict(project_id=project_id, name=name)))

    @atomic.action_timer("neutron.show_tap_flow")
    def get_tap_flow(self, tap_flow_id: str) -> TapFlow:
        return self._network.get_tap_flow(tap_flow_id)

    @atomic.action_timer("neutron.update_tap_flow")
    def update_tap_flow(
        self,
        tap_flow_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> TapFlow:
        update_args: dict[str, t.Any] = {}
        if name:
            update_args["name"] = name
        if description is not None:
            update_args["description"] = description
        if not update_args:
            raise ValueError(
                "update_tap_flow requires at least name or description")
        return self._network.update_tap_flow(
            tap_flow_id, **update_args)

    @atomic.action_timer("neutron.delete_tap_flow")
    def delete_tap_flow(self, tap_flow_id: str) -> None:
        self._network.delete_tap_flow(
            tap_flow_id, ignore_missing=False)
