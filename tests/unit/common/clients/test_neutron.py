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

from unittest import mock

from rally_openstack.common import credential as oscredential
from rally_openstack.common.clients import neutron
from tests.unit import test


PATH = "rally_openstack.common.clients.neutron"


class NeutronTestMixin:

    def setUp(self):
        super().setUp()
        self.credential = oscredential.OpenStackCredential(
            "http://auth_url/v3", "user", "pass", "tenant")

    def _make_neutron(self, cache=None, name_generator=True):
        client = neutron.Neutron(
            self.credential, {} if cache is None else cache)
        client._clients = mock.Mock()
        if name_generator:
            client._name_generator = mock.Mock(return_value="random_name")
        return client

    @property
    def network(self):
        return self.neutron._clients._conn.network


class NeutronLegacyClientTestCase(NeutronTestMixin, test.TestCase):

    @mock.patch("%s.Neutron.keystone" % PATH, new_callable=mock.PropertyMock)
    def test_create_client(self, mock_neutron_keystone):
        self.neutron = self._make_neutron(name_generator=False)
        session = mock.Mock()
        mock_neutron_keystone.return_value.get_session.return_value = (
            session, mock.Mock())
        self.neutron._get_endpoint = mock.Mock(return_value="http://neutron")

        with mock.patch(
            "neutronclient.neutron.client.Client",
        ) as neutron_client:
            result = self.neutron.create_client()

        neutron_client.assert_called_once_with(
            "2.0",
            session=session,
            endpoint_override="http://neutron",
        )
        self.assertEqual(neutron_client.return_value, result)

    def test_call_returns_legacy_client_by_default(self):
        self.neutron = self._make_neutron(name_generator=False)
        legacy = mock.Mock()
        self.neutron.create_client = mock.Mock(return_value=legacy)

        self.assertEqual(legacy, self.neutron())
        self.neutron.create_client.assert_called_once_with(None)

    def test_call_legacy_false_returns_sdk_client(self):
        self.neutron = self._make_neutron(name_generator=False)

        self.assertIs(self.neutron, self.neutron(legacy=False))


class NeutronNetworkTestCase(NeutronTestMixin, test.TestCase):

    def setUp(self):
        super().setUp()
        self.neutron = self._make_neutron()

    def test_create_network(self):
        mock_network = mock.Mock(id="net-id")
        self.network.create_network.return_value = mock_network

        result = self.neutron.create_network()

        self.assertEqual(mock_network, result)
        self.network.create_network.assert_called_once_with(
            name="random_name",
        )

    def test_create_network_with_name(self):
        self.network.create_network.return_value = mock.Mock(id="net-id")

        self.neutron.create_network(name="my-network")

        self.network.create_network.assert_called_once_with(name="my-network")

    def test_list_networks(self):
        networks = [mock.Mock(id="net-1"), mock.Mock(id="net-2")]
        self.network.networks.return_value = networks

        result = self.neutron.list_networks()

        self.assertEqual(networks, result)
        self.network.networks.assert_called_once_with()

    def test_get_network(self):
        mock_network = mock.Mock(id="net-id")
        self.network.get_network.return_value = mock_network

        result = self.neutron.get_network("net-id")

        self.assertEqual(mock_network, result)
        self.network.get_network.assert_called_once_with("net-id")

    def test_delete_network(self):
        self.neutron.delete_network("net-id")

        self.network.delete_network.assert_called_once_with("net-id")

    def test_create_port(self):
        mock_port = mock.Mock(id="port-id")
        self.network.create_port.return_value = mock_port

        result = self.neutron.create_port(network_id="net-id")

        self.assertEqual(mock_port, result)
        self.network.create_port.assert_called_once_with(
            network_id="net-id",
            name="random_name",
        )

    def test_create_port_with_name(self):
        self.network.create_port.return_value = mock.Mock(id="port-id")

        self.neutron.create_port(network_id="net-id", name="my-port")

        self.network.create_port.assert_called_once_with(
            network_id="net-id",
            name="my-port",
        )

    def test_create_port_does_not_mutate_kwargs(self):
        self.network.create_port.return_value = mock.Mock(id="port-id")
        kwargs = {"device_owner": "compute:nova"}

        self.neutron.create_port(network_id="net-id", **kwargs)

        self.assertNotIn("name", kwargs)

    def test_list_ports(self):
        ports = [mock.Mock(id="port-1"), mock.Mock(id="port-2")]
        self.network.ports.return_value = ports

        result = self.neutron.list_ports()

        self.assertEqual(ports, result)
        self.network.ports.assert_called_once_with()

    def test_get_port(self):
        mock_port = mock.Mock(id="port-id")
        self.network.get_port.return_value = mock_port

        result = self.neutron.get_port("port-id")

        self.assertEqual(mock_port, result)
        self.network.get_port.assert_called_once_with("port-id")

    def test_delete_port(self):
        self.neutron.delete_port("port-id")

        self.network.delete_port.assert_called_once_with("port-id")


class NeutronTapMirrorTestCase(NeutronTestMixin, test.TestCase):

    def setUp(self):
        super().setUp()
        self.neutron = self._make_neutron()

    def test_create_tap_mirror(self):
        mock_mirror = mock.MagicMock()
        self.network.create_tap_mirror.return_value = mock_mirror

        result = self.neutron.create_tap_mirror(
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
        )

        self.assertEqual(mock_mirror, result)
        self.network.create_tap_mirror.assert_called_once_with(
            name="random_name",
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
            mirror_type="gre",
        )

    def test_create_tap_mirror_erspanv1(self):
        self.network.create_tap_mirror.return_value = mock.MagicMock()

        self.neutron.create_tap_mirror(
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
            mirror_type=neutron.MirrorType.ERSPANV1,
        )

        self.network.create_tap_mirror.assert_called_once_with(
            name="random_name",
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
            mirror_type="erspanv1",
        )

    def test_create_tap_mirror_with_description(self):
        mock_mirror = mock.MagicMock()
        self.network.create_tap_mirror.return_value = mock_mirror

        result = self.neutron.create_tap_mirror(
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
            description="mirror desc",
        )

        self.assertEqual(mock_mirror, result)
        self.network.create_tap_mirror.assert_called_once_with(
            name="random_name",
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
            mirror_type="gre",
            description="mirror desc",
        )

    def test_create_tap_mirror_always_generates_name(self):
        self.network.create_tap_mirror.return_value = mock.MagicMock()

        self.neutron.create_tap_mirror(
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
        )

        call_kwargs = self.network.create_tap_mirror.call_args.kwargs
        self.assertEqual("random_name", call_kwargs["name"])

    def test_list_tap_mirrors(self):
        mirrors = [mock.MagicMock(), mock.MagicMock()]
        self.network.tap_mirrors.return_value = iter(mirrors)

        result = self.neutron.list_tap_mirrors()

        self.assertEqual(mirrors, result)
        self.network.tap_mirrors.assert_called_once_with()

    def test_list_tap_mirrors_with_filter(self):
        mirrors = [mock.MagicMock()]
        self.network.tap_mirrors.return_value = iter(mirrors)

        result = self.neutron.list_tap_mirrors(project_id="proj-123")

        self.assertEqual(mirrors, result)
        self.network.tap_mirrors.assert_called_once_with(project_id="proj-123")

    def test_get_tap_mirror(self):
        mock_mirror = mock.MagicMock()
        self.network.get_tap_mirror.return_value = mock_mirror

        result = self.neutron.get_tap_mirror("mirror-id")

        self.assertEqual(mock_mirror, result)
        self.network.get_tap_mirror.assert_called_once_with("mirror-id")

    def test_update_tap_mirror_with_name(self):
        mock_mirror = mock.MagicMock()
        self.network.update_tap_mirror.return_value = mock_mirror

        result = self.neutron.update_tap_mirror(
            "mirror-id", name="new-name")

        self.assertEqual(mock_mirror, result)
        self.network.update_tap_mirror.assert_called_once_with(
            "mirror-id", name="new-name")

    def test_update_tap_mirror_with_description(self):
        mock_mirror = mock.MagicMock()
        self.network.update_tap_mirror.return_value = mock_mirror

        result = self.neutron.update_tap_mirror(
            "mirror-id", description="updated")

        self.assertEqual(mock_mirror, result)
        self.network.update_tap_mirror.assert_called_once_with(
            "mirror-id", description="updated")

    def test_update_tap_mirror_with_name_and_description(self):
        mock_mirror = mock.MagicMock()
        self.network.update_tap_mirror.return_value = mock_mirror

        result = self.neutron.update_tap_mirror(
            "mirror-id", name="new-name", description="new-desc")

        self.assertEqual(mock_mirror, result)
        self.network.update_tap_mirror.assert_called_once_with(
            "mirror-id", name="new-name", description="new-desc")

    def test_update_tap_mirror_raises_without_args(self):
        self.assertRaises(
            ValueError,
            self.neutron.update_tap_mirror, "mirror-id")

    def test_delete_tap_mirror(self):
        self.neutron.delete_tap_mirror("mirror-id")

        self.network.delete_tap_mirror.assert_called_once_with("mirror-id")
