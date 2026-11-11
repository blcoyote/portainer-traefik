# Observability stack

Grafana for dashboards, VictoriaMetrics for metrics (90 days), VictoriaLogs for logs (30 days),
VictoriaTraces for traces (30 days), and Grafana Alloy as the single collector. Everything is provisioned from this directory.

```
 any container ── stdout/stderr ──────────────┐
 labelled container ── /metrics (scraped) ────┤
 instrumented app ── OTLP :4317 / :4318 ──────┤
                                              ▼
                                            alloy ──► victoriametrics ─┐
                                                  ├─► victorialogs ────┤
                                                  └─► victoriatraces ──┤
                                                                       ▼
                         GRAFANA_BIND:3000 ◄──────────────────────── grafana
```

| Service | Purpose | Reachable at |
|---|---|---|
| `grafana` | Dashboards | `${GRAFANA_BIND}:3000` (LAN/Tailscale only, no Traefik route) |
| `victoriametrics` | Metrics store (Prometheus-compatible) | `victoriametrics:8428` on `observability` |
| `victorialogs` | Log store | `victorialogs:9428` on `observability` |
| `victoriatraces` | Trace store (OTLP ingest, Jaeger query API) | `victoriatraces:10428` on `observability` |
| `alloy` | Collector | `alloy:4317` (OTLP gRPC), `alloy:4318` (OTLP HTTP) on `observability` |
| `socket-proxy` | Read-only Docker API for Alloy | internal network only |

## First deploy

1. On the host: `docker network create observability`
2. In Portainer, create a stack from this repo with compose path `observability/docker-compose.yml`
   and set the variables from [`.env.example`](.env.example). `GRAFANA_ADMIN_PASSWORD` is required;
   the stack refuses to start without it.
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

**Metrics, logs and traces, pushed (OpenTelemetry).** Point the OTel SDK at Alloy:

```yaml
    environment:
      OTEL_EXPORTER_OTLP_ENDPOINT: http://alloy:4318
      OTEL_EXPORTER_OTLP_PROTOCOL: http/protobuf
      OTEL_SERVICE_NAME: my-app
```

## Dashboards

- **Dashboards:** JSON files in [`grafana/dashboards/`](grafana/dashboards/); subfolders become folders.
- **Datasource UIDs:** `victoriametrics` (Prometheus type, MetricsQL/PromQL), `victorialogs` (LogsQL) and `victoriatraces` (Jaeger type, VictoriaTraces' Jaeger query API).

Provisioned items are read-only in the UI. Make changes in Grafana, export them, and commit the file.

Alerting is switched off for now (`GF_UNIFIED_ALERTING_ENABLED: "false"` in the compose file).

## Querying

- Logs: `{container="grafana"} error`, or `compose_project:observability` in LogsQL.
- Metrics: `up` lists every scrape target (1 = up, 0 = down).

- Log to trace: app logs are JSON lines with `trace_id`. The VictoriaLogs datasource has a `trace_id` derived field
  (regex on the raw line), so log lines in Explore show a link that opens the trace in VictoriaTraces.
- Trace to logs: open a trace in the VictoriaTraces datasource and use the span's "Logs" button; it runs a
  VictoriaLogs query for lines containing the trace id (span time +/- 5 minutes). Equivalent by hand:
  `{compose_service="app"} | unpack_json | trace_id:="<id>"`.

## Verifying traces

Post a minimal OTLP/JSON span to Alloy from a container on the network, then read it back from
VictoriaTraces' Jaeger API (give it a few seconds to flush):

```bash
NOW=$(date +%s%N)
docker run --rm --network observability curlimages/curl -sS -X POST http://alloy:4318/v1/traces \
  -H 'Content-Type: application/json' -d '{
  "resourceSpans": [{
    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "smoke-test"}}]},
    "scopeSpans": [{
      "scope": {"name": "manual"},
      "spans": [{
        "traceId": "5b8efff798038103d269b633813fc60c",
        "spanId": "eee19b7ec3c1b174",
        "name": "hello",
        "kind": 1,
        "startTimeUnixNano": "'"$NOW"'",
        "endTimeUnixNano": "'"$((NOW + 1000000000))"'"
      }]
    }]
  }]
}'

docker run --rm --network observability curlimages/curl -sS http://victoriatraces:10428/select/jaeger/api/services
docker run --rm --network observability curlimages/curl -sS \
  http://victoriatraces:10428/select/jaeger/api/traces/5b8efff798038103d269b633813fc60c
```

`smoke-test` should appear in the services list. The span is stamped with the current time
because VictoriaTraces rejects spans outside `TRACES_RETENTION`.
