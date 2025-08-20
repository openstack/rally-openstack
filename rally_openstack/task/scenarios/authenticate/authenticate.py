# Copyright 2014 Red Hat, Inc. <http://www.redhat.com>
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

from rally.task import atomic
from rally.task import validation

from rally_openstack.task import scenario


"""Scenarios for Authentication mechanism."""


@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="Authenticate.keystone", platform="openstack")
class Keystone(scenario.OpenStackScenario):

    @atomic.action_timer("authenticate.keystone")
    def run(self):
        """Check Keystone Client."""
        self.clients("keystone")


@validation.add("number", param_name="repetitions", minval=1)
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="Authenticate.validate_glance", platform="openstack")
class ValidateGlance(scenario.OpenStackScenario):

    def run(self, repetitions):
        """Check Glance Client to ensure validation of token.

        Creation of the client does not ensure validation of the token.
        We have to do some minimal operation to make sure token gets validated.
        In following we are checking for non-existent image.

        :param repetitions: number of times to validate
        """
        glance_client = self.clients("glance")
        image_name = "__intentionally_non_existent_image___"
        with atomic.ActionTimer(self, "authenticate.validate_glance"):
            for i in range(repetitions):
                list(glance_client.images.list(name=image_name))


@validation.add("number", param_name="repetitions", minval=1)
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="Authenticate.validate_nova", platform="openstack")
class ValidateNova(scenario.OpenStackScenario):

    def run(self, repetitions):
        """Check Nova Client to ensure validation of token.

        Creation of the client does not ensure validation of the token.
        We have to do some minimal operation to make sure token gets validated.

        :param repetitions: number of times to validate
        """
        nova_client = self.clients("nova")
        with atomic.ActionTimer(self, "authenticate.validate_nova"):
            for i in range(repetitions):
                nova_client.flavors.list()


@validation.add("number", param_name="repetitions", minval=1)
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="Authenticate.validate_ceilometer",
                    platform="openstack")
class ValidateCeilometer(scenario.OpenStackScenario):

    def run(self, repetitions):
        """Check Ceilometer Client to ensure validation of token.

        Creation of the client does not ensure validation of the token.
        We have to do some minimal operation to make sure token gets validated.

        :param repetitions: number of times to validate
        """
        ceilometer_client = self.clients("ceilometer")
        with atomic.ActionTimer(self, "authenticate.validate_ceilometer"):
            for i in range(repetitions):
                ceilometer_client.meters.list()


@validation.add("number", param_name="repetitions", minval=1)
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="Authenticate.validate_cinder", platform="openstack")
class ValidateCinder(scenario.OpenStackScenario):

    def run(self, repetitions):
        """Check Cinder Client to ensure validation of token.

        Creation of the client does not ensure validation of the token.
        We have to do some minimal operation to make sure token gets validated.

        :param repetitions: number of times to validate
        """
        cinder_client = self.clients("cinder")
        with atomic.ActionTimer(self, "authenticate.validate_cinder"):
            for i in range(repetitions):
                cinder_client.volume_types.list()


@validation.add("number", param_name="repetitions", minval=1)
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="Authenticate.validate_neutron", platform="openstack")
class ValidateNeutron(scenario.OpenStackScenario):

    def run(self, repetitions):
        """Check Neutron Client to ensure validation of token.

        Creation of the client does not ensure validation of the token.
        We have to do some minimal operation to make sure token gets validated.

        :param repetitions: number of times to validate
        """
        neutron_client = self.clients("neutron")
        with atomic.ActionTimer(self, "authenticate.validate_neutron"):
            for i in range(repetitions):
                neutron_client.list_networks()


@validation.add("number", param_name="repetitions", minval=1)
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="Authenticate.validate_octavia", platform="openstack")
class ValidateOctavia(scenario.OpenStackScenario):

    def run(self, repetitions):
        """Check Octavia Client to ensure validation of token.

        Creation of the client does not ensure validation of the token.
        We have to do some minimal operation to make sure token gets validated.

        :param repetitions: number of times to validate
        """
        octavia_client = self.clients("octavia")
        with atomic.ActionTimer(self, "authenticate.validate_octavia"):
            for i in range(repetitions):
                octavia_client.load_balancer_list()


@validation.add("number", param_name="repetitions", minval=1)
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="Authenticate.validate_heat", platform="openstack")
class ValidateHeat(scenario.OpenStackScenario):

    def run(self, repetitions):
        """Check Heat Client to ensure validation of token.

        Creation of the client does not ensure validation of the token.
        We have to do some minimal operation to make sure token gets validated.

        :param repetitions: number of times to validate
        """
        heat_client = self.clients("heat")
        with atomic.ActionTimer(self, "authenticate.validate_heat"):
            for i in range(repetitions):
                list(heat_client.stacks.list(limit=0))
