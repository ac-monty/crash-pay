#!/bin/bash

# Wait for Kibana to be ready
echo "Waiting for Kibana to be available..."
until curl -s http://localhost:5601/api/status | grep -q '"level":"available"'; do
  echo "Waiting for Kibana..."
  sleep 5
done

echo "Kibana is up. Importing dashboard..."

# Import the dashboard (no authentication needed)
curl -X POST "http://localhost:5601/api/saved_objects/_import" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/ndjson" \
  --data-binary "@/usr/share/kibana/dashboards/default-dashboard.ndjson"

echo "Dashboard import finished." 