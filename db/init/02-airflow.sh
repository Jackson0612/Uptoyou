#!/bin/sh
# Airflow's metadata database, created once on an empty volume alongside the application's.
#
# One PostgreSQL instance, two databases, rather than a second container: Airflow's scheduler
# already wants 1–2 GB on a 7.5 GB machine, and a second Postgres buys isolation this project
# has no use for — both databases are on the same host, backed up together, and lost together.
# The separation that matters is the *role*: airflow owns its schema and cannot read the
# application's tables.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    CREATE ROLE airflow LOGIN PASSWORD '${AIRFLOW_DB_PASSWORD}';
    CREATE DATABASE airflow OWNER airflow;
SQL
