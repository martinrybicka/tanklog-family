"""Explicitní ochrana syntetické místní CI databáze."""

import os


def require_ci_database():
    if (
        os.environ.get("TANKLOG_CI") != "1"
        or not os.environ.get("POSTGRES_DB", "").endswith(("_ci", "_ci_e2e"))
        or os.environ.get("POSTGRES_HOST") not in {"127.0.0.1", "localhost"}
    ):
        raise SystemExit(
            "Vyžaduje TANKLOG_CI=1, samostatnou *_ci nebo *_ci_e2e DB a místní PostgreSQL."
        )


def main():
    # Příkaz je jen pro první založení nové místní testovací DB; existující odmítne.
    import psycopg
    from psycopg import sql

    require_ci_database()
    with psycopg.connect(
        dbname="postgres",
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=os.environ.get("POSTGRES_PORT", "5432"),
        autocommit=True,
    ) as connection:
        if connection.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", [os.environ["POSTGRES_DB"]]
        ).fetchone():
            raise SystemExit(
                "Cílová CI databáze už existuje; nic se nemění ani nemaže."
            )
        connection.execute(
            sql.SQL("CREATE DATABASE {} ").format(
                sql.Identifier(os.environ["POSTGRES_DB"])
            )
        )
    print("Nová syntetická CI databáze byla založená. Žádná existující DB se neměnila.")


if __name__ == "__main__":
    main()
