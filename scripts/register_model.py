"""Register a trained local artifact in MLflow and promote it to Production."""

import json
import os
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import numpy as np


ARTIFACT_DIR = Path(os.getenv("MODEL_ARTIFACT_DIR", "/tmp/model_artifacts"))
MODEL_NAME = os.getenv("MODEL_NAME", "wine_quality_model")
EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "wine_quality_experiment")


def main():
    model_file = ARTIFACT_DIR / "model.joblib"
    metadata_file = ARTIFACT_DIR / "metadata.json"
    if not model_file.exists() or not metadata_file.exists():
        raise FileNotFoundError(f"Training artifacts not found in {ARTIFACT_DIR}")

    with metadata_file.open() as file:
        metadata = json.load(file)

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment(EXPERIMENT_NAME)
    model = joblib.load(model_file)

    with mlflow.start_run(run_name=os.getenv("MLFLOW_RUN_NAME", "model_registration")) as run:
        mlflow.log_params(metadata["params"])
        mlflow.log_metrics(metadata["metrics"])
        mlflow.sklearn.log_model(
            model,
            artifact_path="model",
            registered_model_name=MODEL_NAME,
            signature=mlflow.models.infer_signature(
                np.asarray(metadata["input_example"]),
                model.predict(np.asarray(metadata["input_example"])),
            ),
            input_example=np.asarray(metadata["input_example"]),
        )
        print(f"MLflow run registered: {run.info.run_id}")

    client = mlflow.tracking.MlflowClient()
    versions = client.get_latest_versions(MODEL_NAME, stages=["None"])
    if not versions:
        raise RuntimeError(f"No new version found for {MODEL_NAME}")

    version = versions[0].version
    client.transition_model_version_stage(
        name=MODEL_NAME,
        version=version,
        stage="Production",
        archive_existing_versions=True,
    )
    print(f"Promoted {MODEL_NAME} version {version} to Production")


if __name__ == "__main__":
    main()
