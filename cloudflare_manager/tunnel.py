import argparse
import logging
from pprint import pformat
from .api import Api

LOGGER = logging.getLogger('cfd-hostnames.tunnel')


def ingress_exists(params, tunnel_ingress: list) -> bool:
    hostname_lower = params.hostname.lower()
    for item in tunnel_ingress:
        if item.get('hostname', '').lower() == hostname_lower:
            return True
    return False


def params_to_tunnel_ingress_entry(params) -> dict[str, str]:
    origin_request = {}
    if params.notlsverify is not None:
        origin_request['noTLSVerify'] = params.notlsverify
    return {
        'service': params.service,
        'hostname': params.hostname,
        'originRequest': origin_request,
    }


class Tunnel:
    def __init__(self, api: Api, account_id: str, tunnel_id: str):
        self._api = api
        self._account_id = account_id
        self._tunnel_id = tunnel_id
        self._ingress = api.get_tunnel_ingress(account_id, tunnel_id)
        self._ingress_changed = False

    def add_ingress(self, params):
        if ingress_exists(params, self._ingress):
            LOGGER.info('Public hostname "%s" for tunnel "%s" already exists', params.hostname, params.tunnel_id)
        else:
            self._ingress.insert(-1, params_to_tunnel_ingress_entry(params))
            LOGGER.info(f'Adding public hostname "%s" -> "%s" for tunnel "%s"', params.hostname, params.service,
                        params.tunnel_id)
            self._ingress_changed = True

    def remove_ingress(self, params):
        LOGGER.info(f'Removing public hostname "%s" for tunnel "%s"', params.hostname, params.tunnel_id)
        before_len = len(self._ingress)
        hostname_lower = params.hostname.lower()
        self._ingress = [ii for ii in self._ingress if ii.get('hostname', '').lower() != hostname_lower]
        if before_len == len(self._ingress):
            LOGGER.warning('No public hostname "%s" for tunnel "%s"', params.hostname, params.tunnel_id)
        else:
            self._ingress_changed = True

    def update_cloudflare(self, args: argparse.Namespace):
        if self._ingress_changed:
            if LOGGER.isEnabledFor(logging.INFO):
                LOGGER.info('Updating ingress for tunnel %s:\n%s', self._tunnel_id, pformat(self._ingress))
            if not args.dry_run:
                if not self._api.cf.update_tunnel_configs(self._account_id, self._tunnel_id,
                                                          {'config': {'ingress': self._ingress}}):
                    LOGGER.error(f'Failed to update tunnel ingress for tunnel "{self._tunnel_id}" failed')
            self._ingress_changed = False
