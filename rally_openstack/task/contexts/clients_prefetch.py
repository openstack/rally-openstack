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
        # collect all data required to proceed
        credentials: list[credential.OpenStackCredential] = [
            u["credential"] for u in self.context.get("users", [])
        ]
        admin_cred = self.context.get("admin", {}).get("credential")
        if admin_cred:
            # discovery may reach a service with the token of the first
            # credential (a 401 on an unauthenticated version request is
            # retried with it), and the service caches that token's roles.
            # Contexts running later (e.g. roles) change the roles of the
            # users, not of the admin, so the admin is the one to use.
            credentials.insert(0, admin_cred)
        if not credentials:
            return

        scenario_name: str | None = self.context.get("scenario_name")
        if not scenario_name:
            return
        try:
            scenario_cls = scenario.Scenario.get(scenario_name)
        except exceptions.PluginNotFound:
            return

        # ok, we can continue
        clients = osclients.Clients(credentials[0])
        processed: set[str] = set()
        for name, _args, kwargs in scenario_cls._meta_get("validators"):
            if name != "required_services":
                continue
            services = kwargs.get("services", [])
            if not isinstance(services, (list, tuple)):
                services = [services]
            for service in services:
                try:
                    client_cls = osclients.BaseClient.get(service)
                except exceptions.PluginNotFound:
                    continue
                # a legacy wrapper builds its native client to check the
                # service, and that client does not read the discovery cache
                if issubclass(client_cls, osclients.OSClient):
                    continue
                sdk_type = client_cls.spec.sdk_service_type
                if not sdk_type or sdk_type in processed:
                    continue

                try:
                    getattr(clients, service).check_availability()
                except Exception:
                    LOG.debug(
                        f"Failed to prefetch {sdk_type} version "
                        f"discovery; it will be resolved lazily per worker "
                        f"instead.",
                        exc_info=True,
                    )
                processed.add(sdk_type)

        discovered = credentials[0].discovery_cache
        for cred in credentials[1:]:
            cred.discovery_cache.update(discovered)

    def cleanup(self) -> None:  # pragma: no cover
        pass
