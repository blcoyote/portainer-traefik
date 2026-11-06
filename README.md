# portainer-traefik

Docker Compose stacks for the home server, deployed through Portainer.

| Stack | Purpose |
|---|---|
| [traefik](traefik/) | Reverse proxy, TLS, geoblock, CrowdSec |
| [portainer](portainer/) | Container management |
| [observability](observability/) | Grafana, VictoriaMetrics, VictoriaLogs, Alloy; see its README |
| [tailscale](tailscale/) | Tailnet access and exit node |
| [pihole](pihole/) | DNS ad blocking |
| [homeautomation](homeautomation/) | Home Assistant |
| [frigate](frigate/) | NVR |
