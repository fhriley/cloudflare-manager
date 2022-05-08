from collections import OrderedDict
from typing import Optional
from urllib.parse import urlparse

from .cloudflare_api import DnsRecordType
from .api import Api
from .params import Params
from .dns import DnsParams
from .zerotrust import ZeroTrustParams

_trues = {'true', 'True', 'TRUE', 't', 'T', '1'}
_falses = {'false', 'False', 'FALSE', 'f', 'F', '0'}


def validate_hostname(hostname: str):
    if not hostname:
        raise Exception('hostname not specified')
    # TODO: use domain regex
    hostname_split = hostname.split('.')
    if len(hostname_split) < 2:
        raise Exception('hostname must be like "domain.com" or "subdomain.domain.com"')
    return hostname


def validate_service(service: str):
    if not service:
        raise Exception('service not specified')
    parsed = urlparse(service)
    if not parsed.scheme or not parsed.netloc:
        raise Exception('service invalid')
    if parsed.scheme.lower() not in ('http', 'https'):
        raise Exception('service invalid scheme')
    return service


def validate_notlsverify(val: str) -> Optional[bool]:
    if val is None:
        return None
    if val in _trues:
        return True
    if val in _falses:
        return False
    raise Exception(f'invalid notlsverify value: "{val}"')


def get_zone_name(hostname: str) -> str:
    return '.'.join(hostname.split('.')[-2:])


def get_val_from_label(labels: dict[str, str], label: str, default: Optional[str] = None) -> Optional[str]:
    name = labels.get(label)
    if name is not None:
        return name.strip()
    return default


def get_names_from_label(labels: dict[str, str], label: str) -> list[str]:
    name = get_val_from_label(labels, label)
    if not name:
        return []
    names = OrderedDict.fromkeys(name.strip().split(','))
    return [validate_hostname(hn) for hn in names.keys()]


def get_zt_params_from_labels(api: Api, default_tunnel_id: str, labels: dict[str, str]) -> list[ZeroTrustParams]:
    hostnames = get_names_from_label(labels, 'cloudflare.zero_trust.access.tunnel.public_hostname')
    if not hostnames:
        return []

    service = get_val_from_label(labels, 'cloudflare.zero_trust.access.tunnel.service')
    service = validate_service(service)

    zone_names = [get_zone_name(hn) for hn in hostnames]
    zone_ids = [api.get_zone_id(zone_name) for zone_name in zone_names]

    tunnel_id = get_val_from_label(labels, 'cloudflare.zero_trust.access.tunnel.id', default_tunnel_id)

    notlsverify = get_val_from_label(labels, 'cloudflare.zero_trust.access.tunnel.tls.notlsverify')
    notlsverify = validate_notlsverify(notlsverify)

    return [ZeroTrustParams(hn, service, zone_names[ii], zone_ids[ii], tunnel_id, notlsverify) for ii, hn in
            enumerate(hostnames)]


def get_cname_params_from_labels(api: Api, labels: dict[str, str]) -> list[DnsParams]:
    cnames = get_names_from_label(labels, 'cloudflare.dns.cname.name')
    if not cnames:
        return []
    target = get_val_from_label(labels, 'cloudflare.dns.cname.target')
    if not target:
        raise Exception('target not specified for CNAME')
    # TODO: validate target
    zone_names = [get_zone_name(hn) for hn in cnames]
    zone_ids = [api.get_zone_id(zone_name) for zone_name in zone_names]
    return [DnsParams(name, target, zone_ids[ii], DnsRecordType.CNAME, False) for ii, name in enumerate(cnames)]


def get_aname_params_from_labels(api: Api, labels: dict[str, str]) -> list[DnsParams]:
    anames = get_names_from_label(labels, 'cloudflare.dns.a.name')
    if not anames:
        return []
    ip = get_val_from_label(labels, 'cloudflare.dns.a.ip')
    if not ip:
        raise Exception('ip not specified for A')
    # TODO: validate IP
    zone_names = [get_zone_name(hn) for hn in anames]
    zone_ids = [api.get_zone_id(zone_name) for zone_name in zone_names]
    return [DnsParams(name, ip, zone_ids[ii], DnsRecordType.A, False) for ii, name in enumerate(anames)]


def get_params_from_labels(api: Api, default_tunnel_id: str, labels: dict[str, str]) -> list[Params]:
    params: list[Params] = get_zt_params_from_labels(api, default_tunnel_id, labels)
    params.extend(get_cname_params_from_labels(api, labels))
    params.extend(get_aname_params_from_labels(api, labels))
    return params
