# Understand-First Instrumentation & Metrics

Comprehensive instrumentation and metrics collection for the Understand-First platform, including anonymous opt-in event tracking, derived KPIs, TTU/TTFSC measurement, and performance monitoring.

## Features

- **Anonymous Event Tracking**: Opt-in event tracking with user privacy protection
- **TTU/TTFSC Measurement**: Track Time-to-Understanding and Time-to-First-Safe-Change metrics
- **Performance Monitoring**: Monitor operation duration, memory usage, and CPU utilization
- **Funnel Analysis**: Track user conversion through key workflows
- **Retry Analysis**: Monitor operation retries and failure patterns
- **Rage Click Detection**: Identify UI elements causing user frustration
- **KPI Dashboard**: Web-based dashboard for visualizing metrics
- **Data Export**: Export metrics in JSON and CSV formats

## Quick Start

### Using Docker

1. Build the Docker image:
   ```bash
   docker build -t understand-first/metrics .
   ```

2. Run the container:
   ```bash
   docker run -p 5001:5001 understand-first/metrics
   ```

3. Open your browser to `http://localhost:5001`

### Using Python

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the metrics dashboard:
   ```bash
   python metrics_dashboard.py
   ```

3. Open your browser to `http://localhost:5001`

## Usage

### Basic Event Tracking

```python
from understand_first_metrics import EventTracker

# Initialize tracker
tracker = EventTracker(opt_in=True)

# Track events
tracker.track_event("feature_used", {"feature": "code_map", "duration": 30})
tracker.track_ttu("code_analysis", 45.2, success=True)
tracker.track_ttfsc("bug_fix", 3600, success=True)
tracker.track_rage_click("export_button", 5)
tracker.track_retry("analysis", 3, "timeout")
```

### Performance Monitoring

```python
# Using context manager
with tracker.measure_performance("code_analysis"):
    # Your code here
    analyze_code()

# Manual tracking
tracker.track_performance(
    operation="file_upload",
    duration_ms=1500,
    memory_mb=128.5,
    cpu_percent=25.0,
    success=True
)
```

### Funnel Tracking

```python
# Track funnel steps
tracker.track_funnel_step("onboarding", "welcome", success=True)
tracker.track_funnel_step("onboarding", "tutorial", success=True)
tracker.track_funnel_step("onboarding", "first_analysis", success=False)
```

### Command Line Interface

```bash
# Export metrics
python understand_first_metrics.py --export metrics.json --format json

# View KPIs
python understand_first_metrics.py --days 30

# Enable/disable tracking
python understand_first_metrics.py --opt-in
python understand_first_metrics.py --opt-out
```

## Metrics Tracked

### Time-to-Understanding (TTU)

- **Average TTU**: Mean time to understand code
- **TTU Success Rate**: Percentage of successful understanding attempts
- **TTU Categories**: Excellent (≤10s), Good (≤30s), Acceptable (≤60s), Poor (>60s)

### Time-to-First-Safe-Change (TTFSC)

- **Average TTFSC**: Mean time to make first safe change
- **TTFSC Success Rate**: Percentage of successful change attempts
- **TTFSC Categories**: Excellent (≤1h), Good (≤1d), Acceptable (≤3d), Poor (>3d)

### Performance Metrics

- **Operation Duration**: Time taken for operations
- **Memory Usage**: Memory consumption during operations
- **CPU Utilization**: CPU usage during operations
- **Success Rate**: Percentage of successful operations

### User Experience Metrics

- **Rage Clicks**: Multiple clicks on same element
- **Retries**: Operation retry attempts
- **Funnel Conversion**: Step-by-step conversion rates

## API Endpoints

### Metrics Dashboard

- `GET /api/metrics` - Get complete metrics data
- `GET /api/ttu` - Get TTU metrics
- `GET /api/ttfsc` - Get TTFSC metrics
- `GET /api/funnels` - Get funnel metrics
- `GET /api/performance` - Get performance metrics
- `GET /api/retries` - Get retry metrics
- `GET /api/rage-clicks` - Get rage click metrics
- `GET /health` - Health check

## Configuration

### Environment Variables

- `DB_PATH`: Path to SQLite database file (default: `metrics.db`)
- `PORT`: Port for web server (default: 5001)
- `DEBUG`: Enable debug mode (default: False)

### Opt-in/Opt-out

Users can control metrics collection:

```python
# Enable tracking
tracker = EventTracker(opt_in=True)

# Disable tracking
tracker = EventTracker(opt_in=False)
```

### Privacy Protection

- **Anonymous User IDs**: Generated UUIDs, no personal information
- **Opt-in Only**: No tracking without explicit consent
- **Local Storage**: Data stored locally, not sent to external services
- **Data Retention**: Configurable retention periods

## Database Schema

### Events Table

```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE,
    event_type TEXT,
    timestamp DATETIME,
    user_id TEXT,
    session_id TEXT,
    properties TEXT,  -- JSON
    platform TEXT,
    version TEXT
);
```

### Performance Metrics Table

```sql
CREATE TABLE performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT,
    duration_ms REAL,
    memory_mb REAL,
    cpu_percent REAL,
    timestamp DATETIME,
    success BOOLEAN,
    error_message TEXT
);
```

## Integration

### With Understand-First CLI

```python
# In CLI code
from understand_first_metrics import EventTracker

tracker = EventTracker(opt_in=True)

def analyze_code():
    with tracker.measure_performance("code_analysis"):
        # Analysis code
        result = perform_analysis()
        
        # Track TTU
        tracker.track_ttu("code_analysis", analysis_time, success=True)
        
        return result
```

### With Web Demo

```javascript
// In web demo
const tracker = new EventTracker();

// Track user interactions
tracker.trackEvent('map_interaction', {
    action: 'zoom',
    element: 'canvas'
});

// Track TTU
tracker.trackTTU('onboarding', 120, true);
```

### With VS Code Extension

```typescript
// In VS Code extension
import { EventTracker } from './event-tracker';

const tracker = new EventTracker();

// Track extension usage
tracker.trackEvent('extension_activated', {
    version: '1.0.0'
});

// Track performance
tracker.trackPerformance('code_lens', duration, memory, cpu);
```

## Dashboard Features

### KPI Overview

- **TTU Metrics**: Average time and success rate
- **TTFSC Metrics**: Average time and success rate
- **Performance**: Operation metrics and success rates

### Charts and Visualizations

- **Bar Charts**: TTU and TTFSC metrics
- **Line Charts**: Funnel conversion rates
- **Tables**: Performance, retry, and rage click data

### Filtering and Time Periods

- **Time Periods**: 7, 30, or 90 days
- **Real-time Updates**: Refresh data on demand
- **Export Options**: Download metrics data

## Troubleshooting

### Common Issues

1. **No data showing**: Check that opt-in is enabled and events are being tracked
2. **Database errors**: Ensure SQLite is installed and database file is writable
3. **Performance issues**: Check if too many events are being tracked
4. **Memory usage**: Monitor database size and consider data retention policies

### Debug Mode

Enable debug mode for detailed logging:

```bash
DEBUG=true python metrics_dashboard.py
```

### Data Export

Export metrics for analysis:

```bash
python understand_first_metrics.py --export metrics.json --format json
python understand_first_metrics.py --export metrics.csv --format csv
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
