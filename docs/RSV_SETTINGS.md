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

## Skutečné nasazení 15. 11. 2026

Implementace zveřejněna v commitu `09a0b9f` na main repozitáře martinrybicka/tanklog-family. Backend a web image 0.9.1 byly sestavené na DOCKER01 a nasazené do stejného Portainer stacku 51. Databáze používá image 0.9.0 a původní volume `tanklog-family_postgres_data`. Všechny tři služby jsou healthy, stack aktivní. Webový port zůstává 8088.

Před aktualizací byla vytvořena šifrovaná pg_dump záloha v místní ignorované `.runtime/production-backup-20261115/tanklog.dump.age`; oddělený privátní dešifrovací klíč je v témže soukromém adresáři jako `identity.txt` (práva 600). Uchovejte identitu odděleně od kopie zálohy. Dešifrování do paměti a hlavička PGDMP byly skutečně ověřeny; úplná zkušební obnova této konkrétní produkční zálohy nebyla provedena. Žádný nezašifrovaný produkční dump se nezapsal do souboru.

Kontrolní hashe původních záznamů v 15 aplikačních tabulkách před a po nasazení jsou shodné. Provozní kvóty a audit se přirozeně doplnily o ověřovací volání; nová tabulka obsahuje jedinou šifrovanou konfiguraci. Žádné testovací účty ani auta nevznikly.

Přes skutečné HTTPS rozhraní `/rodina` byl stávající klíč uložen formulářem do DB. Heslové pole se vyprázdnilo, GET vrátil pouze configured/source/updated_at a tlačítko Otestovat spojení zobrazilo **Spojení funguje a registr přijal API klíč. Vozidlo bylo nalezeno.** Vzhled byl zkontrolován v prohlížeči. Krátká ověřovací administrátorská relace byla odhlášena.

Dodatečná sada backendu po posledních úpravách: **46 testů prošlo**, zahrnuje všech 12 nových testů administrace i stávající integrační testy. Frontend: **31 testů**, lint, TypeScript a produkční build prošly. Ruff, kontrola uv.lock, Django check, kontrola migrací a validace OpenAPI prošly. Výsledná Portainer/Compose konfigurace prošla kontrolou config --quiet a následným skutečným spuštěním na DOCKER01. Lokální Docker daemon není dostupný; serverový build a runtime byly ověřeny vzdáleně. Gitleaks nad zveřejňovaným patchem nenašel tajné hodnoty.
