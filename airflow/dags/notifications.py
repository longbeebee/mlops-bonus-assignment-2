"""Webhook notifications for Airflow DAG and task state changes."""

import os
from typing import Any

import requests


def _send(message: str) -> None:
    _send_telegram(message)

    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if not webhook_url:
        if not os.getenv("TELEGRAM_BOT_TOKEN"):
            print(f"No alert destination is configured. Message: {message}")
        return

    try:
        response = requests.post(webhook_url, json={"text": message}, timeout=10)
        response.raise_for_status()
    except requests.RequestException as error:
        # Notification failure must not hide the original pipeline result.
        print(f"Failed to send alert notification: {error}")


def _send_telegram(message: str) -> None:
    """Send a plain-text alert through the Telegram Bot API when configured."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        # Notification failure must not hide the original pipeline result.
        print(f"Failed to send Telegram alert: {error}")


def task_failure_alert(context: dict[str, Any]) -> None:
    task = context.get("task_instance")
    dag_run = context.get("dag_run")
    exception = context.get("exception")
    _send(
        "❌ ML pipeline task failed\n"
        f"DAG: {dag_run.dag_id if dag_run else 'unknown'}\n"
        f"Task: {task.task_id if task else 'unknown'}\n"
        f"Run: {dag_run.run_id if dag_run else 'unknown'}\n"
        f"Error: {exception}"
    )


def dag_success_alert(context: dict[str, Any]) -> None:
    dag_run = context.get("dag_run")
    _send(
        "✅ ML pipeline completed successfully\n"
        f"DAG: {dag_run.dag_id if dag_run else 'unknown'}\n"
        f"Run: {dag_run.run_id if dag_run else 'unknown'}"
    )
