# CloudWatch Logs Insights Queries

Useful saved queries for the application log group `/bootcamp-project/dev/app`, which aggregates container logs from all instances (one stream per instance).

Run these in the CloudWatch console (Logs → Logs Insights → select the log group), or via the CLI with `aws logs start-query`.

## Recent activity (all log lines, newest first)

```
fields @timestamp, @message, @logStream
| sort @timestamp desc
| limit 100
```

## Errors and warnings only

```
fields @timestamp, @message, @logStream
| filter @message like /(?i)(error|exception|traceback|critical|warn)/
| sort @timestamp desc
| limit 50
```

## HTTP 5xx responses (server errors)

```
fields @timestamp, @message
| filter @message like / 5\d\d /
| sort @timestamp desc
| limit 50
```

## Request volume over time (per 5-minute bucket)

```
fields @timestamp
| filter @message like /GET|POST/
| stats count(*) as requests by bin(5m)
```

## Activity per instance (which stream is serving traffic)

```
fields @logStream
| stats count(*) as logLines by @logStream
| sort logLines desc
```

## Gunicorn worker startups (deployment / restart signal)

```
fields @timestamp, @message, @logStream
| filter @message like /Booting worker|Starting gunicorn|Listening at/
| sort @timestamp desc
| limit 50
```

## Health-check requests

```
fields @timestamp, @logStream
| filter @message like /\/health/
| stats count(*) as healthChecks by bin(1m)
```

## CLI example

```bash
aws logs start-query \
  --log-group-name /bootcamp-project/dev/app \
  --start-time $(date -v-1H +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /error/ | sort @timestamp desc | limit 20' \
  --region eu-central-1
```
(Then retrieve results with `aws logs get-query-results --query-id <id>`.)
