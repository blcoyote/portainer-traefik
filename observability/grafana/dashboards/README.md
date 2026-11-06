# Dashboards

Put dashboard JSON files here; subfolders become Grafana folders. Grafana re-reads this directory every
60 seconds, but on Portainer a change only arrives after the stack is redeployed from git.

Provisioned dashboards can't be saved from the UI. To change one, edit it in Grafana, then use
**Share → Export → Save to file** and commit the JSON here.

Use the datasource UIDs `victoriametrics` and `victorialogs` in panels so imported dashboards resolve.
