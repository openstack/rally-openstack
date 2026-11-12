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

from rally import exceptions
from rally.common import logging
from rally.task import scenario

from rally_openstack.common import consts
from rally_openstack.common import credential
from rally_openstack.common import osclients
from rally_openstack.task import context


LOG = logging.getLogger(__name__)


@context.configure(name="clients_prefetch", platform="openstack", order=160,
                   hidden=True)
class ClientsPrefetch(context.OpenStackContext):
    """Prefetch once what the scenario's clients fetch on their first call.

    Only openstacksdk-backed clients are covered.
    """

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "additionalProperties": False,
    }

    def setup(self) -> None:
        # discovery may reach a service with the token of the credential (a
        # 401 on an unauthenticated version request is retried with it), and
        # the service caches that token's roles. Contexts running later (e.g.
        # roles) change the roles of the users, not of the admin, so the
        # admin is the one to use.
        cred: credential.OpenStackCredential | None = (
            self.context.get("admin", {}).get("credential"))
        if cred is None and self.context.get("users"):
            cred = self.context["users"][0]["credential"]
        if cred is None:
            return

        scenario_name: str | None = self.context.get("scenario_name")
        if not scenario_name:
            return
        try:
            scenario_cls = scenario.Scenario.get(scenario_name)
        except exceptions.PluginNotFound:
            return

        # ok, we can continue
        clients = osclients.Clients(cred)
        processed: set[str] = set()
        for name, _args, kwargs in scenario_cls._meta_get("validators"):
            if name != "required_services":
                continue
            services: list[str] = kwargs.get("services", [])
            if not isinstance(services, (list, tuple)):
                services = [services]
            for service in services:
                if service in processed:
                    continue

                # the users context gives every credential the same cloud
                # state, so loading it through one of them is enough
                try:
                    client: osclients.BaseClient = getattr(clients, service)
                    client.load_service_info()
                except Exception:
                    LOG.debug(
                        f"Failed to prefetch {service} service info; it "
                        f"will be resolved lazily per worker instead.",
                        exc_info=True,
                    )
                processed.add(service)

    def cleanup(self) -> None:  # pragma: no cover
        pass
