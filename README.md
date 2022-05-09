# Automatically add CloudFlare Zero Trust public hostnames using docker labels

## Usage

```
docker run -d \
    --name=cloudflare-manager \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e CLOUDFLARE_TUNNEL_ID=<TUNNEL_ID> \
    -e CLOUDFLARE_API_KEY=<API_KEY> \
    -e CLOUDFLARE_ACCOUNT_ID=<ACCOUNT_ID> \
    fhriley/cloudflare-manager
```

### Environment Variables

To customize some properties of the container, the following environment
variables can be passed via the `-e` parameter (one for each variable).  Value
of this parameter has the format `<VARIABLE_NAME>=<VALUE>`.

| Variable       | Description                                  |
|----------------|----------------------------------------------|
|`CLOUDFLARE_TUNNEL_ID`| Tunnel ID used when a tunnel is not specified by label. |
|`CLOUDFLARE_API_KEY`| API token for connecting to the Cloudflare API. This token should have `Account:Cloudflare Tunnel:Edit` and `Zone:DNS:Edit` permissions. |
|`CLOUDFLARE_ACCOUNT_ID`| Cloudflare account ID that owns the tunnel. |

### Docker Labels

| Label       | Description                                  |Required| Example |
|-------------|----------------------------------------------|-----|-|
|`cloudflare.zero_trust.access.tunnel.public_hostname`|Public hostname to add to the tunnel.|Yes|`service.domain.com`|
|`cloudflare.zero_trust.access.tunnel.service`|Service the hostname will proxy to.|Yes|`http://192.168.1.100:8000`|
|`cloudflare.zero_trust.access.tunnel.id`|Tunnel ID to add the hostname to.|No|`423971df-7091-4ed9-85e8-25bb598776ab`|
|`cloudflare.zero_trust.access.tunnel.tls.notlsverify`|Turn off TLS verification for the origin service.|No|`true`|

### Example

A fully working docker compose example can be found [here](https://github.com/fhriley/cloudflare-manager/tree/main/example).
