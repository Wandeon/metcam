# Bug Tracking & Reporting - W48
## Automated Issue Tracking System

## Overview
Automated bug reporting and crash analysis system for FootballVision Pro.

## Components

### 1. Issue Templates
GitHub issue templates for standardized bug reporting:
- Bug Report Template
- Feature Request Template
- Performance Issue Template

### 2. Crash Reporter
Automatic crash dump collection and reporting:
```python
from tools.bug_reporting.crash_reporter import handle_crash

try:
    # Your code
    pass
except Exception as e:
    handle_crash(e)
```

### 3. Log Aggregation
Centralized logging from all components:
- System logs (systemd)
- Application logs
- Kernel logs
- Performance logs

## Bug Priority Levels

### P0 - Critical
- Recording fails
- Data loss
- System crash
- **SLA**: Fix within 24 hours

### P1 - High
- Degraded quality
- Performance issues
- Workaround available
- **SLA**: Fix within 1 week

### P2 - Medium
- Minor functional issues
- Cosmetic problems
- **SLA**: Fix within 1 month

### P3 - Low
- Enhancement requests
- Documentation updates
- **SLA**: Backlog

## Reporting a Bug

### Via GitHub
1. Go to Issues tab
2. Click "New Issue"
3. Select "Bug Report" template
4. Fill in all sections
5. Attach logs/screenshots

### Via Crash Reporter
Automatic crash reports are generated and saved to:
```
/var/log/footballvision/crashes/CRASH-YYYYMMDD-HHMMSS.json
```

Send to: support@footballvision.com

## Analyzing Crash Reports

### View Crash Report
```bash
cat /var/log/footballvision/crashes/CRASH-*.json | jq
```

### Extract Logs
```bash
# System logs
journalctl -u footballvision.service -n 1000

# Application logs
tail -f /var/log/footballvision/app.log

# Crash dumps
ls -lt /var/log/footballvision/crashes/
```

## Bug Metrics

Track and analyze:
- Bug discovery rate
- Bug fix rate
- Bug escape rate (found in production)
- Mean time to resolution (MTTR)
- Bug density (per KLOC)

## Version History
- **v1.0** (2025-09-30): Initial bug tracking system - W48