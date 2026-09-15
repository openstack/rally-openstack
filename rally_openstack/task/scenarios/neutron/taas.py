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

import hashlib
import typing as t

import typing_extensions as te

from rally.task import validation

from rally_openstack.common import consts
from rally_openstack.common.clients.neutron import MirrorDirection
from rally_openstack.common.clients.neutron import MirrorType
from rally_openstack.task import scenario
from rally_openstack.task.scenarios.neutron import utils


def _tunnel_id_max(mirror_type: MirrorType) -> int:
    if mirror_type == MirrorType.ERSPANV1:
        return 1023
    return 16777215


def _allocate_tunnel_id(
    project_id: str,
    owner_id: str,
    iteration: int,
    direction: str,
    mirror_type: MirrorType,
) -> int:
    max_id = _tunnel_id_max(mirror_type)
    seed = f"{project_id}:{owner_id}:{iteration}:{direction}"
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return int(digest, 16) % max_id + 1


class TaaSScenario(utils.NeutronScenario):
    """Base class for TaaS (Tap-as-a-Service) scenarios."""

    def _mirror_type(self, mirror_type: MirrorType | str) -> MirrorType:
        if isinstance(mirror_type, str):
            return MirrorType(mirror_type)
        return mirror_type

    def _allocate_directions(
        self,
        mirror_directions: t.Sequence[MirrorDirection],
        mirror_type: MirrorType,
    ) -> dict[str, int]:
        """Map mirror direction names to unique tunnel IDs."""
        project_id = self.context["tenant"]["id"]
        owner_id = self.context["owner_id"]
        iteration = self.context["iteration"]
        return {
            direction: _allocate_tunnel_id(
                project_id, owner_id, iteration, direction, mirror_type)
            for direction in mirror_directions
        }


class TapMirrorCreateArgs(te.TypedDict, total=False):
    description: str


class TapMirrorUpdateArgs(te.TypedDict, total=False):
    description: str


"""Scenarios for Neutron TaaS (Tap-as-a-Service)."""


@validation.add("required_ports_per_project")
@validation.add("required_contexts", contexts=["network", "ports"])
@validation.add("required_neutron_extensions", extensions=["tap-mirror"])
@validation.add("required_services", services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"],
             "network@openstack": {},
             "ports@openstack": {}},
    name="NeutronTaaS.create_and_list_tap_mirrors",
    platform="openstack")
class CreateAndListTapMirrors(TaaSScenario):

    def run(
        self,
        remote_ip: str,
        mirror_type: MirrorType | str = MirrorType.GRE,
        mirror_directions: t.Sequence[MirrorDirection] = ("IN",),
        tap_mirror_create_args: TapMirrorCreateArgs | None = None,
    ) -> None:
        """Create and list Neutron TaaS tap mirrors.

        Requires ``network`` and ``ports`` contexts with
        ``ports_per_project >= ceil(concurrency / projects)``.

        :param remote_ip: destination IP for mirrored traffic
        :param mirror_type: GRE or ERSPANv1 encapsulation
        :param mirror_directions: traffic directions to mirror (IN, OUT)
        :param tap_mirror_create_args: optional description on create
        """
        tap_mirror_create_args = tap_mirror_create_args or {}
        mirror_type = self._mirror_type(mirror_type)
        directions = self._allocate_directions(mirror_directions, mirror_type)

        ports = self.context["tenant"]["ports"]
        port = ports[self.context["iteration"] % len(ports)]

        self._clients.neutron.create_tap_mirror(
            port_id=port["id"],
            directions=directions,
            remote_ip=remote_ip,
            mirror_type=mirror_type,
            description=tap_mirror_create_args.get("description"),
        )
        self._clients.neutron.list_tap_mirrors()


@validation.add("required_ports_per_project")
@validation.add("required_contexts", contexts=["network", "ports"])
@validation.add("required_neutron_extensions", extensions=["tap-mirror"])
@validation.add("required_services", services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"],
             "network@openstack": {},
             "ports@openstack": {}},
    name="NeutronTaaS.create_and_delete_tap_mirrors",
    platform="openstack")
class CreateAndDeleteTapMirrors(TaaSScenario):

    def run(
        self,
        remote_ip: str,
        mirror_type: MirrorType | str = MirrorType.GRE,
        mirror_directions: t.Sequence[MirrorDirection] = ("IN",),
        tap_mirror_create_args: TapMirrorCreateArgs | None = None,
    ) -> None:
        """Create and delete Neutron TaaS tap mirrors.

        Requires ``network`` and ``ports`` contexts with
        ``ports_per_project >= ceil(concurrency / projects)``.

        :param remote_ip: destination IP for mirrored traffic
        :param mirror_type: GRE or ERSPANv1 encapsulation
        :param mirror_directions: traffic directions to mirror (IN, OUT)
        :param tap_mirror_create_args: optional description on create
        """
        tap_mirror_create_args = tap_mirror_create_args or {}
        mirror_type = self._mirror_type(mirror_type)
        directions = self._allocate_directions(mirror_directions, mirror_type)

        ports = self.context["tenant"]["ports"]
        port = ports[self.context["iteration"] % len(ports)]

        tap_mirror = self._clients.neutron.create_tap_mirror(
            port_id=port["id"],
            directions=directions,
            remote_ip=remote_ip,
            mirror_type=mirror_type,
            description=tap_mirror_create_args.get("description"),
        )
        self._clients.neutron.delete_tap_mirror(tap_mirror.id)


@validation.add("required_ports_per_project")
@validation.add("required_contexts", contexts=["network", "ports"])
@validation.add("required_neutron_extensions", extensions=["tap-mirror"])
@validation.add("required_services", services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"],
             "network@openstack": {},
             "ports@openstack": {}},
    name="NeutronTaaS.create_and_update_tap_mirrors",
    platform="openstack")
class CreateAndUpdateTapMirrors(TaaSScenario):

    def run(
        self,
        remote_ip: str,
        mirror_type: MirrorType | str = MirrorType.GRE,
        mirror_directions: t.Sequence[MirrorDirection] = ("IN",),
        tap_mirror_create_args: TapMirrorCreateArgs | None = None,
        tap_mirror_update_args: TapMirrorUpdateArgs | None = None,
    ) -> None:
        """Create and update Neutron TaaS tap mirrors.

        Requires ``network`` and ``ports`` contexts with
        ``ports_per_project >= ceil(concurrency / projects)``.

        :param remote_ip: destination IP for mirrored traffic
        :param mirror_type: GRE or ERSPANv1 encapsulation
        :param mirror_directions: traffic directions to mirror (IN, OUT)
        :param tap_mirror_create_args: optional description on create
        :param tap_mirror_update_args: optional description on update
        """
        tap_mirror_create_args = tap_mirror_create_args or {}
        tap_mirror_update_args = tap_mirror_update_args or {}
        mirror_type = self._mirror_type(mirror_type)
        directions = self._allocate_directions(mirror_directions, mirror_type)

        ports = self.context["tenant"]["ports"]
        port = ports[self.context["iteration"] % len(ports)]

        tap_mirror = self._clients.neutron.create_tap_mirror(
            port_id=port["id"],
            directions=directions,
            remote_ip=remote_ip,
            mirror_type=mirror_type,
            description=tap_mirror_create_args.get("description"),
        )
        self._clients.neutron.update_tap_mirror(
            tap_mirror.id,
            name=self.generate_random_name(),
            description=tap_mirror_update_args.get("description"),
        )
