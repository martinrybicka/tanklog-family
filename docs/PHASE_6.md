# Fáze 6 – předání lokální části (3. 11. 2026)

Uživatel povolil fázi 6 a současně výslovně zakázal cokoli odesílat na GitHub nebo produkční server. Byla proto realizována pouze lokální příprava. **Celá akceptace fáze 6 není splněná:** private repozitář, push a skutečný CI běh nejsou provedené. Nevznikl remote, nic nebylo publikováno, fáze 7 nebyla zahájena.

## Implementace a soubory

- `.github/workflows/ci.yml`: čtyři úlohy – audit historie/bezpečnosti, backend/PostgreSQL, frontend a izolovaný Docker/E2E. Read-only token, úplné SHA akcí, bez deploy, produkčních secrets a uploadu artefaktů.
- `infra/ci/run_checks.py`, `verify_workflow.py`, `tests/test_policy.py`: sdílené lokální/CI kontroly a 11 regresních testů bezpečnostních hranic. Migrace, OpenAPI a produkční systémové kontroly; přijímá pouze předchozí zdokumentované HSTS W004.
- `infra/ci/check_repository.py`, `tools.json`, `install_tools.py`: audit cest indexu/celé historie, Gitleaks a actionlint, připnuté CLI archivy se SHA-256. Kontroly se doplňují, nepředstavují absolutní důkaz neexistence každého typu tajného údaje.
- `compose.ci.yaml`, `infra/ci/containers.py`, `database.py`, `clean_export.py`: nový izolovaný CI projekt a syntetická DB, ochrana před vzdáleným Dockerem/DB, čistý export pouze sledovaných zdrojů. Žádné mazání volumes.
- `compose.dev.yaml`, `infra/verify_compose.py`: opraven chybějící read-only mount security-headers.conf pro dev nginx; kontrola tří Compose variant. `infra/ruff.toml` sjednocuje Python kontroly pomocníků.
- README, AGENTS, ROADMAP, SPECIFICATION, ARCHITECTURE, SECURITY, DECISIONS a CI.md aktualizují skutečný rozsah. Aplikační kód, API/model/migrace, výpočty a aplikační lock soubory se nemění.

## Skutečné výsledky

Čistý export sledovaných zdrojů byl vytvořen mimo pracovní strom, bez existujících .env/.venv/node_modules. Instalace: Python **3.14.10**, uv **0.13.6**, Node **26.13.0**, npm **11.20.0**, místní PostgreSQL **18.6**. Backend uv sync --frozen a frontend npm ci skutečně prošly; instalace npm hlásila 0 známých zranitelností. Platforma macOS/ARM64, nikoli GitHub Ubuntu/x64.

| Kontrola | Výsledek |
| --- | --- |
| Backend pytest nad oddělenou DB | **192 prošlo**, poslední úplný průchod 33,40 s |
| CI bezpečnostní regrese | **11 prošlo** |
| Frontend Vitest | **28 prošlo**, 8 souborů |
| E2E se skutečným Playwright Chromium | **22 prošlo**, desktop + mobil, čistý export a samostatná *_ci_e2e DB |
| Ruff, Oxlint, Prettier, typecheck, Vite/PWA build | Prošlo |
| Migrace na nové syntetické DB, makemigrations --check, Django check | Prošlo, žádné chybějící migrace |
| Generované OpenAPI --validate --fail-on-warn a shoda docs/openapi.yaml | Prošlo |
| Django check --deploy | Pouze očekávané **security.W004**, HSTS=0 dle ADR-027; další varování nepovolena |
| actionlint 1.7.12, lokální politika workflow | Prošlo |
| Audit indexu/historie a Gitleaks 8.30.1 --redact | Prošlo, žádné detekované úniky; kontrola zopakována po lokálním commitu |
| Compose dev/prod/CI config, porty, sítě, svazky a build targety | Prošlo pomocí standalone Compose 5.6.1 bez daemonu |
| Syntaxe dev nginx v nativním nginx 1.31.7 se skutečnými include soubory | Prošlo |
| Docker dev up, produkční build a CI kontejnery | **Nelze provést**: chybí Docker CLI/daemon a unixový socket |
| Soukromý GitHub, autorizovaný push a skutečný CI běh | **Neprovedeno** podle výslovného zákazu uživatele |

Nativní E2E cílil na 127.0.0.1:18080 (Vite) → 127.0.0.1:18081 (Django), nikoli kontejnery. PWA/produkční HTTPS šest scénářů nebylo v této etapě znovu spuštěno; předchozí výsledek je v PHASE_5.md. Vynechání je stejné jako v připraveném HTTP CI jobu. Platné testy aplikace z předchozí fáze nebyly nahrazeny novými.

## Přesné spuštění aplikace

Z kořene projektu s funkčním Docker Engine a Compose:

```sh
python3 infra/setup_env.py
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py migrate
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py createsuperuser
```

Otevřete http://localhost:8080. Createsuperuser je pouze pro prvního správce; žádné výchozí heslo běžné DB není. Zastavení zachovávající data: `docker compose -f compose.yaml -f compose.dev.yaml stop`.

Na tomto Macu zůstává alternativou stávající syntetický nativní náhled s DB tanklog_e2e. PostgreSQL už běží na 127.0.0.1:55432; případné opětovné spuštění jeho existujícího clusteru je v PHASE_5.md. Dva terminály z kořene:

```sh
# Terminál 1, existující backend/.venv:
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py runserver 127.0.0.1:8000
# Terminál 2, existující frontend/node_modules:
PATH=/opt/homebrew/opt/node@26/bin:$PATH API_PROXY_TARGET=http://127.0.0.1:8000 HMR_CLIENT_PORT=8080 npm run dev --prefix frontend -- --host 127.0.0.1 --port 8080
```

Otevřete http://127.0.0.1:8080. Při předání byly náhled i /api/health/ready/ skutečně ověřené s HTTP 200. Jde o testovací prostředí, ne produkci. Syntetický účet je definován pouze v backend/tests/prepare_e2e.py; nepoužívejte jej pro reálný provoz. Přesná čistá instalace a CI příkazy jsou v [CI.md](CI.md).

## Ruční ověření

1. Zkontrolujte workflow: pouze read oprávnění, akce s úplnými SHA, bez secrets/deploy/uploadu. Spusťte verify_workflow.py, 11 unittestů, actionlint a audit celé historie podle CI.md.
2. Ověřte uv sync --frozen a npm ci v novém exportu zdrojů. Proveďte backendové kontroly nad novou *_ci DB a frontendové kontroly podle CI.md.
3. S dostupným místním Dockerem spusťte `python3 infra/ci/containers.py`. Musí sestavit oba image, provést migrace, dokončit 22 E2E a zastavit pouze vlastní projekt. Svazek se automaticky nemaže. Vyhraďte port 18080.
4. Spusťte běžný dev Compose výše. Ověřte login → profil → vozidlo → tankování → dashboard a historii; obnovte stránku a přihlaste se v druhém prohlížeči. Po restartu kontejnerů musí DB data zůstat. Tento Docker runtime/restart zde není ověřený.
5. Private viditelnost a skutečný CI běh lze ověřit až po samostatném povolení GitHubu; nyní nic nepublikujte. Vzdálená část potřebuje následně konkrétní odkaz na běh a skutečný stav všech úloh.

## Neúspěšné Docker pokusy a meze

Skutečně vyzkoušeno, nikoli pouze navrženo:

```sh
DOCKER_HOST=unix:///var/run/docker.sock .tools/docker-compose --env-file .env -f compose.yaml -f compose.dev.yaml up --build -d
DOCKER_HOST=unix:///var/run/docker.sock NPM_TRUSTED_CIDR=172.30.0.0/24 NPM_NETWORK_NAME=tanklog-verification-only .tools/docker-compose --env-file .env -f compose.yaml -f compose.prod.yaml build backend web
python3 infra/ci/containers.py
```

První dva příkazy skončily chybou připojení k chybějícímu /var/run/docker.sock, třetí odmítl start kvůli chybějícímu Docker CLI/daemonu. Žádná produkční síť nebyla vytvořena. Pinned Linux image, Linux CLI instalátor a GitHub runner tedy nebyly skutečně spuštěné; validní YAML a úspěšný macOS průchod je nenahrazují. Nové syntetické CI DB zůstaly zachované, běžná data se neměnila. Omezení ručního zoomu, čtečky, času člověka a PWA instalace z fáze 5 přetrvávají. Produkční zálohy/obnova a nasazení patří až do fáze 7.
