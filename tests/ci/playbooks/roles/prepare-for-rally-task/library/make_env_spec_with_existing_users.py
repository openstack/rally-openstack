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
import json
import uuid

from ansible.module_utils.basic import AnsibleModule

from rally import api
from rally.env import env_mgr
from rally import plugins

from rally_openstack.common import consts
from rally_openstack.common import credential


def fetch_parent_env_and_admin_creds(env_name):
    """Fetch parent environment spec and openstack admin creds from it."""

    env_data = env_mgr.EnvManager.get(env_name).data

    openstack_platform = env_data["platforms"]["openstack"]
    admin_creds = credential.OpenStackCredential(
        permission=consts.EndpointPermission.ADMIN,
        **openstack_platform["platform_data"]["admin"])

    return env_data["spec"], admin_creds


def create_projects_and_users(admin_creds, projects_count, users_per_project):
    """Create new projects and users via 'users@openstack' context.

    :param admin_creds: admin credentials to use for creating new entities
    :param projects_count: The number of keystone projects to create.
    :param users_per_project: The number of keystone users to create per one
        keystone project.
    """

    # it should be imported after calling rally.api.API that setups oslo_config
    from rally_openstack.task.contexts.keystone import users as users_ctx

    ctx = {
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


def store_a_new_spec(original_spec, users, path_for_new_spec):
    new_spec = copy.deepcopy(original_spec)
    del new_spec["existing@openstack"]["admin"]
    new_spec["existing@openstack"]["users"] = users
    with open(path_for_new_spec, "w") as f:
        f.write(json.dumps(new_spec, indent=4))


@plugins.ensure_plugins_are_loaded
def ansible_main():
    module = AnsibleModule(argument_spec=dict(
        projects_count=dict(
            type="int",
            default=1,
            required=False
        ),
        users_per_project=dict(
            type="int",
            default=1,
            required=False
        ),
        parent_env_name=dict(
            type="str",
            required=True
        ),
        path_for_new_spec=dict(
            type="str",
            required=True
        )
    ))

    # init Rally API as it makes all work for logging and config initialization
    api.API()

    original_spec, admin_creds = fetch_parent_env_and_admin_creds(
        module.params["parent_env_name"]
    )

    users = create_projects_and_users(
        admin_creds,
        projects_count=module.params["projects_count"],
        users_per_project=module.params["users_per_project"]
    )

    store_a_new_spec(original_spec, users, module.params["path_for_new_spec"])

    module.exit_json(changed=True)


if __name__ == "__main__":
    ansible_main()
