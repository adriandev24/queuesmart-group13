# QueueSmart Final Features

## Administrator CSV reporting

The final reporting module is restricted to administrator bearer tokens. `GET /api/admin/reports/summary` builds an on-demand report for UI preview, while `GET /api/admin/reports/export.csv` exports the same data as CSV. Optional `start_date`, `end_date`, and `service_id` filters are supported.

The CSV deliberately contains multiple `record_type` rows so one export includes all required categories:

- `SUMMARY`: total participations, number served, cancellations, average wait, unique customers, and current waiting count.
- `SERVICE`: service description, duration, priority, queue status, queue activity, served count, and canceled count.
- `HISTORY`: customer identity and participation history with service, timestamps, outcome, and wait time.
- `CUSTOMER`: a user with no matching history in the selected report period.

## Smart feature: suggested best time to join

`GET /api/services/{service_id}/best-time` analyzes completed served visits from the configured lookback window (default 90 days). Completed visits are grouped by the hour when the user joined. QueueSmart calculates each hour's average wait and uses a small traffic-volume penalty to avoid recommending a historically crowded hour that happened to have one unusually fast visit. The lowest score becomes the recommended time window.

This is "smart" because the recommendation is derived from QueueSmart's own persisted history rather than a fixed label. It improves the user experience by helping a customer choose a lower-wait time before joining. It integrates directly with the existing `History`, `Service`, and live queue data from Assignment 4. When there is not enough history, the endpoint still provides a transparent current-load fallback based on queue length and the service's expected duration.
