# Administrace klíče RSV

Správce otevře **Správa rodiny** (`/rodina`) → **Registr vozidel – dohledání VIN**. Nový klíč vloží do pole **Nový API klíč RSV**, uloží a stiskne **Otestovat spojení**. Pole se po uložení vyprázdní. Testuje se uložený klíč; volitelně lze vyplnit VIN vlastního auta. Test nevytváří ani nemění auto. Běžný člen nemá přístup ani přes API.

Šifrovaný klíč je v PostgreSQL; změna prohlížeče jej neovlivní. DB nastavení má přednost před výchozím klíčem prostředí. API nikdy nevrací klíč. Audit ukládá pouze verzi a výsledek testu. Chyba spojení, odmítnutý klíč, omezení dotazů a nenalezené vozidlo mají odlišné výsledky. Funkční spojení nezaručuje přítomnost každého VIN v registru.

Při změně `DJANGO_SECRET_KEY` je potřeba uložit RSV klíč znovu. Tajemství prostředí uchovávejte odděleně od šifrovaných záloh DB. Kryptografická knihovna je připnutá v `backend/uv.lock`.

## Lokální ověření

```sh
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python -m pytest -q
npm ci --prefix frontend
npm run test --prefix frontend
npm run lint --prefix frontend
npm run build --prefix frontend
```

Node musí splňovat verzi 26 z package.json. Backend vyžaduje lokální PostgreSQL a prostředí připravené podle README.

## Aktualizace Docker / Portainer

Nejdříve záloha DB a oddělené uložení prostředí. Zachovejte název stacku, volume i všechny stávající tajné hodnoty; nepoužívejte `down -v`. Na Docker hostu sestavte nové aplikační image:

```sh
docker compose --env-file .env.portainer -f compose.portainer.yaml -f compose.build.yaml build backend web
docker compose --env-file .env.portainer -f compose.portainer.yaml up -d
```

V prostředí nastavte `TANKLOG_IMAGE_TAG=0.9.1`; pro existující databázový image ponechte `TANKLOG_DB_IMAGE_TAG=0.9.0`. Portainer používá stejný compose soubor a již sestavené lokální image. Migrace 0003 pouze přidává novou tabulku, stávající data nepřepisuje. Webový port zůstává 8088, DB port není publikovaný.

## Výsledky lokálního ověření 15. 11. 2026

- Celá původní sada s prvními 10 novými testy: 250 backendových testů prošlo.
- Doplňkové testy ověřují také použití DB klíče při běžném VIN lookupu a změnu klíče během vzdáleného testu; výsledky jsou uvedené v záznamu nasazení níže.
- 31 frontendových testů prošlo, včetně uložení, vyprázdnění heslového pole a tlačítka testu.
- OpenAPI bylo vygenerováno a validováno; migrace odpovídají modelům.
- Živý dotaz z běžícího serveru se stávajícím klíčem vrátil Status 1 a údaje vozidla; úmyslně neplatný klíč byl odmítnut.
