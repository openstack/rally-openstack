# Copyright 2014: Mirantis Inc.
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

from rally.common import cfg
from rally.task import utils

import typing as t

if t.TYPE_CHECKING:  # pragma: no cover
    R = t.TypeVar("R", bound="ResourceManager")

CONF = cfg.CONF

cleanup_group = cfg.OptGroup(name="cleanup", title="Cleanup Options")


# NOTE(andreykurilin): There are cases when there is no way to use any kind
#   of "name" for resource as an identifier of alignment resource to the
#   particular task run and even to Rally itself. Previously, we used empty
#   strings as a workaround for name matching specific templates, but
#   theoretically such behaviour can hide other cases when resource should have
#   a name property, but it is missed.
#   Let's use instances of specific class to return as a name of resources
#   which do not have names at all.
class NoName(object):
    def __init__(self, resource_type):
        self.resource_type = resource_type

    def __repr__(self):
        return "<NoName %s resource>" % self.resource_type


def resource(
    service: str,
    resource: str,
    order: int = 0,
    admin_required: bool = False,
    perform_for_admin_only: bool = False,
    tenant_resource: bool = False,
    max_attempts: int = 3,
    timeout: float = CONF.openstack.resource_deletion_timeout,
    interval: int = 1,
    threads: int = CONF.openstack.cleanup_threads
) -> t.Callable[[type[R]], type[R]]:
    """Decorator that overrides resource specification.

    Just put it on top of your resource class and specify arguments that you
    need.

    :param service: It is equal to client name for corresponding service.
                    E.g. "nova", "cinder" or "zaqar"
    :param resource: Client manager name for resource. E.g. in case of
                     nova.servers you should write here "servers"
    :param order: Used to adjust priority of cleanup for different resource
                  types
    :param admin_required: Admin user is required
    :param perform_for_admin_only: Perform cleanup for admin user only
    :param tenant_resource: Perform deletion only 1 time per tenant
    :param max_attempts: Max amount of attempts to delete single resource
    :param timeout: Max duration of deletion in seconds
    :param interval: Resource status pooling interval
    :param threads: Amount of threads (workers) that are deleting resources
                    simultaneously
    """

    def inner(cls: type[R]) -> type[R]:
        # TODO(boris-42): This can be written better I believe =)
        cls._service = service
        cls._resource = resource
        cls._order = order
        cls._admin_required = admin_required
        cls._perform_for_admin_only = perform_for_admin_only
        cls._max_attempts = max_attempts
        cls._timeout = timeout
        cls._interval = interval
        cls._threads = threads
        cls._tenant_resource = tenant_resource

        return cls

    return inner


@resource(service="", resource="")
class ResourceManager(object):
    """Base class for cleanup plugins for specific resources.

    You should use @resource decorator to specify major configuration of
    resource manager. Usually you should specify: service, resource and order.

    If project python client is very specific, you can override delete(),
    list() and is_deleted() methods to make them fit to your case.
    """

    _service: str
    _resource: str
    _order: int
    _admin_required: bool
    _perform_for_admin_only: bool
    _tenant_resource: bool
    _max_attempts: int
    _timeout: float
    _interval: int
    _threads: int

    def __init__(self, resource=None, admin=None, user=None, tenant_uuid=None):
        self.admin = admin
        self.user = user
        self.raw_resource = resource
        self.tenant_uuid = tenant_uuid

    def _manager(self):
        client = self._admin_required and self.admin or self.user
        return getattr(getattr(client, self._service)(), self._resource)

    def id(self):
        """Returns id of resource."""
        return self.raw_resource.id

    def name(self):
        """Returns name of resource."""
        return self.raw_resource.name

    def is_deleted(self):
        """Checks if the resource is deleted.

        Fetch resource by id from service and check it status.
        In case of NotFound or status is DELETED or DELETE_COMPLETE returns
        True, otherwise False.
        """
        try:
            resource = self._manager().get(self.id())
        except Exception as e:
            return getattr(e, "code", getattr(e, "http_status", 400)) == 404

        return utils.get_status(resource) in ("DELETED", "DELETE_COMPLETE")

    def delete(self):
        """Delete resource that corresponds to instance of this class."""
        self._manager().delete(self.id())

    def list(self):
        """List all resources specific for admin or user."""
        return self._manager().list()
