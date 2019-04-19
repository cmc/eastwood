#!/bin/sh

POSTGRES_PASSWORD=$(cat config/config.json | python -c 'import sys, json; print(json.load(sys.stdin)["POSTGRES_PASS"])')
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -d "$POSTGRES_DB" -U "$POSTGRES_USER" -c '\q'; do
  >&2 echo "Waiting for Postgres..."
  sleep 3
done

>&2 echo "Postgres is up - Lets do this."
sleep 3

python -u eastwood.py
