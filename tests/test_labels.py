import logging
import unittest
from unittest.mock import Mock

from cloudflare_manager.cloudflare_api import CloudflareApi, DnsRecordType
from cloudflare_manager.api import Api, CachedApi
from cloudflare_manager.main import get_params_from_labels

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s|%(name)s|%(levelname)s|%(message)s')

cf_mock = Mock(CloudflareApi)
cf_mock.get_zone_id.return_value = 'example_zone_id'

valid_labels = {
    'cloudflare.zero_trust.access.tunnel.public_hostname': 'host.example.com',
    'cloudflare.zero_trust.access.tunnel.service': 'http://foo:80',
}


class TestLabels(unittest.TestCase):
    def test_bad_hostname(self):
        labels = {
            'cloudflare.zero_trust.access.tunnel.public_hostname': 'host',
            'cloudflare.zero_trust.access.tunnel.service': 'http://foo:80',
        }
        with self.assertRaises(Exception):
            get_params_from_labels(Api(cf_mock), 'account_id', 'tunnel', labels)

    def test_bad_service(self):
        labels = {
            'cloudflare.zero_trust.access.tunnel.public_hostname': 'host.example.com',
            'cloudflare.zero_trust.access.tunnel.service': 'foo://service',
        }
        with self.assertRaises(Exception):
            get_params_from_labels(Api(cf_mock), 'account_id', 'tunnel', labels)

    def _assert_valid(self, params, tunnel_id, zone_id, notlsverify):
        if len(params) > 0:
            pp = params[0]
            self.assertEqual(pp.dns_params.dns_type, DnsRecordType.CNAME)
            self.assertEqual(pp.hostname, 'host.example.com')
            self.assertEqual(pp.service, 'http://foo:80')
            self.assertEqual(pp.notlsverify, notlsverify)
            self.assertEqual(pp.tunnel_id, tunnel_id)
            self.assertEqual(pp.zone_name, 'example.com')
            self.assertEqual(pp.zone_id, zone_id)
        if len(params) > 1:
            pp = params[1]
            self.assertEqual(pp.dns_params.dns_type, DnsRecordType.CNAME)
            self.assertEqual(pp.hostname, 'example.com')
            self.assertEqual(pp.service, 'http://foo:80')
            self.assertEqual(pp.notlsverify, notlsverify)
            self.assertEqual(pp.tunnel_id, tunnel_id)
            self.assertEqual(pp.zone_name, 'example.com')
            self.assertEqual(pp.zone_id, zone_id)
        if len(params) > 2:
            pp = params[2]
            self.assertEqual(pp.dns_params.dns_type, DnsRecordType.CNAME)
            self.assertEqual(pp.hostname, 'foo.domain.com')
            self.assertEqual(pp.service, 'http://foo:80')
            self.assertEqual(pp.notlsverify, notlsverify)
            self.assertEqual(pp.tunnel_id, tunnel_id)
            self.assertEqual(pp.zone_name, 'domain.com')
            self.assertEqual(pp.zone_id, 'domain_zone_id')

    def test_valid(self):
        labels = valid_labels
        params = get_params_from_labels(Api(cf_mock), 'account_id', 'tunnel', labels)
        self._assert_valid(params, 'tunnel', 'example_zone_id', None)

    def test_valid_with_cached_zone(self):
        labels = valid_labels
        api = CachedApi(cf_mock)
        api._zone_name_to_id = {('example.com',): 'example_zone_id_cached'}
        params = get_params_from_labels(api, 'account_id', 'tunnel', labels)
        self._assert_valid(params, 'tunnel', 'example_zone_id_cached', None)

    def test_valid_with_tunnel(self):
        labels = valid_labels.copy()
        labels['cloudflare.zero_trust.access.tunnel.id'] = 'specified-tunnel'
        params = get_params_from_labels(Api(cf_mock), 'account_id', 'tunnel', labels)
        self._assert_valid(params, 'specified-tunnel', 'example_zone_id', None)

    def test_valid_with_notlsverify(self):
        labels = valid_labels.copy()
        labels['cloudflare.zero_trust.access.tunnel.tls.notlsverify'] = 'true'
        params = get_params_from_labels(Api(cf_mock), 'account_id', 'tunnel', labels)
        self._assert_valid(params, 'tunnel', 'example_zone_id', True)

    def test_valid_with_invalid_notlsverify(self):
        labels = valid_labels.copy()
        labels['cloudflare.zero_trust.access.tunnel.tls.notlsverify'] = 'foo'
        with self.assertRaises(Exception):
            get_params_from_labels(Api(cf_mock), 'account_id', 'tunnel', labels)

    def test_valid_multiple_hostnams(self):
        labels = valid_labels.copy()
        labels['cloudflare.zero_trust.access.tunnel.public_hostname'] = 'host.example.com,example.com,foo.domain.com'

        cf_mock = Mock(CloudflareApi)
        cf_mock.get_zone_id.side_effect = ['example_zone_id', 'example_zone_id', 'domain_zone_id']

        params = get_params_from_labels(Api(cf_mock), 'account_id', 'tunnel', labels)
        self._assert_valid(params, 'tunnel', 'example_zone_id', None)
