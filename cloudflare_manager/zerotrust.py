import logging
from typing import Optional
from .cloudflare_api import DnsRecordType
from .params import Params
from .api import Api
from .dns import DnsParams
from .tunnel import Tunnel

LOGGER = logging.getLogger('cfd-hostnames.zerotrust')


class ZeroTrustParams(Params):
    def __init__(self, api: Api, account_id: str, hostname: str, service: str, zone_name: str, zone_id: str,
                 tunnel_id: str,
                 notlsverify: Optional[bool] = None):
        super().__init__(api, account_id, zone_id)
        self._hostname = hostname
        self._service = service
        self._zone_name = zone_name
        self._tunnel_id = tunnel_id
        self._notlsverify = notlsverify
        self._dns_params = DnsParams(api, account_id, hostname, f'{tunnel_id}.cfargotunnel.com', zone_id,
                                     DnsRecordType.CNAME, True)

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

    def remove_from_zone(self, zone):
        zone.remove_dns_record(self._dns_params)

    def _get_tunnel(self, tunnels: dict[str, Tunnel]):
        tunnel = tunnels.get(self._tunnel_id) or Tunnel(self._api, self._account_id, self._tunnel_id)
        tunnels[self._tunnel_id] = tunnel
        return tunnel

    def add_to_tunnel(self, tunnels: dict[str, Tunnel]):
        self._get_tunnel(tunnels).add_ingress(self)

    def remove_from_tunnel(self, tunnels: dict[str, Tunnel]):
        self._get_tunnel(tunnels).remove_ingress(self)
