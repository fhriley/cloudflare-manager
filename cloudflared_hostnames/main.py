import argparse
import logging
import os
from queue import SimpleQueue
from threading import Thread
from typing import NamedTuple, Tuple, List, Dict, Optional
from urllib.parse import urlparse

import docker
from docker.types.daemon import CancellableStream

from .cloudflare_api import CloudflareApi

LOGGER = logging.getLogger('cfd-hostnames')


class Params(NamedTuple):
    hostname: str
    service: str
    zone_name: str
    zone_id: str
    tunnel_id: str
    notlsverify: Optional[bool]


def docker_events_thread(events: CancellableStream, queue: SimpleQueue):
    for event in events:
        status = event.get('status')
        if event.get('Type') == 'container' and status in ('start', 'die'):
            queue.put(event)


def get_env_vars() -> List[str]:
    vals = []
    not_found = []
    os.environ['CLOUDFLARE_API_CERTKEY'] = ''
    for ev in ('CLOUDFLARE_ACCOUNT_ID', 'CLOUDFLARE_API_KEY', 'CLOUDFLARE_TUNNEL_ID'):
        val = os.environ.get(ev)
        if not val:
            not_found.append(ev)
        else:
            vals.append(val)
    if not_found:
        LOGGER.critical('%s environment variables are not set', ', '.join(not_found))
        raise SystemExit(1)
    return vals


def get_labels(labels: Dict[str, str]):
    return {key: val for key, val in labels.items() if key.startswith('cloudflare.')}


def validate_hostname(hostname: str):
    if hostname is not None:
        hostname = hostname.strip()
    if not hostname:
        raise Exception('hostname not specified')
    hostname_split = hostname.split('.')
    if len(hostname_split) != 3:
        raise Exception('hostname must be like "subdomain.domain.com"')
    return hostname


def validate_service(service: str):
    if service is not None:
        service = service.strip()
    if not service:
        raise Exception('service not specified')
    parsed = urlparse(service)
    if not parsed.scheme or not parsed.netloc:
        raise Exception('service invalid')
    if parsed.scheme.lower() not in ('http', 'https'):
        raise Exception('service invalid scheme')
    return service


def get_from_cache(cache, func, *keys):
    if cache is not None:
        if keys in cache:
            val = cache[keys]
        else:
            val = func()
            cache[keys] = val
    else:
        val = func()
    return val


def get_zone_id(cf: CloudflareApi, name: str, zone_name_to_id: Optional[Dict] = None) -> str:
    def _get_zone_id() -> str:
        zone_id = cf.get_zone_id(name)
        if not zone_id:
            raise Exception(f'Could not find zone name "{name}"')
        return zone_id

    return get_from_cache(zone_name_to_id, _get_zone_id, name)


_trues = {'true', 'True', 'TRUE', 't', 'T', '1'}
_falses = {'false', 'False', 'FALSE', 'f', 'F', '0'}


def validate_notlsverify(val: str) -> Optional[bool]:
    if val is None:
        return None
    if val in _trues:
        return True
    if val in _falses:
        return False
    raise Exception(f'invalid notlsverify value: "{val}"')


def get_params_from_labels(cf: CloudflareApi, default_tunnel_id: str, labels: Dict[str, str],
                           zone_name_to_id: Optional[Dict[Tuple[str], str]] = None) -> Params:
    hostname = labels.get('cloudflare.zero_trust.access.tunnel.public_hostname')
    hostname = validate_hostname(hostname)

    service = labels.get('cloudflare.zero_trust.access.tunnel.service')
    service = validate_service(service)

    hostname_split = hostname.split('.')
    zone_name = '.'.join(hostname_split[1:])

    tunnel_id = labels.get('cloudflare.zero_trust.access.tunnel.id', default_tunnel_id)

    notlsverify = labels.get('cloudflare.zero_trust.access.tunnel.tls.notlsverify')
    notlsverify = validate_notlsverify(notlsverify)

    zone_id = get_zone_id(cf, zone_name, zone_name_to_id)

    return Params(hostname, service, zone_name, zone_id, tunnel_id, notlsverify)


def tunnel_cname(tunnel_id: str) -> str:
    return f'{tunnel_id}.cfargotunnel.com'


def ingress_exists(params: Params, tunnel_ingress: List) -> bool:
    for item in tunnel_ingress:
        if item.get('hostname') == params.hostname:
            return True
    return False


def params_to_tunnel_ingress_entry(params):
    origin_request = {}
    if params.notlsverify is not None:
        origin_request['noTLSVerify'] = params.notlsverify
    return {
        'service': params.service,
        'hostname': params.hostname,
        'originRequest': origin_request,
    }


def add_tunnel_ingress(params: Params, tunnel_ingress: List):
    tunnel_ingress.insert(-1, params_to_tunnel_ingress_entry(params))
    LOGGER.info(f'Adding public hostname "%s" -> "%s" for tunnel "%s"', params.hostname, params.service,
                params.tunnel_id)


def get_cnames(cf: CloudflareApi, zone_id: str, cnames_by_zone_id: Optional[Dict] = None):
    def _get_cnames() -> Dict:
        cnames = cf.get_cnames(zone_id)
        if cnames is None:
            raise Exception(f'Could not find zone id "{zone_id}"')
        return {ii['name']: ii for ii in cnames}

    return get_from_cache(cnames_by_zone_id, _get_cnames, zone_id)


def get_tunnel_ingress(cf: CloudflareApi, account_id: str, tunnel_id: str,
                       tunnel_config_cache: Optional[Dict] = None) -> List:
    def _get_tunnel_ingress():
        tunnel_ingress = cf.get_tunnel_configs(account_id, tunnel_id)
        if tunnel_ingress is None:
            raise Exception(f'Could not find tunnel ingress for account "{account_id}" and tunnel "{tunnel_id}"')
        return (tunnel_ingress.get('config') or {}).get('ingress') or [{'service': 'http_status:404'}]

    return get_from_cache(tunnel_config_cache, _get_tunnel_ingress, account_id, tunnel_id)


def container_add(cf: CloudflareApi, account_id: str, params: Params, new_cnames: Dict[str, Params],
                  ingress_adds: Dict, cnames_by_zone_id: Optional[Dict] = None,
                  tunnel_ingress_cache: Optional[Dict] = None):
    cnames = get_cnames(cf, params.zone_id, cnames_by_zone_id)
    if params.hostname in cnames:
        LOGGER.info('CNAME "%s" already exists', params.hostname)
    elif params.hostname in new_cnames:
        LOGGER.error('duplicate CNAME "%s"', params.hostname)
    else:
        new_cnames[params.hostname] = params

    tunnel_ingress = get_tunnel_ingress(cf, account_id, params.tunnel_id, tunnel_ingress_cache)
    if ingress_exists(params, tunnel_ingress):
        LOGGER.info('Public hostname "%s" for tunnel "%s" already exists', params.hostname, params.tunnel_id)
    else:
        add_tunnel_ingress(params, tunnel_ingress)
        ingress_adds[(account_id, params.tunnel_id)] = tunnel_ingress

    return new_cnames, ingress_adds


def containers_update_cf(args: argparse.Namespace, cf: CloudflareApi, new_cnames: Dict[str, Params],
                         ingress_adds: Dict):
    for cname, params in new_cnames.items():
        val = tunnel_cname(params.tunnel_id)
        LOGGER.info(f'Adding CNAME "%s" -> "%s"', cname, val)
        if not args.dry_run:
            if not cf.create_cname(params.zone_id, cname, val):
                LOGGER.error('Failed to add cname "%s"', cname)

    for keys, tunnel_ingress in ingress_adds.items():
        if not args.dry_run:
            if not cf.update_tunnel_configs(keys[0], keys[1],
                                            {'config': {'ingress': tunnel_ingress}}):
                LOGGER.error(f'Failed to update tunnel ingress for tunnel "{keys[1]}" failed')


def load_containers(args: argparse.Namespace, containers: List, cf: CloudflareApi, cf_account_id: str,
                    cf_tunnel_id: str):
    tunnel_ingress_cache = {}
    cnames_by_zone_id = {}
    zone_name_to_id = {}
    new_cnames = {}
    ingress_adds = {}
    for container in containers:
        LOGGER.debug('inspecting container "%s"', container.name)
        if container.status != 'running':
            continue
        labels = get_labels(container.labels)
        if not labels:
            continue
        try:
            params = get_params_from_labels(cf, cf_tunnel_id, labels, zone_name_to_id)
            container_add(cf, cf_account_id, params, new_cnames, ingress_adds, cnames_by_zone_id,
                          tunnel_ingress_cache)
        except Exception as exc:
            LOGGER.error('%s: %s', container.name, exc)

    containers_update_cf(args, cf, new_cnames, ingress_adds)


def handle_start_event(args: argparse.Namespace, cf: CloudflareApi, cf_account_id: str, params: Params):
    new_cnames, ingress_adds = container_add(cf, cf_account_id, params, {}, {})
    containers_update_cf(args, cf, new_cnames, ingress_adds)


def handle_stop_event(args: argparse.Namespace, cf: CloudflareApi, account_id: str, params: Params):
    LOGGER.info(f'Removing CNAME "%s" for tunnel "%s"', params.hostname, params.tunnel_id)
    record_id = cf.get_dns_record_id(params.zone_id, params.hostname)
    if record_id:
        if not args.dry_run:
            if not cf.delete_cname(params.zone_id, record_id):
                LOGGER.error('Failed to remove CNAME "%s" for tunnel "%s"', params.hostname, params.tunnel_id)
    else:
        LOGGER.warning('No CNAME "%s" for tunnel "%s"', params.hostname, params.tunnel_id)

    LOGGER.info(f'Removing public hostname "%s" for tunnel "%s"', params.hostname, params.tunnel_id)
    tunnel_ingress = get_tunnel_ingress(cf, account_id, params.tunnel_id)
    before_len = len(tunnel_ingress)
    tunnel_ingress = [ii for ii in tunnel_ingress if ii.get('hostname') != params.hostname]
    if before_len > len(tunnel_ingress) and not args.dry_run:
        if not cf.update_tunnel_configs(account_id, params.tunnel_id,
                                        {'config': {'ingress': tunnel_ingress}}):
            LOGGER.error('Failed to remove public hostname "%s" for tunnel "%s"', params.hostname, params.tunnel_id)
    else:
        LOGGER.warning('No public hostname "%s" for tunnel "%s"', params.hostname, params.tunnel_id)


def main(args: argparse.Namespace):
    events = None

    try:
        cf_account_id, cf_token, cf_tunnel_id = get_env_vars()

        cf = CloudflareApi(cf_token, debug=pargs.debug)
        client = docker.from_env()

        queue = SimpleQueue()
        events = client.events(decode=True)
        thread = Thread(target=docker_events_thread, args=(events, queue), name='docker_events')
        thread.start()

        LOGGER.info('Using tunnel ID "%s" as default tunnel', cf_tunnel_id)

        try:
            load_containers(args, client.containers.list(all=True), cf, cf_account_id, cf_tunnel_id)
        except Exception as exc:
            LOGGER.critical('%s', exc)
            raise SystemExit(1)

        while True:
            event = queue.get()

            try:
                status = event['status']
                attributes = event['Actor']['Attributes']
                labels = get_labels(attributes)
                if not labels:
                    continue

                container_name = attributes["name"]
                try:
                    LOGGER.info('docker event "%s" for container "%s"', status, container_name)
                    params = get_params_from_labels(cf, cf_tunnel_id, labels)
                    if status == 'start':
                        handle_start_event(args, cf, cf_account_id, params)
                    elif status == 'die':
                        handle_stop_event(args, cf, cf_account_id, params)
                except Exception as exc:
                    LOGGER.exception('%s: %s', container_name, exc)
            except Exception:
                LOGGER.exception('invalid event')
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        LOGGER.critical('failed: %s', exc)
    finally:
        if events:
            events.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Read docker container labels and automatically add hostnames and CNAMEs to Cloudflare Zero Trust')
    parser.add_argument('-l', '--log-level', choices=('notset', 'debug', 'info', 'warning', 'error', 'critical'),
                        default='info', help='set the log level [info]')
    parser.add_argument('-d', '--dry-run', action='store_true',
                        help="don't run Cloudflare APIs that modify")
    parser.add_argument('--debug', action='store_true',
                        help='turn on Cloudflare API debug')
    pargs = parser.parse_args()

    pargs.log_level = getattr(logging, pargs.log_level.upper())

    logging.basicConfig(level=logging.DEBUG if pargs.debug else logging.INFO)
    LOGGER.setLevel(pargs.log_level)
    main(pargs)
