# Fáze 4 – spotřeba, intervalové podklady a dashboard

Datum: 2. 11. 2026. Uživatel výslovně povolil fázi 4; předchozí fáze 1–3 zůstávají zachované. Fáze 5/PWA, VIN/OCR ani fotografie se nezahajují. Nic nebylo odesláno na GitHub ani na produkční server.

## Stav a omezení akceptace

Funkce fáze 4 jsou implementované. Nativní ověření běží proti skutečnému PostgreSQL 18.6, React/TypeScript/Vite a Django/DRF se zachovanými DB sessions a CSRF. Veškeré trvalé podklady jsou v PostgreSQL. Analytické výsledky jsou odvozené při čtení, bez nové tabulky nebo trvalého klientského úložiště. Nevznikla nová migrace.

**Docker runtime zůstává neověřený.** Dev/prod konfigurace prošly samostatným Compose 5.6.1. Skutečný pokus o vývojový start i lokální produkční build skončil na chybějícím daemonu/socketu `/var/run/docker.sock`; build také hlásil nepřítomný buildx plugin. Nelze tedy tvrdit, že kontejnery, nginx/HMR nebo restart s persistencí byly ověřené. Nativní build ani testy tyto části nenahrazují. Žádná běžná DB ani volume nebyly odstraněné a žádná produkční síť nebyla vytvořená nebo připojená.

## Implementované funkce

- Čisté immutable DTO a Decimal algoritmus plná–plná. Počáteční nákup kotvy není součástí měření, ale zůstává v nákupech. Mezilehlé částečné i plné nákupy bez km přispívají litry/částkou; plná bez odečtu není hranice.
- Kontrola celé historie před filtrováním: pokles tachometru blokuje dotčené kandidáty až do opravy včetně již uzavřeného intervalu podle C15/C30. Podpočáteční odečet zneplatní měření. Nulová vzdálenost, mezera v evidenci, smíšené palivo a více nádrží mají konkrétní důvody; spotřeba se neodhaduje.
- Vážené součty platných litrů/km a částek/km, oddělené skupiny paliv, žádné násobení sdílené historie. Realizovaná nákupní cena je celková částka / litry. Kč/100 km je výslovně nákupní náklad v intervalech, nikoli přesná cena spálené zásoby.
- Nákupy podle vlastního data, měření podle koncového plného tankování. Výchozí pražský měsíc, den, týden od pondělí, rok a vlastní inkluzivní rozsah. Šipky posouvají kalendářní období; vlastní rozsah o stejný počet dnů, nezávisle na změně času.
- Autorizované dashboard/statistics API, stránkované intervaly a detail s konkrétními tankováními i kotvou mimo filtr. Po změně hranic původní interval vrátí 404. Srovnání normy pouze pro explicitně vybrané auto s kladnou normou a odpovídající skupinou paliva, se zdrojem/metodikou.
- Konzistentní PostgreSQL REPEATABLE READ READ ONLY snapshot zahrnuje novou kontrolu účtu/session, práva, metadata i historii. Statistické služby nesmějí být obalené ATOMIC_REQUESTS nebo dřívějším atomic blokem. Již zahájené čtení může dokončit starý snapshot; nové čtení po odebrání přístupu vrátí 404.
- Dashboard se skutečnými nákupními kartami, pokrytím (platné/vyřazené intervaly, km, hranice, důvody), posledními tankováními a odkazy na opravu historie. Auto lze přepnout včetně archivovaných. Filtry jsou v URL.
- Recharts výdajů, vážené ceny a spotřeby jednotlivých aut/paliv, jednotky a tabulkové alternativy. Null přeruší řadu, samostatný platný cenový bod zůstane vidět. API ratio 6 míst, UI 2 HALF_UP přes BigInt, litry podkladů 3 místa. Žádné klientské účetní agregace nebo uložené osobní preference.
- Invalidace analytických query po změně tankování, pořadí, metadat či práv; nové čtení při návratu/focusu a po 30 s. Logout vyčistí soukromou paměťovou cache, API má private,no-store. Neutrální modrošedý/bílý vzhled v existujících motivech.

## Skutečné výsledky ověření

| Kontrola | Výsledek |
| --- | --- |
| C01–C34 + immutable/determinismus | 35 testů prošlo; napsané a spuštěné před implementací služby |
| Celý pytest / PostgreSQL | **189 prošlo**, včetně předchozích 127 testů |
| Vitest + Testing Library | **23 prošlo**, včetně 6 nových testů kalendáře, HALF_UP/null a podkladů |
| Playwright Chrome desktop + mobil 390×844 | **16 prošlo**, 8 scénářů na každém viewportu; hlavní analytický průchod včetně opravy a tabulky |
| Vizuální kontrola | Prohlédnuté desktopové a mobilní screenshoty; E2E kontroluje nepřesahující šířku stránky |
| TypeScript + Vite build | Prošlo, žádná chyba nebo varování o velkém chunku |
| Django check | Bez chyb/varování |
| makemigrations --check --dry-run | No changes detected |
| OpenAPI --validate --fail-on-warn | Prošlo, strukturované kontrakty analytických odpovědí |
| Ruff a Prettier | Zkontrolovaný kód i formátování |
| uv lock / frozen sync dry-run a npm ls | Lock konzistentní, 27 backendových balíčků, žádné změny; přímé JS závislosti odpovídají přesným verzím |
| Compose dev/prod config + assertions | Obojí prošlo |
| Compose up / produkční Docker build | Nelze dokončit: chybí lokální Docker daemon |

První běh čistých výpočtových testů skončil očekávaně `ModuleNotFoundError: apps.analytics.consumption`, následně všech 35 prošlo. Ručně stanovené výsledky z CONSUMPTION.md mají samostatné C01–C34 testy, nikoli kopii algoritmu. Dalších 6 kalendářních a 21 transakčních API testů ověřuje období, přestupnost/změny času, nákupní filtry a celou historii, normu, druhy paliv, archivaci, role/IDOR/deaktivaci, redundantní grant, přepočet po opravě/mazání/vložení, stránkování a zánik intervalu. Skutečné souběhy zahrnují konzistenci snapshotu při změně litrů, dva zápisy pořadí se stejným ETag a tvorbu tankování při odebrání grantu.

Poslední drobná úprava rozestupů a viditelnosti samostatných bodů byla znovu ověřená oběma analytickými E2E průchody (desktop/mobil); kompletní sada předtím prošla v 1,9 min. Screenshoty jsou pouze v ignorované .runtime.

Recharts **3.10.1** byl ověřen v [oficiální dokumentaci](https://recharts.github.io/en-US/guide/) a npm metadatech a přesně uzamčen v package.json/package-lock.json včetně tranzitivních závislostí. Instalace hlásila 0 zranitelností. Ostatní přímé závislosti nebyly upgradované. Backendový uv lock se neměnil.

## Přesné příkazy pro lokální spuštění

Z kořene repozitáře s místním Dockerem a Compose ≥ 2.24.4:

```sh
cd /Users/mrybicka/Documents/Codex/tankovaci_aplikace
python3 infra/setup_env.py
docker compose -f compose.yaml -f compose.dev.yaml config --quiet
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py migrate
# Jen při prvním startu nové prázdné DB:
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py createsuperuser
```

Otevřít http://localhost:8080. U existujícího vývojového frontend_modules po změně locku spusťte `docker compose -f compose.yaml -f compose.dev.yaml exec frontend npm ci`. PostgreSQL nemá veřejný host port. Bezpečné zastavení: `docker compose -f compose.yaml -f compose.dev.yaml stop`; restart pro kontrolu persistence: `docker compose -f compose.yaml -f compose.dev.yaml restart`. Nepoužívat down -v.

Na tomto Macu je již připravený nativní cluster a oddělená syntetická databáze tanklog_e2e. Náhled je ponechaný spuštěný na http://127.0.0.1:8080. Následující start použijte pouze pokud procesy neběží:

```sh
cd /Users/mrybicka/Documents/Codex/tankovaci_aplikace
/opt/homebrew/opt/postgresql@18/bin/pg_ctl -D "$PWD/.runtime/postgres" -l "$PWD/.runtime/postgres.log" -o "-h 127.0.0.1 -p 55432 -k $PWD/.runtime" start
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py migrate
# Terminál 1:
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py runserver 127.0.0.1:8000
# Terminál 2, z kořene:
PATH=/opt/homebrew/opt/node@26/bin:$PATH API_PROXY_TARGET=http://127.0.0.1:8000 HMR_CLIENT_PORT=8080 npm run dev --prefix frontend -- --host 127.0.0.1 --port 8080
```

Nativní runtime Python 3.14.6 / Node 26.3.1 / PostgreSQL 18.6, macOS ARM64; není to ověřený běh Docker image. Čistá instalace závislostí: `uv sync --frozen` v backend/ a `npm ci` s Node 26 ve frontend/. Syntetický E2E správce se připravuje jen přes chráněný backend/tests/prepare_e2e.py nad *_e2e DB podle PHASE_1.md; do běžných dat se žádné výchozí heslo nezavádí.

## Příkazy použitých kontrol

```sh
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/pytest -q
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py check
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py makemigrations --check --dry-run
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py spectacular --file ../docs/openapi.yaml --validate --fail-on-warn
PATH=/opt/homebrew/opt/node@26/bin:$PATH npm run test --prefix frontend
PATH=/opt/homebrew/opt/node@26/bin:$PATH npm run build --prefix frontend
PATH=/opt/homebrew/opt/node@26/bin:$PATH npm run test:e2e --prefix frontend
backend/.venv/bin/ruff check backend
backend/.venv/bin/ruff format --check backend
PATH=/opt/homebrew/opt/node@26/bin:$PATH npx --prefix frontend prettier --check frontend/src frontend/e2e/analytics.spec.ts
COMPOSE_COMMAND=.tools/docker-compose python3 infra/verify_compose.py
```

Skutečné neúspěšné místní pokusy o Docker bez přístupu k produkci:

```sh
DOCKER_HOST=unix:///var/run/docker.sock .tools/docker-compose --env-file .env -f compose.yaml -f compose.dev.yaml up --build -d
DOCKER_HOST=unix:///var/run/docker.sock NPM_TRUSTED_CIDR=172.30.0.0/24 NPM_NETWORK_NAME=tanklog-verification-only .tools/docker-compose --env-file .env -f compose.yaml -f compose.prod.yaml build backend web
```

Po instalaci daemonu zopakovat skutečný up, migrace, živost/připravenost, frontend/API přes nginx, HMR a zachování historie/účtenek/statistik po restartu. Produkční build je lokální, neopravňuje připojení k produkční síti nebo nasazení.

## Ruční ověření a známé meze

Osmikrokový scénář v README („Ruční ověření spotřeby a dashboardu“) používá kotvu 50 l, mezilehlých 20 l a koncových 25 l / 600 km. Únor: nákupy 45 l / 1 800 Kč, spotřeba 7,50, nákupní náklad 300 Kč/100 km, norma 6 se rozdílem 1,50 / 25 %. Kotva 31. 1. je v detailu, nikoli v únorových nákupech. Filtr jen 1. 2. má 20 l a null spotřebu; oprava 20→15 přepočte na 6,67. Dále ověřte mezeru, archivaci, sdílení/odebrání a nové přihlášení na jiném zařízení.

Výpočet čte celou historii přístupných aut, bez příloh; pro velmi velkou instalaci zatím nejsou naměřené limity ani zavedená analytická cache. Nákupní graf má limit 5 000 skupin a tabulky mají vlastní posuv. Více nádrží, CNG/EV, výměna tachometru po segmentech a chybějící nákupy se neodhadují; jde o další samostatně schvalované rozšíření. DB podklady a uložený motiv jsou stejné pro všechna zařízení, samotný URL filtr není osobní preference ukládaná do profilu. Kompletní přístupnost/PWA a produkční zálohy/restore zůstávají pozdější fáze. Již doručená soukromá data nelze zpětně odvolat.

## Změněné části

Nový backend/apps/analytics/ (čistý výpočet, kalendář, snapshot služby, kontrakty/API a URL), test_consumption.py/test_periods.py/test_analytics.py. Registrace URL, systémová fáze/verze a schema test. Nové frontend/features/analytics/, pages/Dashboard.tsx a e2e/analytics.spec.ts, Recharts lock. Routy a přehled, odkazy vozidel, invalidace tankování/metadat/grantů a dashboardové styly. README, AGENTS, specifikace/metodika/model/API/OpenAPI/architektura/bezpečnost/UI/rozhodnutí/roadmapa. Přesný seznam poskytne lokální git show --stat HEAD; .env, databáze, screenshoty a syntetické běhové výstupy se neverzují.
