import argparse
import logging
import os
from queue import SimpleQueue
from threading import Thread

import docker
from docker.types.daemon import CancellableStream

from .cloudflare_api import CloudflareApi
from .api import Api, CachedApi
from .labels import get_params_from_labels
from .params import Params
from .tunnel import Tunnel
from .zone import Zone

LOGGER = logging.getLogger('cfd-hostnames')


def docker_events_thread(events: CancellableStream, queue: SimpleQueue):
    for event in events:
        status = event.get('status')
        if event.get('Type') == 'container' and status in ('start', 'die'):
            queue.put(event)


def get_env_vars() -> list[str]:
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


def get_labels(labels: dict[str, str]):
    return {key: val for key, val in labels.items() if key.startswith('cloudflare.')}


def handle_start_event(zones: dict[str, Zone], tunnels: dict[str, Tunnel], params: Params):
    zone = zones.get(params.zone_id) or Zone(params.api, params.account_id, params.zone_id)
    zones[params.zone_id] = zone
    params.add_to_zone(zone)
    params.add_to_tunnel(tunnels)


def handle_die_event(zones: dict[str, Zone], tunnels: dict[str, Tunnel], params: Params):
    zone = zones.get(params.zone_id) or Zone(params.api, params.account_id, params.zone_id)
    zones[params.zone_id] = zone
    params.remove_from_zone(zone)
    params.remove_from_tunnel(tunnels)


def update_cloudflare(args: argparse.Namespace, zones: dict[str, Zone], tunnels: dict[str, Tunnel]):
    for zone in zones.values():
        zone.update_cloudflare(args)

    for tunnel in tunnels.values():
        tunnel.update_cloudflare(args)


def load_containers(args: argparse.Namespace, containers: list, api: Api, cf_account_id: str,
                    cf_tunnel_id: str):
    zones: dict[str, Zone] = {}
    tunnels: dict[str, Tunnel] = {}
    for container in containers:
        LOGGER.debug('inspecting container "%s"', container.name)
        if container.status != 'running':
            continue
        labels = get_labels(container.labels)
        if not labels:
            continue
        try:
            params = get_params_from_labels(api, cf_account_id, cf_tunnel_id, labels)
            for pp in params:
                try:
                    handle_start_event(zones, tunnels, pp)
                except Exception as exc:
                    LOGGER.exception('%s (%s): %s', container.name, pp, exc)
        except Exception as exc:
            LOGGER.error('%s: %s', container.name, exc)

    update_cloudflare(args, zones, tunnels)


def main(args: argparse.Namespace):
    docker_events = None

    try:
        cf_account_id, cf_token, cf_tunnel_id = get_env_vars()

        cf = CloudflareApi(cf_token, debug=pargs.debug)
        docker_client = docker.from_env()

        queue = SimpleQueue()
        docker_events = docker_client.events(decode=True)
        thread = Thread(target=docker_events_thread, args=(docker_events, queue), name='docker_events')
        thread.start()

        LOGGER.info('Using tunnel ID "%s" as default tunnel', cf_tunnel_id)

        try:
            api = CachedApi(cf)
            load_containers(args, docker_client.containers.list(all=True), api, cf_account_id, cf_tunnel_id)
        except Exception as exc:
            LOGGER.critical('%s', exc)
            raise SystemExit(1)

        while True:
            event = queue.get()
            api = CachedApi(cf)
            zones: dict[str, Zone] = {}
            tunnels: dict[str, Tunnel] = {}

            try:
                status = event['status']
                attributes = event['Actor']['Attributes']
                labels = get_labels(attributes)
                if not labels:
                    continue

                container_name = attributes["name"]
                LOGGER.info('docker event "%s" for container "%s"', status, container_name)

                try:
                    params = get_params_from_labels(api, cf_account_id, cf_tunnel_id, labels)
                except Exception as exc:
                    LOGGER.exception('%s: %s', container_name, exc)
                    continue

                if status == 'start':
                    for pp in params:
                        try:
                            handle_start_event(zones, tunnels, pp)
                        except Exception as exc:
                            LOGGER.exception('%s (%s): %s', container_name, pp, exc)
                elif status == 'die':
                    for pp in params:
                        try:
                            handle_die_event(zones, tunnels, pp)
                        except Exception as exc:
                            LOGGER.exception('%s (%s): %s', container_name, pp, exc)

                update_cloudflare(args, zones, tunnels)

            except Exception as exc:
                LOGGER.exception('invalid event: %s', exc)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        LOGGER.critical('failed: %s', exc)
    finally:
        if docker_events:
            docker_events.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Read docker container labels and automatically add hostnames '
                                                 'and DNS records to Cloudflare Zero Trust')
    parser.add_argument('-l', '--log-level', choices=('notset', 'debug', 'info', 'warning', 'error', 'critical'),
                        default='info', help='set the log level [info]')
    parser.add_argument('-d', '--dry-run', action='store_true',
                        help="don't run Cloudflare APIs that modify")
    parser.add_argument('--debug', action='store_true',
                        help='turn on Cloudflare API debug')
    pargs = parser.parse_args()

    pargs.log_level = getattr(logging, pargs.log_level.upper())

    logging.basicConfig(level=logging.DEBUG if pargs.debug else logging.INFO,
                        format='%(asctime)s|%(name)s|%(levelname)s|%(message)s')
    LOGGER.setLevel(pargs.log_level)
    main(pargs)
