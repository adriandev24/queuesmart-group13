"""Generate reports/sample_queue_report.csv directly from the persisted QueueSmart database."""
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import SessionLocal, init_db
from backend.logic import build_report_data

OUT = Path(__file__).resolve().parents[1] / "reports" / "sample_queue_report.csv"
FIELDS = [
    "record_type","user_email","user_name","service_name","service_description","priority_level",
    "expected_duration","queue_status","current_waiting","joined_at","completed_at","outcome",
    "wait_minutes","participation_count","total_participations","users_served","canceled",
    "average_wait_minutes","unique_customers"
]


def generate():
    init_db()
    db = SessionLocal()
    try:
        report = build_report_data(db)
        with OUT.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            s = report["statistics"]
            writer.writerow({"record_type":"SUMMARY","current_waiting":s["current_waiting"],"total_participations":s["total_participations"],"users_served":s["users_served"],"canceled":s["canceled"],"average_wait_minutes":s["average_wait_minutes"],"unique_customers":s["unique_customers"]})
            for service in report["services"]:
                writer.writerow({"record_type":"SERVICE","service_name":service["name"],"service_description":service["description"],"priority_level":service["priority_level"],"expected_duration":service["expected_duration"],"queue_status":service["queue_status"],"current_waiting":service["current_waiting"],"users_served":service["served"],"canceled":service["canceled"]})
            for user in report["users"]:
                if not user["history"]:
                    writer.writerow({"record_type":"CUSTOMER","user_email":user["email"],"user_name":user["full_name"],"participation_count":0})
                for item in user["history"]:
                    writer.writerow({"record_type":"HISTORY","user_email":user["email"],"user_name":user["full_name"],"service_name":item["service"],"joined_at":item["joined_at"],"completed_at":item["completed_at"],"outcome":item["outcome"],"wait_minutes":item["wait_minutes"],"participation_count":user["participation_count"]})
        print(f"Generated {OUT}")
    finally:
        db.close()


if __name__ == "__main__":
    generate()
