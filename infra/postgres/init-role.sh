#!/bin/sh
# Pouze první inicializace nového produkčního svazku. Existující DB se nemění.
set -eu
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --no-password --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_user TANKLOG_APP_DB_USER
\getenv app_password TANKLOG_APP_DB_PASSWORD
\getenv database POSTGRES_DB
SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=:'app_user') AS role_exists \gset
\if :role_exists
\echo 'Aplikační role již existuje; automatická inicializace odmítnuta.'
SELECT 1/0;
\endif
CREATE ROLE :"app_user" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD :'app_password';
GRANT CONNECT ON DATABASE :"database" TO :"app_user";
GRANT USAGE, CREATE ON SCHEMA public TO :"app_user";
SQL
