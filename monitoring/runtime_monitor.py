"""Runtime health and alert monitor for the ML monitoring stack."""

import json
import logging
import os
import socket
import time
from typing import Any

import requests


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("runtime-monitor")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
INTERVAL = int(os.getenv("RUNTIME_MONITOR_INTERVAL_SECONDS", "30"))
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
DOCKER_SOCKET = "/var/run/docker.sock"
STACK_PREFIX = f"{os.getenv('USER', 'user')}_monitoring-"


class RuntimeMonitor:
    def __init__(self) -> None:
        self.active: set[str] = set()
        self.restart_counts: dict[str, int] = {}

    def send_telegram(self, message: str) -> None:
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            LOGGER.warning("Telegram alert skipped: Telegram variables are not configured")
            return
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            LOGGER.error("Failed to send Telegram alert: %s", error)

    def set_alert(self, key: str, message: str) -> None:
        if key not in self.active:
            self.send_telegram(f"⚠️ Runtime alert\n{message}")
            self.active.add(key)
            LOGGER.error("%s", message.replace("\n", " | "))

    def clear_alert(self, key: str, message: str) -> None:
        if key in self.active:
            self.send_telegram(f"✅ Runtime recovered\n{message}")
            self.active.remove(key)
            LOGGER.info("%s", message.replace("\n", " | "))

    @staticmethod
    def get(url: str) -> requests.Response:
        return requests.get(url, timeout=8)

    def check_http(self, key: str, name: str, url: str, healthy=None) -> None:
        try:
            response = self.get(url)
            ok = response.ok and (healthy(response) if healthy else True)
            if ok:
                self.clear_alert(key, f"{name} is healthy again: {url}")
            else:
                self.set_alert(key, f"{name} is unavailable or unhealthy: {url} (HTTP {response.status_code})")
        except (requests.RequestException, ValueError) as error:
            self.set_alert(key, f"{name} is unreachable: {url}\nError: {error}")

    def query_prometheus(self, query: str) -> list[dict[str, Any]]:
        try:
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": query},
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("data", {}).get("result", [])
        except (requests.RequestException, ValueError) as error:
            self.set_alert("prometheus", f"Prometheus query failed\nError: {error}")
            return []

    def check_metric_alert(self, key: str, query: str, message: str) -> None:
        if self.query_prometheus(query):
            self.set_alert(key, message)
        else:
            self.clear_alert(key, f"Condition recovered: {message}")

    def check_prometheus_alerts(self) -> None:
        try:
            response = self.get(f"{PROMETHEUS_URL}/api/v1/alerts")
            response.raise_for_status()
            alerts = response.json().get("data", {}).get("alerts", [])
        except (requests.RequestException, ValueError) as error:
            self.set_alert("prometheus-alerts", f"Prometheus alerts endpoint failed\nError: {error}")
            return

        current = set()
        for alert in alerts:
            if alert.get("state") not in {"pending", "firing"}:
                continue
            labels = alert.get("labels", {})
            name = labels.get("alertname", "UnnamedAlert")
            key = f"prometheus:{name}:{json.dumps(labels, sort_keys=True)}"
            current.add(key)
            self.set_alert(
                key,
                f"{name}\nSeverity: {labels.get('severity', 'unknown')}\n"
                f"Summary: {alert.get('annotations', {}).get('summary', 'No summary')}",
            )

        for key in [item for item in self.active if item.startswith("prometheus:") and item not in current]:
            self.clear_alert(key, "Prometheus alert is no longer active")

    def check_docker_restarts(self) -> None:
        if not os.path.exists(DOCKER_SOCKET):
            self.set_alert("docker-socket", "Docker socket is not mounted; container restart monitoring is unavailable")
            return
        try:
            request = (
                "GET /containers/json?all=1 HTTP/1.1\r\n"
                "Host: docker\r\nConnection: close\r\n\r\n"
            ).encode()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(DOCKER_SOCKET)
                client.sendall(request)
                chunks = []
                while True:
                    chunk = client.recv(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
            raw_response = b"".join(chunks)
            headers, body = raw_response.split(b"\r\n\r\n", 1)
            if b"transfer-encoding: chunked" in headers.lower():
                decoded = bytearray()
                while body:
                    size_end = body.find(b"\r\n")
                    if size_end < 0:
                        raise ValueError("invalid chunked Docker API response")
                    size = int(body[:size_end].split(b";", 1)[0], 16)
                    if size == 0:
                        break
                    start = size_end + 2
                    decoded.extend(body[start:start + size])
                    body = body[start + size + 2:]
                body = bytes(decoded)
            containers = json.loads(body)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.set_alert("docker-api", f"Docker API query failed\nError: {error}")
            return

        for container in containers:
            names = container.get("Names", [])
            name = names[0].lstrip("/") if names else container.get("Id", "unknown")[:12]
            if not name.startswith(STACK_PREFIX):
                continue
            restart_count = int(container.get("RestartCount", 0))
            previous = self.restart_counts.get(name)
            self.restart_counts[name] = restart_count
            if previous is not None and restart_count > previous:
                self.set_alert(
                    f"restart:{name}",
                    f"Container restarted: {name}\nRestart count: {restart_count}",
                )

    def check_once(self) -> None:
        self.check_http(
            "api-down",
            "FastAPI",
            "http://api:8000/health",
            lambda response: response.json().get("status") == "healthy",
        )
        self.check_http("evidently-down", "Evidently", "http://evidently:8001/health")
        self.check_http("mlflow-down", "MLflow", "http://mlflow:5000/health")
        self.check_http("minio-down", "MinIO", "http://minio:9000/minio/health/live")
        self.check_http("grafana-down", "Grafana", "http://grafana:3000/api/health")
        self.check_metric_alert(
            "prediction-errors",
            "increase(model_prediction_errors_total[5m]) > 0",
            "FastAPI prediction errors detected in the last 5 minutes",
        )
        self.check_metric_alert(
            "data-drift",
            "evidently_data_drift_detected == 1",
            "Evidently detected model/data drift",
        )
        self.check_prometheus_alerts()
        self.check_docker_restarts()

    def run(self) -> None:
        LOGGER.info("Runtime monitor started; interval=%ss", INTERVAL)
        while True:
            self.check_once()
            time.sleep(INTERVAL)


if __name__ == "__main__":
    RuntimeMonitor().run()
