FROM postgres:18.6-bookworm@sha256:5c4783a8cc3f0074912164f94dfa1be4e043438f0f707cf968d7af9a0d31a2c8
COPY --chmod=755 infra/postgres/init-role.sh /docker-entrypoint-initdb.d/10-tanklog-role.sh
