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

import time
import typing as t

from rally.common import broker
from rally.common import logging
from rally.common.plugin import discover
from rally.common.plugin import plugin
from rally.common import utils as rutils
from rally_openstack.task.cleanup import base


LOG = logging.getLogger(__name__)


class SeekAndDestroy(object):

    def __init__(self, manager_cls, admin, users,
                 resource_classes=None, task_id=None):
        """Resource deletion class.

        This class contains method exterminate() that finds and deletes
        all resources created by Rally.

        :param manager_cls: subclass of base.ResourceManager
        :param admin: admin credential like in context["admin"]
        :param users: users credentials like in context["users"]
        :param resource_classes: Resource classes to match resource names
                                 against
        :param task_id: The UUID of task to match resource names against
        """
        self.manager_cls = manager_cls
        self.admin = admin
        self.users = users or []
        self.resource_classes = resource_classes or [
            rutils.RandomNameGeneratorMixin]
        self.task_id = task_id

    def _get_cached_client(self, user):
        """Simplifies initialization and caching OpenStack clients."""
        if not user:
            return None
        # NOTE(astudenov): Credential now supports caching by default
        return user["credential"].clients()

    def _delete_single_resource(self, resource):
        """Safe resource deletion with retries and timeouts.

        Send request to delete resource, in case of failures repeat it few
        times. After that pull status of resource until it's deleted.

        Writes in LOG warning with UUID of resource that wasn't deleted

        :param resource: instance of resource manager initiated with resource
                         that should be deleted.
        """

        msg_kw = {
            "uuid": resource.id(),
            "name": resource.name() or "",
            "service": resource._service,
            "resource": resource._resource
        }

        LOG.debug(
            "Deleting %(service)s.%(resource)s object %(name)s (%(uuid)s)"
            % msg_kw)

        try:
            rutils.retry(resource._max_attempts, resource.delete)
        except Exception as e:
            msg = ("Resource deletion failed, max retries exceeded for "
                   "%(service)s.%(resource)s: %(uuid)s.") % msg_kw

            if logging.is_debug():
                LOG.exception(msg)
            else:
                LOG.warning("%(msg)s Reason: %(e)s" % {"msg": msg, "e": e})
        else:
            started = time.time()
            failures_count = 0
            while time.time() - started < resource._timeout:
                try:
                    if resource.is_deleted():
                        return
                except Exception:
                    LOG.exception(
                        "Seems like %s.%s.is_deleted(self) method is broken "
                        "It shouldn't raise any exceptions."
                        % (resource.__module__, type(resource).__name__))

                    # NOTE(boris-42): Avoid LOG spamming in case of bad
                    #                 is_deleted() method
                    failures_count += 1
                    if failures_count > resource._max_attempts:
                        break

                finally:
                    rutils.interruptable_sleep(resource._interval)

            LOG.warning("Resource deletion failed, timeout occurred for "
                        "%(service)s.%(resource)s: %(uuid)s." % msg_kw)

    def _publisher(self, queue):
        """Publisher for deletion jobs.

        This method iterates over all users, lists all resources
        (using manager_cls) and puts jobs for deletion.

        Every deletion job contains tuple with two values: user and resource
        uuid that should be deleted.

        In case of tenant based resource, uuids are fetched only from one user
        per tenant.
        """
        def _publish(admin, user, manager):
            try:
                for raw_resource in rutils.retry(3, manager.list):
                    queue.append((admin, user, raw_resource))
            except Exception:
                LOG.exception(
                    "Seems like %s.%s.list(self) method is broken. "
                    "It shouldn't raise any exceptions."
                    % (manager.__module__, type(manager).__name__))

        if self.admin and (not self.users
                           or self.manager_cls._perform_for_admin_only):
            manager = self.manager_cls(
                admin=self._get_cached_client(self.admin))
            _publish(self.admin, None, manager)

        else:
            visited_tenants = set()
            admin_client = self._get_cached_client(self.admin)
            for user in self.users:
                if (self.manager_cls._tenant_resource
                   and user["tenant_id"] in visited_tenants):
                    continue

                visited_tenants.add(user["tenant_id"])
                manager = self.manager_cls(
                    admin=admin_client,
                    user=self._get_cached_client(user),
                    tenant_uuid=user["tenant_id"])
                _publish(self.admin, user, manager)

    def _consumer(self, cache, args):
        """Method that consumes single deletion job."""
        admin, user, raw_resource = args

        manager = self.manager_cls(
            resource=raw_resource,
            admin=self._get_cached_client(admin),
            user=self._get_cached_client(user),
            tenant_uuid=user and user["tenant_id"])

        if (isinstance(manager.name(), base.NoName)
                or rutils.name_matches_object(
                    manager.name(), *self.resource_classes,
                    task_id=self.task_id, exact=False)):
            self._delete_single_resource(manager)

    def exterminate(self):
        """Delete all resources for passed users, admin and resource_mgr."""

        broker.run(self._publisher, self._consumer,
                   consumers_count=self.manager_cls._threads)


def list_resource_names(admin_required=None):
    """List all resource managers names.

    Returns all service names and all combination of service.resource names.

    :param admin_required: None -> returns all ResourceManagers
                           True -> returns only admin ResourceManagers
                           False -> returns only non admin ResourceManagers
    """
    res_mgrs: t.Iterable[type[base.ResourceManager]] = discover.itersubclasses(
        base.ResourceManager
    )
    if admin_required is not None:
        res_mgrs = filter(lambda cls: cls._admin_required == admin_required,
                          res_mgrs)

    names = set()
    for cls in res_mgrs:
        names.add(cls._service)
        names.add("%s.%s" % (cls._service, cls._resource))

    return names


def find_resource_managers(names=None, admin_required=None):
    """Returns resource managers.

    :param names: List of names in format <service> or <service>.<resource>
                  that is used for filtering resource manager classes
    :param admin_required: None -> returns all ResourceManagers
                           True -> returns only admin ResourceManagers
                           False -> returns only non admin ResourceManagers
    """
    names = set(names or [])

    resource_managers = []
    for manager in discover.itersubclasses(base.ResourceManager):
        if admin_required is not None:
            if admin_required != manager._admin_required:
                continue

        if (manager._service in names
           or "%s.%s" % (manager._service, manager._resource) in names):
            resource_managers.append(manager)

    resource_managers.sort(key=lambda x: x._order)

    found_names = set()
    for mgr in resource_managers:
        found_names.add(mgr._service)
        found_names.add("%s.%s" % (mgr._service, mgr._resource))

    missing = names - found_names
    if missing:
        LOG.warning("Missing resource managers: %s" % ", ".join(missing))

    return resource_managers


def cleanup(names=None, admin_required=None, admin=None, users=None,
            superclass=plugin.Plugin, task_id=None):
    """Generic cleaner.

    This method goes through all plugins. Filter those and left only plugins
    with _service from services or _resource from resources.

    Then goes through all passed users and using cleaners cleans all related
    resources.

    :param names: Use only resource managers that have names in this list.
                  There are in as _service or
                  (%s.%s % (_service, _resource)) from
    :param admin_required: If None -> return all plugins
                           If True -> return only admin plugins
                           If False -> return only non admin plugins
    :param admin: rally.deployment.credential.Credential that corresponds to
                  OpenStack admin.
    :param users: List of OpenStack users that was used during testing.
                  Every user has next structure:
                  {
                    "id": <uuid1>,
                    "tenant_id": <uuid2>,
                    "credential": <rally.deployment.credential.Credential>
                  }
    :param superclass: The plugin superclass to perform cleanup
                       for. E.g., this could be
                       ``rally.task.scenario.Scenario`` to cleanup all
                       Scenario resources.
    :param task_id: The UUID of task
    """
    resource_classes = [cls for cls in discover.itersubclasses(superclass)
                        if issubclass(cls, rutils.RandomNameGeneratorMixin)]
    if not resource_classes and issubclass(superclass,
                                           rutils.RandomNameGeneratorMixin):
        resource_classes.append(superclass)
    for manager in find_resource_managers(names, admin_required):
        LOG.debug("Cleaning up %(service)s %(resource)s objects"
                  % {"service": manager._service,
                     "resource": manager._resource})
        SeekAndDestroy(manager, admin, users,
                       resource_classes=resource_classes,
                       task_id=task_id).exterminate()
