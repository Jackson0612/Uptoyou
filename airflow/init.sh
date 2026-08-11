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

echo "airflow-init: setting the admin password"
# `airflow users create` is not this Airflow's command. It belongs to the FAB auth manager of
# Airflow 2; Airflow 3 defaults to the simple auth manager, which has no user table and no
# such subcommand. The call printed the CLI help and created nothing — and because it was
# written as `2>/dev/null || echo "admin already exists"`, the log said the opposite and the
# UI rejected the password in .env for three commits. Nothing here masks a failure any more —
# the two `|| true` below are an expected absence on a first run, not a discarded error, and
# every other command is left to `set -e`.
#
# Under the simple auth manager the *user list* is configuration — core.simple_auth_manager_users,
# which already defaults to `admin:admin` — and only the password is state. The api-server
# reads the file below on start and invents a random password for any listed user missing from
# it, printing it once to its own log. Writing the file first is what makes the password the
# one in .env, and keeps it that way across `docker compose down`.
python - <<'PY'
import json
import os

path = os.environ["AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE"]
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as file:
    json.dump({"admin": os.environ["AIRFLOW_ADMIN_PASSWORD"]}, file)
    file.write("\n")
os.chmod(path, 0o600)
print(f"airflow-init: admin password written to {path}")
PY

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
