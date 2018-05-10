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

import copy
import operator
import re
import traceback

from rally.common import logging
from rally.common.plugin import plugin
from rally import exceptions
from rally.task import types

import rally_openstack
from rally_openstack import osclients
from rally_openstack.services.image import image
from rally_openstack.services.storage import block


LOG = logging.getLogger(__name__)


configure = plugin.configure


class OpenStackResourceType(types.ResourceType):
    """A base class for OpenStack ResourceTypes plugins with help-methods"""

    def __init__(self, context=None, cache=None):
        if rally_openstack.__rally_version__ >= (0, 12):
            super(OpenStackResourceType, self).__init__(context, cache)
        else:
            super(OpenStackResourceType, self).__init__()
            self._context = context or {}
            self._global_cache = cache or {}
            self._global_cache.setdefault(self.get_name(), {})
            self._cache = self._global_cache[self.get_name()]

        self._clients = None
        if self._context.get("admin"):
            self._clients = osclients.Clients(
                self._context["admin"]["credential"])
        elif self._context.get("users"):
            self._clients = osclients.Clients(
                self._context["users"][0]["credential"])

    def _find_resource(self, resource_spec, resources):
        """Return the resource whose name matches the pattern.

        .. note:: This method is a modified version of
            `rally.task.types.obj_from_name`. The difference is supporting the
            case of returning the latest version of resource in case of
            `accurate=False` option.

        :param resource_spec: resource specification to find.
            Expected keys:

            * name - The exact name of resource to search. If no exact match
              and value of *accurate* key is False (default behaviour), name
              will be interpreted as a regexp
            * regexp - a regexp of resource name to match. If several resources
              match and value of *accurate* key is False (default behaviour),
              the latest resource will be returned.
        :param resources: iterable containing all resources
        :raises InvalidScenarioArgument: if the pattern does
            not match anything.

        :returns: resource object mapped to `name` or `regex`
        """
        if "name" in resource_spec:
            # In a case of pattern string exactly matches resource name
            matching_exact = [resource for resource in resources
                              if resource.name == resource_spec["name"]]
            if len(matching_exact) == 1:
                return matching_exact[0]
            elif len(matching_exact) > 1:
                raise exceptions.InvalidScenarioArgument(
                    "%(typename)s with name '%(pattern)s' "
                    "is ambiguous, possible matches "
                    "by id: %(ids)s" % {
                        "typename": self.get_name().title(),
                        "pattern": resource_spec["name"],
                        "ids": ", ".join(map(operator.attrgetter("id"),
                                             matching_exact))})
            if resource_spec.get("accurate", False):
                raise exceptions.InvalidScenarioArgument(
                    "%(typename)s with name '%(name)s' not found" % {
                        "typename": self.get_name().title(),
                        "name": resource_spec["name"]})
            # Else look up as regex
            patternstr = resource_spec["name"]
        elif "regex" in resource_spec:
            patternstr = resource_spec["regex"]
        else:
            raise exceptions.InvalidScenarioArgument(
                "%(typename)s 'id', 'name', or 'regex' not found "
                "in '%(resource_spec)s' " % {
                    "typename": self.get_name().title(),
                    "resource_spec": resource_spec})

        pattern = re.compile(patternstr)
        matching = [resource for resource in resources
                    if re.search(pattern, resource.name or "")]
        if not matching:
            raise exceptions.InvalidScenarioArgument(
                "%(typename)s with pattern '%(pattern)s' not found" % {
                    "typename": self.get_name().title(),
                    "pattern": pattern.pattern})
        elif len(matching) > 1:
            if not resource_spec.get("accurate", False):
                return sorted(matching, key=lambda o: o.name or "")[-1]

            raise exceptions.InvalidScenarioArgument(
                "%(typename)s with name '%(pattern)s' is ambiguous, possible "
                "matches by id: %(ids)s" % {
                    "typename": self.get_name().title(),
                    "pattern": pattern.pattern,
                    "ids": ", ".join(map(operator.attrgetter("id"),
                                         matching))})
        return matching[0]

    if rally_openstack.__rally_version__ < (0, 12):
        @classmethod
        def _get_doc(cls):
            return cls.__doc__


class DeprecatedBehaviourMixin(object):
    """A Mixin class which returns deprecated `transform` method."""

    @classmethod
    def transform(cls, clients, resource_config):
        caller = traceback.format_stack(limit=2)[0]
        if rally_openstack.__rally_version__ >= (0, 12):
            # The new interface of ResourceClass is introduced with Rally 0.12
            LOG.warning("Calling method `transform` of %s is deprecated:\n%s"
                        % (cls.__name__, caller))
        if clients:
            # it doesn't matter "permission" of the user. it will pick the
            # first one
            context = {"admin": {"credential": clients.credential}}
        else:
            context = {}
        self = cls(context, cache={})
        return self.pre_process(resource_spec=resource_config, config={})


@plugin.configure(name="nova_flavor")
class Flavor(DeprecatedBehaviourMixin, OpenStackResourceType):
    """Find Nova's flavor ID by name or regexp."""

    def pre_process(self, resource_spec, config):
        resource_id = resource_spec.get("id")
        if not resource_id:
            novaclient = self._clients.nova()
            resource_id = types._id_from_name(
                resource_config=resource_spec,
                resources=novaclient.flavors.list(),
                typename="flavor")
        return resource_id


@plugin.configure(name="ec2_flavor")
class EC2Flavor(DeprecatedBehaviourMixin, OpenStackResourceType):
    """Find Nova's flavor Name by it's ID or regexp."""

    def pre_process(self, resource_spec, config):
        resource_name = resource_spec.get("name")
        if not resource_name:
            # NOTE(wtakase): gets resource name from OpenStack id
            novaclient = self._clients.nova()
            resource_name = types._name_from_id(
                resource_config=resource_spec,
                resources=novaclient.flavors.list(),
                typename="flavor")
        return resource_name


@plugin.configure(name="glance_image")
class GlanceImage(DeprecatedBehaviourMixin, OpenStackResourceType):
    """Find Glance's image ID by name or regexp."""

    def pre_process(self, resource_spec, config):
        resource_id = resource_spec.get("id")
        list_kwargs = resource_spec.get("list_kwargs", {})

        if not resource_id:
            cache_id = hash(frozenset(list_kwargs.items()))
            if cache_id not in self._cache:
                glance = image.Image(self._clients)
                self._cache[cache_id] = glance.list_images(**list_kwargs)
            images = self._cache[cache_id]
            resource = self._find_resource(resource_spec, images)
            return resource.id
        return resource_id


@plugin.configure(name="glance_image_args")
class GlanceImageArguments(DeprecatedBehaviourMixin, OpenStackResourceType):
    """Process Glance image create options to look similar in case of V1/V2."""
    def pre_process(self, resource_spec, config):
        resource_spec = copy.deepcopy(resource_spec)
        if "is_public" in resource_spec:
            if "visibility" in resource_spec:
                resource_spec.pop("is_public")
            else:
                visibility = ("public" if resource_spec.pop("is_public")
                              else "private")
                resource_spec["visibility"] = visibility
        return resource_spec


@plugin.configure(name="ec2_image")
class EC2Image(DeprecatedBehaviourMixin, OpenStackResourceType):
    """Find EC2 image ID."""

    def pre_process(self, resource_spec, config):
        if "name" not in resource_spec and "regex" not in resource_spec:
            # NOTE(wtakase): gets resource name from OpenStack id
            glanceclient = self._clients.glance()
            resource_name = types._name_from_id(
                resource_config=resource_spec,
                resources=list(glanceclient.images.list()),
                typename="image")
            resource_spec["name"] = resource_name

        # NOTE(wtakase): gets EC2 resource id from name or regex
        ec2client = self._clients.ec2()
        resource_ec2_id = types._id_from_name(
            resource_config=resource_spec,
            resources=list(ec2client.get_all_images()),
            typename="ec2_image")
        return resource_ec2_id


@plugin.configure(name="cinder_volume_type")
class VolumeType(DeprecatedBehaviourMixin, OpenStackResourceType):
    """Find Cinder volume type ID by name or regexp."""

    def pre_process(self, resource_spec, config):
        resource_id = resource_spec.get("id")
        if not resource_id:
            cinder = block.BlockStorage(self._clients)
            resource_id = types._id_from_name(
                resource_config=resource_spec,
                resources=cinder.list_types(),
                typename="volume_type")
        return resource_id


@plugin.configure(name="neutron_network")
class NeutronNetwork(DeprecatedBehaviourMixin, OpenStackResourceType):
    """Find Neutron network ID by it's name."""
    def pre_process(self, resource_spec, config):
        resource_id = resource_spec.get("id")
        if resource_id:
            return resource_id
        else:
            neutronclient = self._clients.neutron()
            for net in neutronclient.list_networks()["networks"]:
                if net["name"] == resource_spec.get("name"):
                    return net["id"]

        raise exceptions.InvalidScenarioArgument(
            "Neutron network with name '{name}' not found".format(
                name=resource_spec.get("name")))


@plugin.configure(name="watcher_strategy")
class WatcherStrategy(DeprecatedBehaviourMixin, OpenStackResourceType):
    """Find Watcher strategy ID by it's name."""

    def pre_process(self, resource_spec, config):
        resource_id = resource_spec.get("id")
        if not resource_id:
            watcherclient = self._clients.watcher()
            resource_id = types._id_from_name(
                resource_config=resource_spec,
                resources=[watcherclient.strategy.get(
                    resource_spec.get("name"))],
                typename="strategy",
                id_attr="uuid")
        return resource_id


@plugin.configure(name="watcher_goal")
class WatcherGoal(DeprecatedBehaviourMixin, OpenStackResourceType):
    """Find Watcher goal ID by it's name."""

    def pre_process(self, resource_spec, config):
        resource_id = resource_spec.get("id")
        if not resource_id:
            watcherclient = self._clients.watcher()
            resource_id = types._id_from_name(
                resource_config=resource_spec,
                resources=[watcherclient.goal.get(resource_spec.get("name"))],
                typename="goal",
                id_attr="uuid")
        return resource_id
