import logging
from typing import Optional
from .cloudflare_api import DnsRecordType
from .params import Params
from .dns import DnsParams

LOGGER = logging.getLogger('cfd-hostnames.zerotrust')


class ZeroTrustParams(Params):
    def __init__(self, hostname: str, service: str, zone_name: str, zone_id: str, tunnel_id: str,
                 notlsverify: Optional[bool] = None):
        super().__init__(zone_id)
        self._hostname = hostname
        self._service = service
        self._zone_name = zone_name
        self._tunnel_id = tunnel_id
        self._notlsverify = notlsverify
        self._dns_params = DnsParams(hostname, f'{tunnel_id}.cfargotunnel.com', zone_id, DnsRecordType.CNAME, True)

    def __str__(self):
        return f'{self._dns_params} -> {self._service}'

    @property
    def hostname(self):
        return self._hostname

    @property
    def service(self):
        return self._service

    @property
    def zone_name(self):
        return self._zone_name

    @property
    def tunnel_id(self):
        return self._tunnel_id

    @property
    def notlsverify(self):
        return self._notlsverify

    @property
    def dns_params(self):
        return self._dns_params

    def add_to_zone(self, zone):
        zone.add_dns_record(self._dns_params)
        zone.add_ingress(self)

    def remove_from_zone(self, zone):
        zone.remove_dns_record(self._dns_params)
        zone.remove_ingress(self)
