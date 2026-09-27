"""Train the model and persist a local artifact for the registration step."""

import json
import os
from pathlib import Path

import joblib
from sklearn.datasets import load_wine
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split


OUTPUT_DIR = Path(os.getenv("MODEL_ARTIFACT_DIR", "/tmp/model_artifacts"))


def main():
    wine = load_wine()
    X_train, X_test, y_train, y_test = train_test_split(
        wine.data, wine.target, test_size=0.2, random_state=42
    )

    params = {
        "n_estimators": 100,
        "max_depth": 10,
        "min_samples_split": 2,
        "random_state": 42,
    }
    model = RandomForestClassifier(**params)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "f1_score": f1_score(y_test, y_pred, average="weighted"),
        "precision": precision_score(y_test, y_pred, average="weighted"),
        "recall": recall_score(y_test, y_pred, average="weighted"),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, OUTPUT_DIR / "model.joblib")
    with (OUTPUT_DIR / "metadata.json").open("w") as file:
        json.dump(
            {
                "params": params,
                "metrics": metrics,
                "input_example": X_train[:5].tolist(),
                "training_samples": len(X_train),
            },
            file,
            indent=2,
        )
    print(f"Trained model written to {OUTPUT_DIR}")
    print(f"Metrics: {metrics}")


if __name__ == "__main__":
    main()
