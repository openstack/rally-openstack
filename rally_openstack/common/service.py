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

import typing as t

from rally.task import service as base_service


if t.TYPE_CHECKING:
    from rally.task import atomic

    from rally_openstack.common import osclients


service = base_service.service
compat_layer = base_service.compat_layer
should_be_overridden = base_service.should_be_overridden

if t.TYPE_CHECKING:

    class Service(base_service.Service):
        """A typed view of rally's Service base class.

        ``rally.task.service.Service.__init__`` is not annotated, so its
        parameters and the attributes it assigns are all inferred as ``Any``.
        That silently disables type checking for every service in this tree:
        ``self._clients`` is ``Any``, so ``self._clients.<anything>`` is too.

        This subclass exists only for the type checker -- at runtime
        ``Service`` is rally's own class, untouched (see the ``else`` branch
        below). It re-declares the constructor and the attributes it sets with
        the types rally-openstack actually passes, and adds nothing else.
        """

        #: the per-service client container the service works through
        _clients: osclients.Clients
        #: usually the ``generate_random_name`` of the owning scenario/context
        _name_generator: t.Callable[[], str] | None
        #: the sink atomic actions are recorded into
        _atomic_actions: list[atomic.AtomicAction]
        #: major API version declared by the ``@service`` decorator
        version: str | None

        def __init__(
            self,
            clients: osclients.Clients,
            name_generator: t.Callable[[], str] | None = None,
            atomic_inst: list[atomic.AtomicAction] | None = None,
        ) -> None: ...

else:
    Service = base_service.Service
