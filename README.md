# Traefik & Portainer Docker Compose Stack

Reverse proxy with automatic Let's Encrypt SSL (Traefik) and container management UI (Portainer) for apps.

## Prerequisites

- Docker and Docker Compose installed and running
- Public DNS for (and subdomains) pointing to the host
- Ports 80 and 443 open on the host firewall

## Quick start

```bash
./setup.sh
docker compose up -d
```

The setup script will:
- Verify Docker is installed and running
- Warn if ports 80/443 are already in use
- Create the `proxy` Docker network
- Create `traefik/acme.json` with correct permissions (mode 600)
- Create the `portainer/data/` directory

## Accessing services

| Service | URL | Access |
|---------|-----|--------|
| Traefik dashboard | `http://localhost:8080` | Local only (127.0.0.1) |
| Portainer | `https://localhost:9443` | Local only (127.0.0.1) |

**Portainer first login**: On first access, Portainer requires you to set an admin password. This must be done within a few minutes of the container starting. If you miss the window, restart the Portainer container: `docker compose restart portainer`.

## Adding a new service

Any service on the `proxy` network can opt into Traefik routing with Docker labels. Here is a complete example using the `whoami` test service:

```yaml
# In a separate docker-compose.yml or deployed via Portainer
services:
  whoami:
    image: traefik/whoami
    container_name: whoami
    restart: unless-stopped
    networks:
      - proxy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.whoami.rule=Host(`whoami.mysite.com`)"
      - "traefik.http.routers.whoami.entrypoints=websecure"
      - "traefik.http.routers.whoami.tls.certresolver=letsencrypt"

networks:
  proxy:
    external: true
```

**Required labels for any service:**

| Label | Purpose |
|-------|---------|
| `traefik.enable=true` | Enables Traefik discovery for this container |
| `traefik.http.routers.<name>.rule=Host(...)` | Routes traffic for the given hostname |
| `traefik.http.routers.<name>.entrypoints=websecure` | Uses the HTTPS entrypoint |
| `traefik.http.routers.<name>.tls.certresolver=letsencrypt` | Obtains a Let's Encrypt certificate |

**Requirements:**
- The service must be on the `proxy` network
- DNS for the subdomain must point to the host
- `traefik.enable=true` must be set (services are not exposed by default)

## Configuration overview

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Service definitions, port bindings, volumes, network |
| `traefik/traefik.yml` | Traefik static config: entrypoints, ACME resolver, Docker provider |
| `traefik/acme.json` | Let's Encrypt certificate storage (auto-managed by Traefik) |
| `portainer/data/` | Portainer persistent database and config |

Traefik configuration is split in two:
- **Static config** (`traefik/traefik.yml`): entrypoints, certificate resolvers, providers. Changes require a Traefik restart.
- **Dynamic config** (Docker labels): per-service routing rules. Traefik picks these up automatically — no restart needed.

## Tailscale VPN

`tailscale/docker-compose.yml` runs a Tailscale VPN gateway for mobile devices. Phones and laptops running the Tailscale app connect to it from anywhere and are routed into the **physical local network** (NAS, printers, router, other hosts) — not just the Docker networks. It can optionally act as an exit node so all mobile traffic goes out through your home connection.

```
phone (Tailscale app) ──tailnet──▶ tailscale container (host network) ──▶ LAN 192.168.1.0/24
```

### Configuration

Set these in `tailscale/.env` (or in the Portainer stack environment):

| Variable | Default | Purpose |
|----------|---------|---------|
| `TS_AUTHKEY` | — (required) | Auth key from the Tailscale admin console (Settings → Keys). Use a reusable or non-expiring key for a server |
| `TS_HOSTNAME` | `homelab-vpn` | Machine name shown in the tailnet |
| `TS_ROUTES` | `192.168.1.0/24` | Your LAN subnet(s) to expose to mobile clients, comma-separated |
| `TS_EXTRA_ARGS` | `--advertise-exit-node` | Extra `tailscale up` flags. Set to empty to disable the exit node |

### Host setup

The host kernel forwards VPN traffic onto the LAN, so IP forwarding must be enabled:

```bash
echo 'net.ipv4.ip_forward = 1' | sudo tee /etc/sysctl.d/99-tailscale.conf
echo 'net.ipv6.conf.all.forwarding = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf
sudo sysctl -p /etc/sysctl.d/99-tailscale.conf
```

### Start and approve

```bash
cd tailscale && docker compose up -d
```

In the [Tailscale admin console](https://login.tailscale.com/admin/machines), open the machine → **Edit route settings** and approve the subnet route (and exit node, if wanted). Optionally disable key expiry for the machine so the server never drops off.

### Connect a mobile device

1. Install the Tailscale app (iOS / Android) and sign in to the same tailnet.
2. Turn the VPN on — LAN addresses like `192.168.1.x` are now reachable from anywhere.
3. To route *all* traffic through home, pick this machine under **Exit node** in the app.

Tip: to use Pi-hole for VPN clients, add the host's LAN IP as a nameserver under **DNS** in the admin console and enable **Override local DNS**.

### Notes

- Client traffic is SNAT'ed to the host's LAN IP, so other LAN devices need no extra routes.
- The container has no web UI, so it carries `traefik.enable=false` (like Pi-hole). Services behind Traefik are reachable over the VPN at the host's LAN IP.
- Docker sets the host's iptables `FORWARD` policy to `DROP`. Tailscale inserts its own `ts-forward` chain into `FORWARD`, which accepts VPN traffic and marks it for SNAT in `ts-postrouting`. If clients connect but cannot reach the LAN, check that those rules are present:

  ```bash
  sudo iptables -S FORWARD | grep ts-forward
  sudo iptables -t nat -S POSTROUTING | grep ts-postrouting
  ```

  If they are missing (e.g. Docker was restarted after Tailscale and flushed them), restart the container so Tailscale re-installs them: `docker compose restart tailscale`. Avoid adding a blanket `ACCEPT` for `tailscale0` in `DOCKER-USER` — it would short-circuit `ts-forward`, skipping the SNAT mark so LAN devices could not reply.

## Troubleshooting

### Check Traefik logs

```bash
docker compose logs traefik
docker compose logs -f traefik   # follow live
```

### Verify certificate status

Check if `acme.json` has certificate data:

```bash
cat traefik/acme.json | python3 -m json.tool | head -30
```

If the file is empty or contains errors, Traefik could not obtain a certificate. Common causes:
- DNS for the domain does not point to this host
- Port 80 is blocked (required for HTTP-01 challenge)
- Let's Encrypt rate limit reached (see staging server below)

### Switch to Let's Encrypt staging server

To avoid rate limits during testing, edit `traefik/traefik.yml` and uncomment the `caServer` line:

```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      caServer: https://acme-staging-v02.api.letsencrypt.org/directory
```

Then restart Traefik and clear the existing ACME data:

```bash
docker compose down
> traefik/acme.json   # truncate the file
chmod 600 traefik/acme.json
docker compose up -d
```

Staging certificates are not trusted by browsers but confirm that ACME is working. Switch back to production (comment out `caServer`) when ready.

### Reset ACME state

If certificates are corrupted or you need a fresh start:

```bash
docker compose down
> traefik/acme.json
chmod 600 traefik/acme.json
docker compose up -d
```

### Portainer locked out

If you missed the initial admin password window:

```bash
docker compose restart portainer
```

Then access `https://localhost:9443` immediately to set the password.

### Port already in use

If `setup.sh` warns about ports 80 or 443:

```bash
# Find what is using the port
sudo lsof -iTCP:80 -sTCP:LISTEN -P -n
sudo lsof -iTCP:443 -sTCP:LISTEN -P -n
```

Stop the conflicting service before starting the stack.

## Security notes

- **Docker socket**: Traefik mounts the Docker socket read-only to discover containers via labels. This gives Traefik visibility into all containers. For additional hardening, consider a Docker socket proxy like [tecnativa/docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy).
- **Portainer**: Has `traefik.enable=false` to prevent public exposure. Removing this label would expose Portainer through Traefik.
- **Dashboard**: Bound to `127.0.0.1:8080` — not accessible from the internet. Do not change this to `0.0.0.0`.
