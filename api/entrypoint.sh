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
echo "entrypoint: migrations current, starting $*"
exec "$@"
