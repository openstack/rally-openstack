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

[Unreleased]
------------

Added
~~~~~

* [scenario plugin] GnocchiMetric.list_metric
* [scenario plugin] GnocchiMetric.create_metric
* [scenario plugin] GnocchiMetric.create_delete_metric

[1.0.0] - 2018-03-28
--------------------
Start a fork of `rally/plugins/openstack module of original OpenStack Rally
project
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
  in results of scenarios.

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
  <https://pypi.python.org/pypi/kubernetes>`_ (which is used by Magnum plugins)
  is not limited by 3.0.0 max version. You can use more modern releases of that
  library.
