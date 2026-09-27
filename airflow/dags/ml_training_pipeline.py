"""Scheduled data preparation and MLflow model training pipeline."""

from datetime import datetime, timedelta
import os
from pathlib import Path

import mlflow
import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

from notifications import dag_success_alert, task_failure_alert


MODEL_NAME = os.getenv("MODEL_NAME", "wine_quality_model")
REFERENCE_DIR = Path("/opt/airflow/evidently_reference")


def prepare_reference_data():
    """Create the reference dataset consumed by the Evidently service."""
    from sklearn.datasets import load_wine
    import pandas as pd

    wine = load_wine(as_frame=True)
    reference = wine.data.copy()
    reference.columns = [f"feature_{i}" for i in range(reference.shape[1])]
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    reference.to_csv(REFERENCE_DIR / "reference_data.csv", index=False)
    (REFERENCE_DIR / "metadata.json").write_text(
        '{"description": "Wine dataset reference window", "source": "airflow"}'
    )


def verify_registered_model():
    """Fail the DAG if training did not publish a Production model."""
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
    client = mlflow.tracking.MlflowClient()
    versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
    if not versions:
        raise RuntimeError(f"No Production version found for {MODEL_NAME}")
    print(f"Production model: {MODEL_NAME} v{versions[0].version}")


def reload_api_model():
    """Tell the serving API to load the newly promoted model."""
    response = requests.post(
        f"{os.getenv('API_URL', 'http://api:8000')}/model/reload", timeout=30
    )
    response.raise_for_status()


with DAG(
    dag_id="ml_training_pipeline",
    description="Prepare reference data, train/register a model in MLflow, and reload serving",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args={
        "owner": "ml-platform",
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
        "on_failure_callback": task_failure_alert,
    },
    on_success_callback=dag_success_alert,
    tags=["mlops", "mlflow", "training"],
) as dag:
    prepare_data = PythonOperator(
        task_id="prepare_reference_data", python_callable=prepare_reference_data
    )

    train_model = BashOperator(
        task_id="train_model",
        bash_command="python /opt/airflow/scripts/train_model.py",
        env={
            "MODEL_ARTIFACT_DIR": "/opt/airflow/model_artifacts",
        },
    )

    register_model = BashOperator(
        task_id="register_model",
        bash_command="python /opt/airflow/scripts/register_model.py",
        env={
            "MODEL_ARTIFACT_DIR": "/opt/airflow/model_artifacts",
            "MLFLOW_TRACKING_URI": "http://mlflow:5000",
            "MLFLOW_S3_ENDPOINT_URL": "http://minio:9000",
            "AWS_ACCESS_KEY_ID": "minio",
            "AWS_SECRET_ACCESS_KEY": "minio123",
            "MLFLOW_S3_IGNORE_TLS": "true",
            "MODEL_NAME": MODEL_NAME,
            "MLFLOW_RUN_NAME": "airflow_{{ ts_nodash }}",
        },
    )

    verify_model = PythonOperator(
        task_id="verify_production_model", python_callable=verify_registered_model
    )
    reload_model = PythonOperator(task_id="reload_api_model", python_callable=reload_api_model)

    prepare_data >> train_model >> register_model >> verify_model >> reload_model
