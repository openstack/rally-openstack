=====================
Zuul V3 configuration
=====================

Zuul is a pipeline-oriented project gating system. It facilitates running
tests and automated tasks in response to Code Review events.

See `official doc
<https://docs.openstack.org/infra/system-config/zuulv3.html>`_ for more
details.

What do we have in this dir?
---------------------------------

.. note:: Do not document all files and jobs here. It will (for sure) become
    outdated at some point.

* **zuul.yaml** - the main configuration file. It contains a list of jobs
  which should be launched at CI for rally-openstack project

* **base.yaml** - the second by importance file. It contains basic parent
  jobs.

* All other files are named as like a job for which they include definition.

Where are the actual job playbooks?
-----------------------------------

Unfortunately, Zuul defines *zuul.d* (as like *.zuul.d*) as a directory for
project configuration and job definitions.

Ansible roles, tasks cannot be here, so we placed them at *tests/ci/playbooks*
directory.

.. warning:: A task job resolves ``rally_task`` against the checkout of the
    project that triggers it. Passing an absolute path makes it possible to
    reuse a task file shipped in this repo from another project (e.g. rally).
    This is technically supported but not recommended in general, as it couples
    that project to rally-openstack's on-disk layout.
