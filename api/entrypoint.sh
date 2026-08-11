#!/bin/sh
# Migrations run before the application, in the same container, on every start.
#
# The alternative — a separate migrate step a human remembers — fails §6's criterion, which
# is literally `docker compose up` and nothing else. Running them here is safe because there
# is exactly one API worker (H2), so there is no second process to race.
#
# `alembic upgrade head` is idempotent: on an already-current database it prints nothing and
# exits 0. If it fails, the container fails, which is the point — an API serving against a
# schema it does not expect is worse than an API that did not start.
set -e
echo "entrypoint: applying migrations"
alembic upgrade head
echo "entrypoint: seeding the township-station map"
# Ticket 06's one command, and it is idempotent: an upsert keyed on the township code, with
# a self-check that refuses rather than writing a mapping that disagrees with the ingested
# observations. Running it on every start is what makes `docker compose up` sufficient.
python -m upto.seed.township_station

echo "entrypoint: migrations current, starting $*"
exec "$@"
