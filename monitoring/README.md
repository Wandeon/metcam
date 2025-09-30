# Monitoring & Telemetry - W47
## FootballVision Pro Monitoring System

## Overview
Comprehensive monitoring and alerting system using Prometheus and Grafana for real-time system health tracking.

## Components

### Prometheus (Metrics Collection)
- System metrics (CPU, RAM, temperature)
- Recording metrics (frames, drops, bitrate)
- Network metrics (bandwidth, errors)
- Storage metrics (available, throughput)

### Grafana (Visualization)
- System Health Dashboard
- Recording Statistics
- Performance Trends
- Historical Analysis

### AlertManager (Alerting)
- Critical alerts (frame drops, failures)
- Warning alerts (temperature, storage)
- Email/SMS/Webhook notifications

## Metrics Exposed

### Recording Metrics
```
recording_duration_seconds         # Current recording duration
frames_captured_total             # Total frames captured
frames_dropped_total              # Total frames dropped
bitrate_mbps                      # Current bitrate
recording_status                  # 1=active, 0=inactive
```

### System Metrics
```
cpu_temperature_celsius           # CPU temperature
gpu_utilization_percent           # GPU usage
memory_usage_bytes                # RAM usage
storage_available_bytes           # Available storage
```

### Network Metrics
```
upload_bandwidth_mbps             # Upload speed
network_errors_total              # Network errors
api_request_duration_seconds      # API latency
network_connected                 # 1=connected, 0=disconnected
```

## Setup

### Install Prometheus
```bash
sudo apt-get install prometheus
sudo cp monitoring/prometheus/prometheus.yml /etc/prometheus/
sudo systemctl restart prometheus
```

### Install Grafana
```bash
sudo apt-get install grafana
sudo systemctl start grafana-server
# Access: http://localhost:3000
```

### Import Dashboards
```bash
# Import system health dashboard
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @monitoring/grafana/dashboards/system_health.json
```

## Alert Configuration

### Email Alerts
Edit `/etc/alertmanager/alertmanager.yml`:
```yaml
receivers:
  - name: 'email'
    email_configs:
      - to: 'support@footballvision.com'
        from: 'alerts@footballvision.com'
```

### Critical Alert Rules
- Frame drops > 0 for 30 seconds
- Temperature > 80°C for 1 minute
- Storage < 10GB for 1 minute
- Recording failed for 1 minute

## Accessing Monitoring

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Metrics Endpoint**: http://localhost:8000/metrics

## Dashboards

### System Health Dashboard
- Real-time recording status
- Temperature monitoring
- Frame rate graph
- Resource utilization

### Recording Statistics
- Total recordings
- Success rate
- Average duration
- Processing queue

### Performance Trends
- Historical metrics
- Performance degradation detection
- Capacity planning

## Version History
- **v1.0** (2025-09-30): Initial monitoring system - W47