=========
Changelog
=========

.. Changelogs are for humans, not machines. The end users of Rally project are
   human beings who care about what's is changing, why and how it affects them.
   Please leave these notes as much as possible human oriented.

.. Each release can use the next sections:
    - **Added** for new features.
    - **Changed** for changes in existing functionality.
    - **Deprecated** for soon-to-be removed features/plugins.
    - **Removed** for now removed features/plugins.
    - **Fixed** for any bug fixes.

.. Release notes for existing releases are MUTABLE! If there is something that
   was missed or can be improved, feel free to change it!

[2.0.0] - 2020-05-08
--------------------

Added
~~~~~

* The *rally_openstack.task.context.OpenStackContext* class which provides
  helpers for all OpenStack context.

* Declare Python 3.8 support

* ManilaShares.create_share_and_access_from_vm scenario which allows to check
  share access from within a VM.

* Regular automated builds for `docker image
  <https://hub.docker.com/r/xrally/xrally-openstack>`_

* VMTasks.check_designate_dns_resolving scenario which tests resolving
  hostname from within a VM using existing designate DNS.

Changed
~~~~~~~

* `docker image <https://hub.docker.com/r/xrally/xrally-openstack>`_ is
  switched to use `docker image <https://hub.docker.com/r/xrally/xrally>`_ as
  a base user that brings use python 3.6 and ubuntu bionic.

* Bump min supported Rally framework version to 3.1.0 (rally>=3.1.0)

* Extend *network@openstack* context to save information about created subnets
  and *existing_network@openstack* context with listing subnets.

Deprecated
~~~~~~~~~~

* a huge project restructure had happened. Old paths are deprecated now.

    rally_openstack.cfg         ->  rally_openstack.common.cfg

    rally_openstack.cleanup     ->  rally_openstack.task.cleanup

    rally_openstack.consts      ->  rally_openstack.common.consts

    rally_openstack.contexts    ->  rally_openstack.task.contexts

    rally_openstack.credential  ->  rally_openstack.common.credential

    rally_openstack.embedcharts ->  rally_openstack.task.ui.charts

    rally_openstack.exceptions  ->  rally_openstack.common.exceptions

    rally_openstack.hook        ->  rally_openstack.task.hooks

    rally_openstack.osclients   ->  rally_openstack.common.osclients

    rally_openstack.platforms   ->  rally_openstack.environment.platforms

    rally_openstack.scenario    ->  rally_openstack.task.scenario

    rally_openstack.scenarios   ->  rally_openstack.task.scenarios

    rally_openstack.service     ->  rally_openstack.common.service

    rally_openstack.services    ->  rally_openstack.common.services

    rally_openstack.types       ->  rally_openstack.task.types

    rally_openstack.validators  ->  rally_openstack.common.validators

    rally_openstack.wrappers    ->  rally_openstack.common.wrappers


Removed
~~~~~~~

* Support for Python < 3.6

* *required_clients* validator was deprecated since Rally 0.10.0 (at the time
  when OpenStack plugins were part of Rally framework).

* `api_info` argument of OSClient plugins since it was merged into credentials
  object long time ago.

* The keyword arguments for *GlanceImages.create_image_and_boot_instances*
  scenario. They were deprecated since Rally 0.8.0 (at the time when OpenStack
  plugins were part of Rally framework). Use *boot_server_kwargs* for
  additional parameters when booting servers.

* *server_kwargs* alias for *boot_server_kwargs* of
  *NovaKeypair.boot_and_delete_server_with_keypair* scenario was deprecated
  since Rally 0.3.2 (at the time when OpenStack plugins were part of Rally
  framework).

* *api_versions* argument of cleanup manager.

[1.7.0] - 2019-12-25
--------------------

Added
~~~~~

* An ability to specify Primary and Alternate reference flavor disk sized.

* Support to upload an image from a https server

Fixed
~~~~~

* [tempest] Only volume-backed servers are allowed for flavors with zero disk
  on stein

  `Launchpad-bug #1841609 <https://launchpad.net/bugs/1841609>`_

* [tempest] Failing to configure Tempest with nullable fields at Python 3 envs

  `Launchpad-bug #1863945 <https://launchpad.net/bugs/1863945>`_

[1.6.0] - 2019-11-29
--------------------

Please note that Python 2.7 will reach the end of its life on
January 1st, 2020. A future version of Rally will drop support for Python 2.7,
it will happen soon. Also, the same will happen with support of Python 3.4 and
Python 3.5

Added
~~~~~

Scenarios:

* NeutronNetworks.create_and_bind_ports
* BarbicanOrders.list
* BarbicanOrders.create_key_and_delete
* BarbicanOrders.create_certificate_and_delete
* BarbicanOrders.create_asymmetric_and_delete

Removed
~~~~~~~

* Removed the former multiattach support dropped in Cinder Train (5.0.0)
* Removed the former ``sort_key`` and ``sort_dir`` support at listing cinder
  volumes.

Changed
~~~~~~~

* Improved logging message for the number of used threads while creating
  keystone users and projects/tenants at *users@openstack* context.
* Updated upper-constraints
* Improved check for existing rules at *allow_ssh* context.

Fixed
~~~~~

* Handling of errors while cleaning up octavia resources
* Missing project_id key for several Octavia API calls

  `Launchpad-bug #1819284 <https://launchpad.net/bugs/1833235>`_

[1.5.0] - 2019-05-29
--------------------

Added
~~~~~

* libpq-dev dependency to docker image for supporting external PostgreSQL
  backend

* Extend configuration of identity section for tempest with endpoint type

* A new option *user_password* is added to users context for specifying certain
  password for new users.

Changed
~~~~~~~

* Default Cinder service type is switched to **block-storage** as it is
  new unversioned endpoint. ``api_versions@openstack`` context or ``api_info``
  property of environment configuration should be used for selecting another
  service type.

* Rally 1.5.1 is used by default. Minimum required version is not changed.

* Default source of tempest is switched from git.openstack.org to
  git.opendev.org due to recent infrastructure changes.

Fixed
~~~~~~~

* For performance optimization some calls from python-barbicanclient to
  Barbican API are lazy. In case of secret representation, until any property
  is invoked on it, no real call to API is made which affects timings of
  obtaining the resource and slows down cleanup process.

  `Launchpad-bug #1819284 <https://launchpad.net/bugs/1819284>`_

* Tempest configurator was case sensitive while filtering roles by name.

* python 3 incompatibility while uploading glance images

  `Launchpad-bug #1819274 <https://launchpad.net/bugs/1819274>`_

[1.4.0] - 2019-03-07
--------------------

Added
~~~~~

* Added neutron trunk scenarios
* Added barbican scenarios
  * [scenario plugin] BarbicanContainers.list
  * [scenario plugin] BarbicanContainers.create_and_delete
  * [scenario plugin] BarbicanContainers.create_and_add
  * [scenario plugin] BarbicanContainers.create_certificate_and_delete
  * [scenario plugin] BarbicanContainers.create_rsa_and_delete
  * [scenario plugin] BarbicanSecrets.list
  * [scenario plugin] BarbicanSecrets.create
  * [scenario plugin] BarbicanSecrets.create_and_delete
  * [scenario plugin] BarbicanSecrets.create_and_get
  * [scenario plugin] BarbicanSecrets.get
  * [scenario plugin] BarbicanSecrets.create_and_list
  * [scenario plugin] BarbicanSecrets.create_symmetric_and_delete
* Added octavia scenarios
  * [scenario plugin] Octavia.create_and_list_loadbalancers
  * [scenario plugin] Octavia.create_and_delete_loadbalancers
  * [scenario plugin] Octavia.create_and_update_loadbalancers
  * [scenario plugin] Octavia.create_and_stats_loadbalancers
  * [scenario plugin] Octavia.create_and_show_loadbalancers
  * [scenario plugin] Octavia.create_and_list_pools
  * [scenario plugin] Octavia.create_and_delete_pools
  * [scenario plugin] Octavia.create_and_update_pools
  * [scenario plugin] Octavia.create_and_show_pools
* Support for osprofiler config in Devstack plugin.
* Added property 'floating_ip_enabled' in magnum cluster_templates context.
* Enhanced neutron trunk port scenario to create multiple trunks
* Enhanced NeutronSecurityGroup.create_and_list_security_group_rules
* Added three new trunk port related scenarios
  * [scenario plugin] NeutronTrunks.boot_server_with_subports
  * [scenario plugin] NeutronTrunks.boot_server_and_add_subports
  * [scenario plugin] NeutronTrunks.boot_server_and_batch_add_subports
* Added neutron scenarios
  [scenario plugin] NeutronNetworks.associate_and_dissociate_floating_ips

Changed
~~~~~~~

* Extend CinderVolumes.list_volumes scenario arguments.

Fixed
~~~~~

* Ignoring ``region_name`` from environment specification while
  initializing keystone client.
* Fetching OSProfiler trace-info for some drivers.
* ``https_insecure`` is not passed to manilaclient

[1.3.0] - 2018-10-08
--------------------

Added
~~~~~

* Support Python 3.7 environment.
* New options ``https_cert`` and ``https_key`` are added to the spec for
  ``existing@openstack`` platform to represent client certificate bundle and
  key files. Also the support for appropriate system environment variables (
  ``OS_CERT``, ``OS_KEY``) is added.
* ``existing@openstack`` plugin now supports a new field ``api_info`` for
  specifying not default API version/service_type to use. The format and
  purpose is similar to `api_versions
  <https://xrally.org/plugins/openstack/plugins/#api_versions-context>`_ task
  context.
* Added Cinder V3 support and use it as the default version. You could use
  api_versions context or api_info option of the spec to choose the proper
  version.
* The documentation for ``existing@openstack`` plugin is extended with
  information about accepted system environment variables via
  ``rally env create --from-sysenv`` command.

Changed
~~~~~~~

* Our requirements are updated as like upper-constraints (the list of
  suggested tested versions to use)
* Error messages become more user-friendly in ``rally env check``.
* Deprecate api_info argument of all clients plugins which inherits from
  OSClient and deprecate api_version argument of
  ``rally_openstack.cleanup.manager.cleanup``. API information (not default
  version/service_type to use) has been included into credentials dictionary.
* The proper packages are added to `docker image
  <https://hub.docker.com/r/xrally/xrally-openstack>`_ to support MySQL and
  PostgreSQL as DB backends.
* Rename an action ``nova.create_image`` to ``nova.snapshot_server`` for better
  understanding for what is actually done.

Removed
~~~~~~~

* Remove deprecated wrappers (rally_openstack.wrappers) and
  helpers (scenario utils) for Keystone, Cinder, Glance
  services. The new service model should be used instead
  (see ``rally_openstack.services`` module for more details)
  while developing custom plugins. All the inner plugins have been using
  the new code for a long time.
* Remove deprecated properties *insecure*, *cacert* (use *https_insecure* and
  *https_cacert* properties instead) and method *list_services* (use
  appropriate method of Clients object) from
  *rally_openstack.credentials.OpenStackCredentials* object.
* Remove deprecated in Rally 0.10.0 ``NovaImages.list_images`` scenario.

Fixed
~~~~~

* Keypairs are now properly cleaned up after the execution of Magnum
  workloads.


[1.2.0] - 2018-06-25
--------------------

Rally 1.0.0 has released. This is a major release which doesn't contain
in-tree OpenStack plugins. Also, this release extends flexibility of
validating required platforms which means that logic of required admin/users
for the plugin can be implemented at **rally-openstack** side and this is
done in rally-openstack 1.2.0

Changed
~~~~~~~

Also, it is sad to mention, but due to OpenStack policies we need to stop
duplicating release notes at ``git tag message``. At least for now.

[1.1.0] - 2018-05-11
--------------------

Added
~~~~~

* [scenario plugin] GnocchiMetric.list_metric
* [scenario plugin] GnocchiMetric.create_metric
* [scenario plugin] GnocchiMetric.create_delete_metric
* [scenario plugin] GnocchiResource.create_resource
* [scenario plugin] GnocchiResource.create_delete_resource
* Introduce *__version__*, *__version_tuple__* at *rally_openstack* module.
  As like other python packages each release of *rally-openstack* package can
  introduce new things, deprecate or even remove other ones. To simplify
  integration with other plugins which depends on *rally-openstack*, the new
  properties can be used with proper checks.

Changed
~~~~~~~

* `Docker image <https://hub.docker.com/r/xrally/xrally-openstack>`_ ported
  to publish images from `rally-openstack
  <https://github.com/openstack/rally-openstack>`_ repo instead of using the
  rally framework repository.
  Also, the CI is extended to check ability to build Docker image for any of
  changes.
* An interface of ResourceType plugins is changed since Rally 0.12. All our
  plugins are adopted to support it.
  The port is done in a backward compatible way, so the minimum required
  version of Rally still is 0.11.0, but we suggest you to use the latest
  release of Rally.

Removed
~~~~~~~

* Calculation of the duration for "nova.bind_actions" action. It shows
  only duration of initialization Rally inner class and can be easily
  misunderstood as some kind of "Nova operation".
  Affects 1 inner scenario "NovaServers.boot_and_bounce_server".

Fixed
~~~~~

* ``required_services`` validator should not check services which are
  configured via ``api_versions@openstack`` context since the proper validation
  is done at the context itself.
  The inner check for ``api_versions@openstack`` in ``required_services``
  checked only ``api_versions@openstack``, but ``api_versions`` string is also
  valid name for the context (if there is no other ``api_versions`` contexts
  for other platforms, but the case of name conflict is covered by another
  check).

[1.0.0] - 2018-03-28
--------------------
A start of a fork from `rally/plugins/openstack module of original OpenStack
Rally project
<https://github.com/openstack/rally/tree/0.11.1/rally/plugins/openstack>`_

Added
~~~~~

* [scenario plugin] GnocchiArchivePolicy.list_archive_policy
* [scenario plugin] GnocchiArchivePolicy.create_archive_policy
* [scenario plugin] GnocchiArchivePolicy.create_delete_archive_policy
* [scenario plugin] GnocchiResourceType.list_resource_type
* [scenario plugin] GnocchiResourceType.create_resource_type
* [scenario plugin] GnocchiResourceType.create_delete_resource_type
* [scenario plugin] NeutronSubnets.delete_subnets
* [ci] New Zuul V3 native jobs
* Extend existing@openstack platform to support creating a specification based
  on system environment variables. This feature should be available with
  Rally>0.11.1

Changed
~~~~~~~

* Methods for association and dissociation floating ips  were deprecated in
  novaclient a year ago and latest major release (python-novaclient 10)
  `doesn't include them
  <https://github.com/openstack/python-novaclient/blob/10.0.0/releasenotes/notes/remove-virt-interfaces-add-rm-fixed-floating-398c905d9c91cca8.yaml>`_.
  These actions should be performed via neutronclient now. It is not as simple
  as it was via Nova-API and you can find more neutron-related atomic actions
  in results of workloads.

Removed
~~~~~~~

* *os-hosts* CLIs and python API bindings had been deprecated in
  python-novaclient 9.0.0 and became removed in `10.0.0 release
  <https://github.com/openstack/python-novaclient/blob/10.0.0/releasenotes/notes/remove-hosts-d08855550c40b9c6.yaml>`_.
  This decision affected 2 scenarios `NovaHosts.list_hosts
  <https://rally.readthedocs.io/en/0.11.1/plugins/plugin_reference.html#novahosts-list-hosts-scenario>`_
  and `NovaHosts.list_and_get_hosts
  <https://rally.readthedocs.io/en/0.11.1/plugins/plugin_reference.html#novahosts-list-and-get-hosts-scenario>`_
  which become redundant and we cannot leave them (python-novaclient doesn't
  have proper interfaces any more).

Fixed
~~~~~

* The support of `kubernetes python client
  <https://pypi.org/project/kubernetes>`_ (which is used by Magnum plugins)
  is not limited by 3.0.0 max version. You can use more modern releases of that
  library.
