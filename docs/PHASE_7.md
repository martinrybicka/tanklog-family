# Fáze 7 – předání lokální části (3. 11. 2026)

Uživatel povolil fázi 7 a současně zakázal cokoli odesílat na GitHub nebo produkční server. Implementována je proto místní příprava a skutečné izolované testy. **Celá fáze 7 není akceptovaná:** veřejné HTTPS/NPM, off-host automatické zálohy a produkční RPO/RTO bez autorizovaného přístupu a konkrétního inventáře nelze ověřit. Fáze 8 nebyla zahájena, vzdálená akceptace fáze 6 zůstává neprovedená.

## Implementované části a soubory

- `compose.prod.yaml`, `infra/postgres/init-role.sh`, `.env.production.example`: samostatná bootstrap/aplikační role pro nové DB volumes, web alias tanklog-web pro existující NPM síť, web healthcheck, omezená velikost Docker logů a povinná produkční konfigurace. Žádné publikované porty. Existující DB role se automaticky nemění.
- `compose.yaml`: DB readiness přes TCP až po dokončení dočasné inicializace; backend healthcheck posílá přesný nakonfigurovaný Host, takže funguje i s jedinou produkční doménou.
- `infra/backend.Dockerfile`, `infra/nginx/common-http.conf`, `production.conf.template`, `local_production_preview.py`: access logy bez query stringu, cookies a IP, místní náhled používá stejnou konfiguraci a vlastní log.
- `infra/ops/backup.py`: konzistentní custom pg_dump a manifest ze stejného exportovaného read-only snapshotu, SHA-256 všech řádků včetně binárních účtenek, šifrování age, atomický nový výstup a synchronizace, obnova pouze do nové tanklog_restore_* DB, kontrola všech obnovených tabulek a plán retence bez mazání.
- `infra/operations.Dockerfile`, `infra/ops/tools.json`, `install_age.py`, `compose.ops.yaml`: připnuté nástroje pro amd64/arm64, privátní tmpfs, běžné zálohování pouze s veřejným recipientem, oddělený DB administrátor. Zdroj/klíč/mount musí existovat; Compose je nevytváří jako fallback.
- `compose.restore.yaml`, `restore_compose.py`: samostatný náhodný místní projekt a nový restore_data volume, žádná NPM síť/host porty, nové role a secrets, read-only archiv/identity, migrační a systémová kontrola, volitelný syntetický API test. Žádné mazání volumes.
- `preflight.py`, `systemd/*`: kontrola domény/originu, proxy CIDR, oddělených rolí a secrets, revize, odpovědné osoby a mountu; připravené spouštění 2× denně na budoucím Linuxu. Nic není nainstalováno ani aktivováno na serveru.
- `drill.py`, `drill_data.py`, `tests/test_operations.py`: skutečné nativní cvičení a 10 nových regresí. CI pomocníky rozšiřuje kontrola operations kódu/testů a budoucí build image; `verify_compose.py` kontroluje pět variant. `.age` zálohy jsou vyloučené z Gitu, historie i build contextu.

Aplikační API/model/migrace, algoritmus spotřeby a UI se nemění. Aplikační locky se nemění; nové operační nástroje mají přesnou verzi/checksum/digest. Technický postup a skutečně neznámé provozní údaje jsou v [OPERATIONS.md](OPERATIONS.md).

## Skutečně provedené testy

Místní prostředí: macOS/ARM64, Python 3.14.6 v existující backend/.venv, Node 26.13.0, uv 0.13.6, PostgreSQL nástroje/server 18.6, age 1.3.2, nginx 1.31.7. Navržený operations image má Python 3.14.10 a Linux; jeho runtime zde nebyl spuštěný.

| Kontrola | Skutečný výsledek |
| --- | --- |
| Backend pytest nad oddělenou syntetickou CI DB | **192 prošlo**, 39,95 s |
| Frontend Vitest | **28 prošlo**, 8 souborů |
| HTTP desktop/mobil E2E | **22 prošlo**, 3,2 min |
| Produkční build přes místní HTTPS nginx/Gunicorn | **6 prošlo**; cookies, proxy, fallback/chyby, PWA/offline/retry |
| Bezpečnostní politika CI | **11 prošlo** |
| Nové provozní regrese | **10 prošlo**: nový cíl, existující DB, traversal/odkazy, checksum, velikost, identity oprávnění, preflight a retence |
| Skutečná šifrovaná záloha/obnova do nového fyzického clusteru | Prošlo, **19 tabulek**, 3 účtenky s náhledy, souběžný zápis mimo snapshot, skutečný login/CSRF/Secure cookie a role |
| Špatná identity, zkrácený ciphertext a již existující cíl | Skutečně odmítnuto, původní DB se nepřepsala |
| Omezená aplikační DB role po obnově | SUPERUSER/CREATEDB/CREATEROLE = false, API zápisy sessions fungují |
| Access logy nginx/Gunicorn | Skutečná HTTPS žádost zaznamenala cestu/stav, syntetický soukromý query marker se v logu nevyskytl |
| Ruff/Oxlint/Prettier, typy, Vite/PWA build | Prošlo |
| Django check, migrace/makemigrations, OpenAPI shoda | Prošlo; žádné nové migrace/změny API |
| check --deploy | Jen známé security.W004 (HSTS=0 dle ADR-027), ostatní varování odmítnuta |
| Compose dev/prod/CI/operations/restore config | Prošlo standalone Compose 5.6.1, včetně izolace, rolí, portů a svazků |
| actionlint, shellcheck init-role.sh, syntaxe nginx, audit cest a Gitleaks historie | Prošlo; audit historie zopakován po lokálním commitu |
| Docker build/start/restart a obnova do Docker volumes | **Nelze spustit**: Docker CLI/daemon a Unix socket chybí |
| systemd-analyze a reálný časovač | **Nespouštěno**: na tomto Macu systemd není |
| Produkční HTTPS certifikát, NPM, off-host mount a produkční RPO/RTO | **Neprovedeno**: neznámé údaje a výslovný zákaz produkčního zásahu |

HTTPS test používá samopodepsaný localhost certifikát s výjimkou pouze v izolovaném headless testu. Není to důkaz platného veřejného certifikátu. HSTS nebylo kvůli testu zapnuto.

## Měření z posledního nativního obnovovacího cvičení

Zdroj obsahoval 3 syntetické účty, jedno sdílené auto, 3 nákupy a 3 malé syntetické PNG originály/JPEG náhledy. Dump a manifest pocházely z jednoho snapshotu; změna poznámek po dumpu zůstala mimo obnovenou DB, jak má být. Přesná kontrola před následnými API zápisy potvrdila otisky všech 19 tabulek včetně oprávnění a migrační historie.

- Šifrovaná záloha: **0,109 s**.
- Dešifrování, restore a porovnání dat: **0,148 s**.
- Inicializace odděleného clusteru + obnova + aplikační kontroly: **2,330 s**.
- Stáří snapshotu při dokončení datové kontroly: **0,963 s** – pouze simulované recovery okno, nikoli změřené produkční RPO.
- Obnovený výsledek analytiky: **45 l / 1800 Kč / 7,50 l/100 km**.

Časy jsou pro velmi malý vzorek, bez provisioning serveru, stahování images, NPM přepnutí nebo realistického objemu dat. Nelze z nich odvodit garantované RTO ≤4 h nebo RPO ≤24 h v produkci. Zdrojová DB a nový zastavený cluster jsou zachované v místním testovacím prostředí; žádný existující DB volume se nemazal. Testovací klíče a výsledky jsou jen v ignorovaném .runtime, nikoli v Gitu.

## Přesné lokální příkazy

Běžná aplikace s dostupným Dockerem, z kořene projektu:

```sh
python3 infra/setup_env.py
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py migrate
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py createsuperuser
```

Poslední příkaz pouze pro prvního správce; otevřete http://localhost:8080. Zastavení bez smazání dat: `docker compose -f compose.yaml -f compose.dev.yaml stop`. Nepoužívejte down -v/prune.

Na tomto Macu zůstává syntetický náhled http://127.0.0.1:8080 s DB tanklog_e2e. Pro opakovaný start při běžícím místním PG na portu 55432:

```sh
# Terminál 1, existující backend/.venv:
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py runserver 127.0.0.1:8000
# Terminál 2, existující frontend/node_modules:
PATH=/opt/homebrew/opt/node@26/bin:$PATH API_PROXY_TARGET=http://127.0.0.1:8000 HMR_CLIENT_PORT=8080 npm run dev --prefix frontend -- --host 127.0.0.1 --port 8080
```

Provedené hlavní kontroly (PostgreSQL CI DB je vyhrazená z předchozí fáze, nikoli běžná DB):

```sh
TANKLOG_CI=1 POSTGRES_DB=tanklog_phase6_ci POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 UV_COMMAND="$PWD/.tools/python/bin/uv" python3 infra/ci/run_checks.py backend
PATH="$PWD/.tools/node-ci/node-v26.13.0-darwin-arm64/bin:$PATH" python3 infra/ci/run_checks.py frontend
backend/.venv/bin/python -m unittest discover -s infra/ops/tests -v
COMPOSE_COMMAND=.tools/docker-compose python3 infra/verify_compose.py
shellcheck infra/postgres/init-role.sh
actionlint
TANKLOG_DRILL=1 POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python ../infra/ops/drill.py
```

Příprava místní CI DB je v CI.md. Nativní HTTPS start je v PHASE_5.md. E2E příkazy této etapy:

```sh
PATH="$PWD/.tools/node-ci/node-v26.13.0-darwin-arm64/bin:$PATH" E2E_BROWSER_CHANNEL=chromium E2E_BASE_URL=http://127.0.0.1:8080 npm run test:e2e --prefix frontend -- --grep-invert 'produkční nginx:|PWA:'
PATH="$PWD/.tools/node-ci/node-v26.13.0-darwin-arm64/bin:$PATH" E2E_BROWSER_CHANNEL=chromium E2E_PRODUCTION=1 E2E_HTTPS=1 E2E_BASE_URL=https://localhost:8443 npm run test:e2e --prefix frontend -- --grep 'produkční nginx:|PWA:'
```

## Ruční ověření a zbývající kroky

1. Projděte web: přihlášení, profil, auto, tankování, náhled účtenky, dashboard. Obnovte stránku a přihlaste se v druhém prohlížeči. Restart kontejnerů musí data zachovat; zde jej nelze ověřit.
2. Spusťte 10 provozních regresí a nativní drill výše. Výsledek musí mít verified:true, 19 tabulek, separate_cluster:true, omezenou roli a tři odmítnuté negativní případy.
3. S funkčním místním Dockerem zopakujte cvičení přes restore_compose.py podle OPERATIONS.md, se syntetickým archivem a --synthetic-check. Musí vzniknout nový projekt/svazek bez portů a NPM. Na konci se nic nemaže.
4. Zkontrolujte šablonu produkce a preflight. Prázdná/placeholder konfigurace musí být odmítnutá. Ověření skutečných domén, certifikátů, off-host úložiště a spuštěného scheduleru vyžaduje až konkrétní nasazení a autorizaci.
5. Před případnou produkcí dokončit inventář, odpovědnou osobu, dohled/alerty, retenci a kapacitní měření na realistických datech. Automatický purge není zapnutý; plán retence pouze označí kandidáty k revizi. Řízené migrace a rollback jsou v OPERATIONS.md.

Skutečné pokusy o dev start i produkční/operations build skončily na chybějícím /var/run/docker.sock; restore_compose.py odmítl pokračovat bez Docker CLI/daemonu. Nebyl vytvořen produkční NPM network ani vzdálený repozitář. Přetrvávají dříve uvedené limity úplného ručního přístupnostního/PWA ověření z fáze 5. Do další fáze se nepokračuje.
