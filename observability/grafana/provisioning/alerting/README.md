# Alert rules

Grafana loads every `*.yml` / `*.yaml` file in this directory at startup. Add alert rules as files here,
e.g. `rules-<area>.yml`, so they are version-controlled and come back on every redeploy.

The easiest way to write one: build the rule in the Grafana UI, then use **Export** (Alerting → Alert rules →
rule → More → Export, format YAML), save it here and delete the UI copy.

Minimal shape:

```yaml
apiVersion: 1
groups:
  - orgId: 1
    name: example
    folder: Infrastructure
    interval: 1m
    rules:
      - uid: example-rule
        title: Example
        condition: C
        data:
          - refId: A
            datasourceUid: victoriametrics
            relativeTimeRange: { from: 300, to: 0 }
            model:
              expr: up   # 1 = up, 0 = down; C fires below 1
              instant: true
          - refId: C
            datasourceUid: __expr__
            model:
              type: threshold
              expression: A
              conditions:
                - evaluator: { type: lt, params: [1] }
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.job }} is down"
```

All alerts route to the `telegram` contact point (see `contact-points.yml`).
