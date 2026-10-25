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

"""Create keystone users and store a Rally env spec that uses them."""

import argparse
import copy
import json
import typing as t
import uuid

from rally import api
from rally import plugins
from rally.env import env_mgr

from rally_openstack.common import consts
from rally_openstack.common import credential


def fetch_parent_env_and_admin_creds(
    env_name: str,
) -> tuple[dict[str, t.Any], credential.OpenStackCredential]:
    """Fetch parent environment spec and openstack admin creds from it."""

    env_data = env_mgr.EnvManager.get(env_name).data

    openstack_platform = env_data["platforms"]["openstack"]
    admin_creds = credential.OpenStackCredential(
        permission=consts.EndpointPermission.ADMIN,
        **openstack_platform["platform_data"]["admin"])

    return env_data["spec"], admin_creds


def create_projects_and_users(
    admin_creds: credential.OpenStackCredential,
    projects_count: int,
    users_per_project: int,
) -> list[dict[str, str]]:
    """Create new projects and users via 'users@openstack' context.

    :param admin_creds: admin credentials to use for creating new entities
    :param projects_count: The number of keystone projects to create.
    :param users_per_project: The number of keystone users to create per one
        keystone project.
    """

    # it should be imported after calling rally.api.API that setups oslo_config
    from rally_openstack.task.contexts.keystone import users as users_ctx

    ctx: dict[str, t.Any] = {
        "env": {
            "platforms": {
                "openstack": {
                    "admin": admin_creds.to_dict(),
                    "users": []
                }
            }
        },
        "task": {
            "uuid": str(uuid.uuid4())
        },
        "config": {
            "users@openstack": {
                "tenants": projects_count,
                "users_per_tenant": users_per_project
            }
        }
    }

    users_ctx.UserGenerator(ctx).setup()

    users = []
    for user in ctx["users"]:
        users.append({
            "username": user["credential"]["username"],
            "password": user["credential"]["password"],
            "project_name": user["credential"]["tenant_name"]
        })

        for optional in ("domain_name",
                         "user_domain_name",
                         "project_domain_name"):
            if user["credential"][optional]:
                users[-1][optional] = user["credential"][optional]

    return users


def store_a_new_spec(
    original_spec: dict[str, t.Any],
    users: list[dict[str, str]],
    path_for_new_spec: str,
) -> None:
    new_spec = copy.deepcopy(original_spec)
    del new_spec["existing@openstack"]["admin"]
    new_spec["existing@openstack"]["users"] = users
    with open(path_for_new_spec, "w") as f:
        f.write(json.dumps(new_spec, indent=4))


@plugins.ensure_plugins_are_loaded
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects-count", type=int, default=1)
    parser.add_argument("--users-per-project", type=int, default=1)
    parser.add_argument("--parent-env-name", required=True)
    parser.add_argument("--path-for-new-spec", required=True)
    args = parser.parse_args()

    # init Rally API as it makes all work for logging and config initialization
    api.API()

    original_spec, admin_creds = fetch_parent_env_and_admin_creds(
        args.parent_env_name
    )

    users = create_projects_and_users(
        admin_creds,
        projects_count=args.projects_count,
        users_per_project=args.users_per_project
    )

    store_a_new_spec(original_spec, users, args.path_for_new_spec)


if __name__ == "__main__":
    main()
