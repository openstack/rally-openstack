Tasks Configuration Samples
===========================

To specify your tasks, use configuration files in json or yaml format.


The input task format (version 2) looks like:

::

    {
        "version": 2,
        "title": "A task title",
        "description": "A longer description of the task",
        "subtasks": [
            {
                "title": "A subtask title",
                "scenario": {
                    "ScenarioClass.scenario_method": {
                        ...
                    }
                },
                "runner": {
                    "constant": {
                        ...
                    }
                },
                "contexts": {
                    ...
                },
                "sla": {
                    ...
                }
            }
        ]
    }


Scenario Plugin should be a subclass of the base Scenario class
and implement run() method. The object under "scenario" maps the scenario
name to its arguments. To learn more about scenarios configuration, see
samples in `samples/tasks/scenarios
<https://github.com/openstack/rally/tree/master/samples/tasks/scenarios>`_.

Section "runner" specifies the way, how task should be run. To learn
more about runners configurations, see samples in `samples/tasks/runners
<https://github.com/openstack/rally/tree/master/samples/tasks/runners>`_.

Section "contexts" defines different types of environments in which task can
be launched. Look at `samples/tasks/contexts
<https://github.com/openstack/rally/tree/master/samples/tasks/contexts>`_
for samples.

Section "sla" defines details for determining compliance with contracted values
such as maximum error rate or minimum response time.
Look at `samples/tasks/sla
<https://github.com/openstack/rally/tree/master/samples/tasks/sla>`_ for
samples.

See a `detailed description of scenarios, contexts & runners
<https://github.com/openstack/rally/tree/master/source/concepts.rst>`_.
