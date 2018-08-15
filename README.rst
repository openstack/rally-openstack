===============
rally-openstack
===============

Rally plugins for `OpenStack platform <https://openstack.org>`_


Usage
-----

.. code-block:: bash

    # Install this package (will install rally if not installed)
    pip install rally-openstack

    # List all installed plugins
    rally plugin list --platform openstack

    # Create OpenStack Env

    cat <<EOT >> env.yaml
    ---
    openstack:
      auth_url: "https://keystone.net/identity"
      region_name: RegionOne
      https_insecure: False
      users:
        - username: user_that_runs_commands
          password: his password
          project_name: project_that_users_belong_to
    EOT

    rally env create --name my_openstack --spec env.yaml

    # Check that you provide correct credentials
    rally env check

    # Collect key Open Stack metrics
    rally task start ./tasks/openstack_metrics/task.yaml --task-args {"image_name": "image_to_use", "flavor_name": "flavor_to_use"}

    # Generate Report
    rally task report --out report.html


Links
----------------------

* Free software: Apache license
* Documentation: https://rally.readthedocs.org/en/latest/
* Source: https://git.openstack.org/cgit/openstack/rally-openstack
* Bugs: https://bugs.launchpad.net/rally
* Step-by-step tutorial: https://rally.readthedocs.io/en/latest/quick_start/tutorial.html
* Launchpad page: https://launchpad.net/rally
* Gitter chat: https://gitter.im/rally-dev/Lobby
* Trello board: https://trello.com/b/DoD8aeZy/rally
