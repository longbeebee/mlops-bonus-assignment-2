FROM apache/airflow:2.10.2-python3.10

USER airflow

RUN pip install --no-cache-dir \
    mlflow==2.16.2 \
    scikit-learn==1.5.1 \
    boto3==1.35.24 \
    joblib==1.4.2 \
    requests==2.32.3

WORKDIR /opt/airflow
