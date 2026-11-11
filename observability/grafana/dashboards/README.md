# Dashboards

Put dashboard JSON files here; subfolders become Grafana folders. Grafana re-reads this directory every
60 seconds, but on Portainer a change only arrives after the stack is redeployed from git.

Provisioned dashboards can't be saved from the UI. To change one, edit it in Grafana, then use
**Share → Export → Save to file** and commit the JSON here.

Use the datasource UIDs `victoriametrics` and `victorialogs` in panels so imported dashboards resolve.

Dashboards: `camera-events-v2.json` (camera-events-v2 app: HTTP, MQTT, push, memory).
`camera-events-logs.json` (camera-events-v2 app logs: volume by level, top errors, filterable log view; pick env, level, component, camera, search).
`golden-signals.json` (generic Golden Signals: latency, traffic, errors, saturation for any OTel HTTP service; pick the job).
