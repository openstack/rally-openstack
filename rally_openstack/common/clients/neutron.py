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


if t.TYPE_CHECKING:
    import typing_extensions as te
    from openstack.network.v2._proxy import Proxy as NetworkProxy
    from openstack.network.v2.network import Network
    from openstack.network.v2.port import Port
    from openstack.network.v2.tap_mirror import TapMirror


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
        self._network.delete_network(network_id)

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
        self._network.delete_port(port_id)

    @atomic.action_timer("neutron.create_tap_mirror")
    def create_tap_mirror(
        self,
        port_id: str,
        directions: dict[str, int],
        remote_ip: str,
        mirror_type: MirrorType = MirrorType.GRE,
        description: str | None = None,
    ) -> TapMirror:
        kwargs: dict[str, t.Any] = {
            "name": self.generate_random_name(),
            "port_id": port_id,
            "directions": directions,
            "remote_ip": remote_ip,
            "mirror_type": mirror_type.value,
        }
        if description is not None:
            kwargs["description"] = description
        return self._network.create_tap_mirror(**kwargs)

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
        update_args: dict[str, t.Any] = {}
        if name:
            update_args["name"] = name
        if description is not None:
            update_args["description"] = description
        if not update_args:
            raise ValueError(
                "update_tap_mirror requires at least name or description")
        return self._network.update_tap_mirror(
            tap_mirror_id, **update_args)

    @atomic.action_timer("neutron.delete_tap_mirror")
    def delete_tap_mirror(self, tap_mirror_id: str) -> None:
        self._network.delete_tap_mirror(tap_mirror_id)
