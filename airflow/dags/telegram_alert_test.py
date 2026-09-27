"""Manual Airflow failure test for Telegram notifications.

This DAG is paused and unscheduled by default. Trigger it manually when you
want to verify a real Airflow task failure, task log, and Telegram alert.
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from notifications import task_failure_alert


def fail_on_purpose() -> None:
    raise RuntimeError("Intentional failure for Telegram alert testing")


with DAG(
    dag_id="telegram_alert_test",
    description="Manual failure test for Airflow Telegram notifications",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=True,
    default_args={
        "owner": "ml-platform",
        "retries": 0,
        "on_failure_callback": task_failure_alert,
    },
    tags=["test", "telegram", "notifications"],
) as dag:
    PythonOperator(
        task_id="fail_on_purpose",
        python_callable=fail_on_purpose,
    )
