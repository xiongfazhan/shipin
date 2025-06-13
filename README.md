# ShipIn Video Analytics Services

This repository contains several microservices written in Python for video processing and analysis.
Each service can be launched independently.

## Services

- **detection-service**: Performs object detection with YOLO and exposes an HTTP API.
- **analytics-service**: Receives detection events, runs rule based analysis and aggregates summaries.
- **stream-service**: Handles input video streams and manages basic metadata.
- **storage-service**: Persists detections and summaries in database or file storage.
- **management-service**: Simple management frontend for configuring streams and reviewing results.

## Running a Service

1. Install Python 3.8 or later.
2. Install the dependencies for the chosen service:
   ```bash
   pip install -r <service>/requirements.txt
   ```
3. Start the service:
   ```bash
   cd <service>
   python app.py
   ```

## Demo Client

`demo_summary_client.py` is a small Flask app that can receive push notifications from `analytics-service`.
Run it with:
```bash
pip install flask rich
python demo_summary_client.py
```

Each service exposes a small REST API. See the source of `app.py` within each service directory for
endpoint details.

