FROM docker.elastic.co/kibana/kibana:9.0.2

# Copy the dashboard and import script
COPY infra/observability/kibana/dashboards/default-dashboard.ndjson /usr/share/kibana/dashboards/default-dashboard.ndjson
COPY infra/observability/kibana/import-dashboard.sh /usr/share/kibana/import-dashboard.sh

# Set permissions for the import script
USER root
RUN chmod +x /usr/share/kibana/import-dashboard.sh

# Create necessary directories
RUN mkdir -p /usr/share/kibana/logs

# Switch back to kibana user
USER kibana

# Run the import script in the background after kibana starts
CMD ["/bin/bash", "-c", "/usr/share/kibana/import-dashboard.sh & /usr/local/bin/kibana-docker"] 