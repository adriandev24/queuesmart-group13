# Final Demo Checklist

1. Start from a seeded database: `python scripts/seed_demo.py`.
2. Run the application: `uvicorn backend.main:app --reload`.
3. User login: `student@queuesmart.local` / `Student123!`.
4. Show available services, estimated wait, join a queue, current position, notifications, and history.
5. Select a service and click **Suggest Best Time**. Explain that QueueSmart groups persisted served visits by join hour and recommends the lowest average-wait/traffic score.
6. Administrator login: `admin@queuesmart.local` / `Admin123!`.
7. Show service creation, open/close queue, queue management, and serving the next user.
8. Refresh/restart as needed to demonstrate that records are persisted in SQLite.
9. Open **Reporting**, generate a report, and show users/history, service activity, served count, and average wait.
10. Export the report as CSV and open the downloaded file.
11. Mention the verified automated test result: 15 tests passed, 96% backend coverage.
12. Each group member should explain the code they personally committed; TA grading uses GitHub history and demo participation.
