from __future__ import annotations

import logging
from .cloudflare_api import DnsRecordType
from .params import Params

LOGGER = logging.getLogger('cfd-hostnames.dns')


class DnsParams(Params):
    def __init__(self, name: str, value: str, zone_id: str, dns_type: DnsRecordType, proxied: bool):
        super().__init__(zone_id)
        self._name = name
        self._value = value
        self._dns_type = dns_type
        self._proxied = proxied

    def __hash__(self):
        return hash((self._dns_type, self._zone_id, self._name))

    def __eq__(self, other):
        return (self._dns_type, self._zone_id, self._name) == (other._dns_type, other._zone_id, other._name)

    def __str__(self):
        return f'{self._dns_type.name} {self._name} -> {self._value}'

    @property
    def name(self):
        return self._name

    @property
    def value(self):
        return self._value

    @property
    def dns_type(self):
        return self._dns_type

    @property
    def proxied(self):
        return self._proxied

    def add_to_zone(self, zone):
        zone.add_dns_record(self)

    def remove_from_zone(self, zone):
        zone.remove_dns_record(self)
