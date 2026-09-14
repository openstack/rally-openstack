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

import copy
import typing as t

import typing_extensions as te

from rally import exceptions
from rally.common import logging
from rally.common.plugin import plugin
from rally.task import scenario
from rally.task import types
from rally.utils import typeutils

from rally_openstack.common import osclients
from rally_openstack.common.clients import glance
from rally_openstack.common.services.storage import block


LOG = logging.getLogger(__name__)


configure = plugin.configure


class IDSpec(te.TypedDict, closed=True):
    """Specification of a resource to search by its id."""

    id: t.Annotated[
        str, typeutils.Field(description="the id of an existing resource")]


class NameSpec(te.TypedDict, closed=True):
    """Specification of a resource to search by its exact name."""

    name: t.Annotated[
        str, typeutils.Field(description="the exact name of a resource")]


class RegexSpec(te.TypedDict, closed=True):
    """Specification of a resource to search by a regex of its name."""

    regex: t.Annotated[
        str,
        typeutils.Field(description="a regex to match a resource name with")]


class _GlanceImageFiltersSpec(te.TypedDict):
    """Filters shared by every Glance image lookup specification."""

    accurate: te.NotRequired[t.Annotated[
        bool,
        typeutils.Field(
            description="fail instead of picking the latest match when "
                        "several images match")]]
    status: te.NotRequired[t.Annotated[
        glance.ImageStatus | None,
        typeutils.Field(
            description="only consider images in this status. Defaults to "
                        "'active'; null considers any of them")]]
    visibility: te.NotRequired[t.Annotated[
        glance.Visibility,
        typeutils.Field(
            description="only consider images with this visibility")]]
    owner: te.NotRequired[t.Annotated[
        str,
        typeutils.Field(
            description="only consider images owned by this project id")]]
    list_kwargs: te.NotRequired[t.Annotated[
        dict[str, t.Any],
        typeutils.Field(
            description="DEPRECATED. The former home of 'status', "
                        "'visibility' and 'owner'. Set them directly "
                        "instead")]]


class GlanceImageNameSpec(_GlanceImageFiltersSpec, closed=True):
    """Specification of a Glance image to search by its name."""

    name: t.Annotated[
        str,
        typeutils.Field(
            description="the exact name of an image. If nothing matches it "
                        "exactly, it is retried as a regex")]


class GlanceImageRegexSpec(_GlanceImageFiltersSpec, closed=True):
    """Specification of a Glance image to search by a regex of its name."""

    regex: t.Annotated[
        str,
        typeutils.Field(description="a regex to match an image name with")]


class GlanceImageArgsSpec(t.TypedDict, total=False):
    """Arguments of an image creation call.

    Only the keys that differ between Glance V1 and V2 are listed here, any
    other key is passed through as is.
    """

    is_public: t.Annotated[
        bool,
        typeutils.Field(
            description="the V1 way to make an image public. It is translated "
                        "into the V2 'visibility' key")]
    visibility: t.Annotated[
        str,
        typeutils.Field(
            description="the access permission for the created image")]


class OpenStackResourceType(types.ResourceType):
    """A base class for OpenStack ResourceTypes plugins with help-methods"""

    _clients: osclients.Clients

    def __init__(
        self,
        context: dict[str, t.Any],
        cache: dict[str, t.Any] | None = None,
        *,
        scenario_cls: type[scenario.Scenario],
    ) -> None:
        """Initialize the pre-processor.

        :param context: the workload context
        :param cache: the cache shared by resource types of the workload
        :param scenario_cls: the scenario plugin that owns the argument
        """
        super().__init__(
            context=context, cache=cache, scenario_cls=scenario_cls)

        if self._context.get("admin"):
            self._clients = osclients.Clients(
                self._context["admin"]["credential"])
        elif self._context.get("users"):
            self._clients = osclients.Clients(
                self._context["users"][0]["credential"])


@plugin.configure(name="nova_flavor")
class Flavor(OpenStackResourceType):
    """Find Nova's flavor ID by name or regexp."""

    def pre_process(
        self,
        *,
        resource_spec: IDSpec | NameSpec | RegexSpec,
        config: types.ConvertConfig,
        output_type: t.Any,
    ) -> str:
        """Return the id of the flavor described by the specification."""
        if "id" in resource_spec:
            return resource_spec["id"]

        novaclient = self._clients.nova()
        return types._id_from_name(
            resource_config=dict(resource_spec),
            resources=novaclient.flavors.list(),
            typename="flavor")


@plugin.configure(name="glance_image")
class GlanceImage(OpenStackResourceType):
    """Find Glance's image ID by name or regexp."""

    def pre_process(
        self,
        *,
        resource_spec: IDSpec | GlanceImageNameSpec | GlanceImageRegexSpec,
        config: types.ConvertConfig,
        output_type: t.Any,
    ) -> str:
        """Return the id of the image described by the specification."""
        if "id" in resource_spec:
            return resource_spec["id"]

        filters: dict[str, t.Any] = dict(resource_spec)
        list_kwargs = filters.pop("list_kwargs", None)
        if list_kwargs:
            LOG.warning(
                "The 'list_kwargs' key of the 'glance_image' resource type is "
                "deprecated and will be removed. Set the filters it carries "
                "('status', 'visibility', 'owner') directly in specific "
                "arg level."
            )
            for key in ("status", "visibility", "owner"):
                if key in list_kwargs:
                    filters.setdefault(key, list_kwargs[key])

            if "is_public" in list_kwargs and "visibility" not in filters:
                filters.setdefault(
                    "visibility",
                    glance.Visibility.PUBLIC
                    if list_kwargs["is_public"]
                    else glance.Visibility.PRIVATE,
                )

        # the cache is shared with the other resource types of the workload
        key = ("glance_image", tuple(sorted(filters.items())))
        if key not in self._cache:
            try:
                image = self._clients.glance.find_image(**filters)
            except exceptions.GetResourceFailure as e:
                # what the client reports as a failed lookup is, from here, a
                # scenario argument that does not describe an usable image
                raise exceptions.InvalidScenarioArgument(
                    e.format_message()) from e
            self._cache[key] = image.id
        return t.cast("str", self._cache[key])


@plugin.configure(name="glance_image_args")
class GlanceImageArguments(OpenStackResourceType):
    """Process Glance image create options to look similar in case of V1/V2."""

    def pre_process(
        self,
        *,
        resource_spec: GlanceImageArgsSpec,
        config: types.ConvertConfig,
        output_type: t.Any,
    ) -> dict[str, t.Any]:
        """Return the image creation arguments in their V2 form."""
        resource_spec = copy.deepcopy(resource_spec)
        if "is_public" in resource_spec:
            if "visibility" in resource_spec:
                resource_spec.pop("is_public")
            else:
                visibility = ("public" if resource_spec.pop("is_public")
                              else "private")
                resource_spec["visibility"] = visibility
        return dict(resource_spec)


@plugin.configure(name="ec2_image")
class EC2Image(OpenStackResourceType):
    """Find EC2 image ID."""

    def pre_process(
        self,
        *,
        resource_spec: IDSpec | NameSpec | RegexSpec,
        config: types.ConvertConfig,
        output_type: t.Any,
    ) -> str:
        """Return the EC2 id of the image described by the specification."""
        lookup: dict[str, t.Any] = dict(resource_spec)
        if "id" in resource_spec:
            # NOTE(wtakase): gets resource name from OpenStack id
            lookup = {
                "name": types._name_from_id(
                    resource_config=lookup,
                    resources=self._clients.glance.list_images(
                        status=None),
                    typename="image")
            }

        # NOTE(wtakase): gets EC2 resource id from name or regex
        ec2client = self._clients.ec2()
        resource_ec2_id = types._id_from_name(
            resource_config=lookup,
            resources=list(ec2client.get_all_images()),
            typename="ec2_image")
        return resource_ec2_id


@plugin.configure(name="cinder_volume_type")
class VolumeType(OpenStackResourceType):
    """Find Cinder volume type ID by name or regexp."""

    def pre_process(
        self,
        *,
        resource_spec: IDSpec | NameSpec | RegexSpec,
        config: types.ConvertConfig,
        output_type: t.Any,
    ) -> str:
        """Return the id of the volume type described by the spec."""
        if "id" in resource_spec:
            return resource_spec["id"]

        cinder = block.BlockStorage(self._clients)
        return types._id_from_name(
            resource_config=dict(resource_spec),
            resources=cinder.list_types(),
            typename="volume_type")


@plugin.configure(name="neutron_network")
class NeutronNetwork(OpenStackResourceType):
    """Find Neutron network ID by it's name."""

    def pre_process(
        self,
        *,
        resource_spec: IDSpec | NameSpec,
        config: types.ConvertConfig,
        output_type: t.Any,
    ) -> str:
        """Return the id of the network described by the specification."""
        if "id" in resource_spec:
            return resource_spec["id"]

        name = resource_spec["name"]
        neutronclient = self._clients.neutron()
        for net in neutronclient.list_networks()["networks"]:
            if net["name"] == name:
                return net["id"]

        raise exceptions.InvalidScenarioArgument(
            f"Neutron network with name '{name}' not found")


@plugin.configure(name="watcher_strategy")
class WatcherStrategy(OpenStackResourceType):
    """Find Watcher strategy ID by it's name."""

    def pre_process(
        self,
        *,
        resource_spec: IDSpec | NameSpec,
        config: types.ConvertConfig,
        output_type: t.Any,
    ) -> str:
        """Return the uuid of the strategy described by the spec."""
        if "id" in resource_spec:
            return resource_spec["id"]

        watcherclient = self._clients.watcher()
        return types._id_from_name(
            resource_config=dict(resource_spec),
            resources=[watcherclient.strategy.get(resource_spec["name"])],
            typename="strategy",
            id_attr="uuid")


@plugin.configure(name="watcher_goal")
class WatcherGoal(OpenStackResourceType):
    """Find Watcher goal ID by it's name."""

    def pre_process(
        self,
        *,
        resource_spec: IDSpec | NameSpec,
        config: types.ConvertConfig,
        output_type: t.Any,
    ) -> str:
        """Return the uuid of the goal described by the specification."""
        if "id" in resource_spec:
            return resource_spec["id"]

        watcherclient = self._clients.watcher()
        return types._id_from_name(
            resource_config=dict(resource_spec),
            resources=[watcherclient.goal.get(resource_spec["name"])],
            typename="goal",
            id_attr="uuid")
