import argparse
from copy import deepcopy
import unittest
from typing import NamedTuple, Dict
from unittest.mock import Mock, call

from cloudflared_hostnames.cloudflare_api import CloudflareApi, DnsRecordType
from cloudflared_hostnames.api import Api, CachedApi
from cloudflared_hostnames.main import load_containers

args = argparse.Namespace(dry_run=False)


class Container(NamedTuple):
    name: str
    status: str
    labels: Dict[str, str]


containers = [
    Container('c1', 'running',
              {
                  'cloudflare.zero_trust.access.tunnel.public_hostname': 'host.example.com',
                  'cloudflare.zero_trust.access.tunnel.service': 'http://service:80',
              }
              ),
    Container('c2', 'running', {'foo': 'bar'}),
    Container('c3', 'stopped', {}),
]


class TestLoadContainers(unittest.TestCase):
    def test_load(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_zone_id.return_value = 'example_zone_id'
        cf_mock.get_dns_records.return_value = []
        cf_mock.get_tunnel_configs.return_value = {'tunnel_id': 'tunnel_id', 'config': None}

        load_containers(args, containers, CachedApi(cf_mock), 'account_id', 'tunnel_id')

        cf_mock.create_dns_record.assert_called_once_with(DnsRecordType.CNAME, 'example_zone_id', 'host.example.com',
                                                          'tunnel_id.cfargotunnel.com')
        value = {
            'config': {
                'ingress': [
                    {'service': 'http://service:80', 'hostname': 'host.example.com', 'originRequest': {}},
                    {'service': 'http_status:404'},
                ]
            }
        }
        cf_mock.update_tunnel_configs.assert_called_once_with('account_id', 'tunnel_id', value)

    def test_load_multiple(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_zone_id.return_value = 'example_zone_id'
        cf_mock.get_dns_records.return_value = []
        cf_mock.get_tunnel_configs.return_value = {'tunnel_id': 'tunnel_id', 'config': None}

        global containers
        containers_copy = containers.copy()
        containers_copy.append(Container('c4', 'running',
                                         {
                                             'cloudflare.zero_trust.access.tunnel.public_hostname': 'host2.example.com',
                                             'cloudflare.zero_trust.access.tunnel.service': 'http://service2:80',
                                         }
                                         ))

        load_containers(args, containers_copy, CachedApi(cf_mock), 'account_id', 'tunnel_id')

        cf_mock.create_dns_record.assert_has_calls([
            call(DnsRecordType.CNAME, 'example_zone_id', 'host.example.com', 'tunnel_id.cfargotunnel.com'),
            call(DnsRecordType.CNAME, 'example_zone_id', 'host2.example.com', 'tunnel_id.cfargotunnel.com'),
        ])
        value = {
            'config': {
                'ingress': [
                    {'service': 'http://service:80', 'hostname': 'host.example.com', 'originRequest': {}},
                    {'service': 'http://service2:80', 'hostname': 'host2.example.com', 'originRequest': {}},
                    {'service': 'http_status:404'},
                ]
            }
        }
        cf_mock.update_tunnel_configs.assert_called_once_with('account_id', 'tunnel_id', value)

    def test_load_multiple_hostnames(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_zone_id.return_value = 'example_zone_id'
        cf_mock.get_dns_records.return_value = []
        cf_mock.get_tunnel_configs.return_value = {'tunnel_id': 'tunnel_id', 'config': None}

        global containers
        containers_copy = deepcopy(containers)
        containers_copy[0].labels[
            'cloudflare.zero_trust.access.tunnel.public_hostname'] = 'host.example.com,example.com'

        load_containers(args, containers_copy, CachedApi(cf_mock), 'account_id', 'tunnel_id')

        cf_mock.create_dns_record.assert_has_calls([
            call(DnsRecordType.CNAME, 'example_zone_id', 'host.example.com', 'tunnel_id.cfargotunnel.com'),
            call(DnsRecordType.CNAME, 'example_zone_id', 'example.com', 'tunnel_id.cfargotunnel.com'),
        ])

        value = {
            'config': {
                'ingress': [
                    {'service': 'http://service:80', 'hostname': 'host.example.com', 'originRequest': {}},
                    {'service': 'http://service:80', 'hostname': 'example.com', 'originRequest': {}},
                    {'service': 'http_status:404'},
                ]
            }
        }
        cf_mock.update_tunnel_configs.assert_called_once_with('account_id', 'tunnel_id', value)

    def test_load_dns_record_already_exists(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_zone_id.return_value = 'example_zone_id'
        cf_mock.get_dns_records.return_value = [{'name': 'host.example.com'}]
        cf_mock.get_tunnel_configs.return_value = {'tunnel_id': 'tunnel_id', 'config': None}

        load_containers(args, containers, CachedApi(cf_mock), 'account_id', 'tunnel_id')
        cf_mock.create_dns_record.assert_not_called()

    def test_load_ingress_already_exists(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_zone_id.return_value = 'example_zone_id'
        cf_mock.get_dns_records.return_value = [{'name': 'host.example.com'}]
        cf_mock.get_tunnel_configs.return_value = {
            'tunnel_id': 'tunnel_id',
            'config': {
                'ingress': [
                    {'service': 'http://service:80', 'hostname': 'host.example.com', 'originRequest': {}},
                    {'service': 'http_status:404'},
                ],
            },
        }

        load_containers(args, containers, CachedApi(cf_mock), 'account_id', 'tunnel_id')
        cf_mock.update_tunnel_configs.assert_not_called()
