#!/bin/bash
# One-shot bootstrap: migrate Airflow's own database, create the admin, and create the two
# Connections the DAG reads.
#
# D33 is the whole point of this file. The CWA key and the application database arrive here
# once, as Connections, Fernet-encrypted in Airflow's metadata database. After this runs, no
# task reads either from the environment — and the only environment variables left are the
# ones that bootstrap Airflow itself, which is the exception D33 names.
set -euo pipefail

echo "airflow-init: migrating the metadata database"
airflow db migrate

echo "airflow-init: ensuring the admin user"
airflow users create \
    --username admin --firstname up --lastname to --role Admin \
    --email admin@example.invalid --password "${AIRFLOW_ADMIN_PASSWORD}" 2>/dev/null || \
    echo "airflow-init: admin already exists"

echo "airflow-init: creating connections"
# Deleting first makes this idempotent; `add` alone fails on a second run.
airflow connections delete upto_postgres >/dev/null 2>&1 || true
airflow connections add upto_postgres \
    --conn-type postgres \
    --conn-host db \
    --conn-port 5432 \
    --conn-schema "${POSTGRES_DB}" \
    --conn-login "${POSTGRES_USER}" \
    --conn-password "${POSTGRES_PASSWORD}"

airflow connections delete cwa_open_data >/dev/null 2>&1 || true
airflow connections add cwa_open_data \
    --conn-type http \
    --conn-host opendata.cwa.gov.tw \
    --conn-password "${UPTO_CWA_API_KEY}"

echo "airflow-init: done — connections are stored encrypted, not in the environment of any task"
