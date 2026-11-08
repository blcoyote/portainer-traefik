# Observability stack

Grafana for dashboards and alerting, VictoriaMetrics for metrics (90 days), VictoriaLogs for logs (30 days),
and Grafana Alloy as the single collector. Everything is provisioned from this directory.

```
 any container ── stdout/stderr ──────────────┐
 labelled container ── /metrics (scraped) ────┤
 instrumented app ── OTLP :4317 / :4318 ──────┤
                                              ▼
                                            alloy ──► victoriametrics ─┐
                                                  └─► victorialogs ────┤
                                                                       ▼
                         GRAFANA_BIND:3000 ◄──────────────────────── grafana ──► Telegram
```

| Service | Purpose | Reachable at |
|---|---|---|
| `grafana` | Dashboards, alerting | `${GRAFANA_BIND}:3000` (LAN/Tailscale only, no Traefik route) |
| `victoriametrics` | Metrics store (Prometheus-compatible) | `victoriametrics:8428` on `observability` |
| `victorialogs` | Log store | `victorialogs:9428` on `observability` |
| `alloy` | Collector | `alloy:4317` (OTLP gRPC), `alloy:4318` (OTLP HTTP) on `observability` |
| `socket-proxy` | Read-only Docker API for Alloy | internal network only |

## First deploy

1. On the host: `docker network create observability`
2. In Portainer, create a stack from this repo with compose path `observability/docker-compose.yml`
   and set the variables from [`.env.example`](.env.example). `GRAFANA_ADMIN_PASSWORD`,
   `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are required; the stack refuses to start without them.
3. Set `GRAFANA_BIND` to the host's LAN or Tailscale IP, then open `http://<that IP>:3000`.

Grafana downloads the VictoriaLogs datasource plugin from grafana.com on first start, so the host
needs internet access then. The plugin is kept in the `grafana-data` volume afterwards.

## Connecting a service

Join the service to the `observability` network:

```yaml
services:
  my-app:
    networks:
      - observability

networks:
  observability:
    external: true
```

Then pick one or both of these:

**Logs: nothing to do.** Alloy collects stdout/stderr from every container on the host, whether or not
it is on the network. Opt out with the label `logs.collect: "false"`.

**Metrics, scraped.** If the app exposes Prometheus metrics, add labels:

```yaml
    labels:
      metrics.scrape: "true"
      metrics.port: "8080"        # required
      metrics.path: "/metrics"    # optional, default /metrics
      metrics.job: "my-app"       # optional, default compose service name
```

**Metrics and logs, pushed (OpenTelemetry).** Point the OTel SDK at Alloy:

```yaml
    environment:
      OTEL_EXPORTER_OTLP_ENDPOINT: http://alloy:4318
      OTEL_EXPORTER_OTLP_PROTOCOL: http/protobuf
      OTEL_SERVICE_NAME: my-app
      OTEL_TRACES_EXPORTER: none   # no traces backend in this stack
```

## Dashboards and alerts

- **Dashboards:** JSON files in [`grafana/dashboards/`](grafana/dashboards/); subfolders become folders.
- **Alert rules:** YAML files in [`grafana/provisioning/alerting/`](grafana/provisioning/alerting/).
  Every alert goes to the Telegram contact point. No rules are defined yet.
- **Datasource UIDs:** `victoriametrics` (Prometheus type, MetricsQL/PromQL) and `victorialogs` (LogsQL).

Provisioned items are read-only in the UI. Make changes in Grafana, export them, and commit the file.

## Querying

- Logs: `{container="grafana"} error`, or `compose_project:observability` in LogsQL.
- Metrics: `up` lists every scrape target; `up == 0` is a good first alert.
