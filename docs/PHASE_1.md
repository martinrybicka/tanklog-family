# Fáze 1 – implementace a ověření

Datum: 2. 11. 2026. Rozsah byl výslovně zadán uživatelem. Následný dodatek ukládá všechna trvalá aplikační data do DB a mění paletu na neutrální modrou/šedou/bílou. Další etapy se nezahajují.

**Stav:** funkce fáze 1 jsou implementované a běhově ověřené nativně. Docker konfigurace prošla kontrolami, ale běh kontejnerů a Docker build zůstávají neověřené, protože zde není Docker daemon. Nelze označit všechna Docker akceptační kritéria za splněná.

## Implementované funkce

- React 19 / TypeScript / Vite, Tailwind, Lucide, komponenty podle přístupu shadcn/ui s Radix dialogem, TanStack Query a RHF/Zod. Český responzivní shell, navigace podle role, světlý/tmavý/systémový motiv a neutrální modrošedý vzhled. Budoucí funkce jsou zřetelně označené jako připravované.
- Django 5.2 LTS / DRF / PostgreSQL. Vlastní UUID User od první migrace, case-insensitive unikátní jméno, role ADMIN/USER, profil a motiv uložené v DB. Konkrétní verze jsou zamknuté v obou lock souborech.
- Serverové DB sessions, CSRF i na anonymním loginu a logoutu, HttpOnly/SameSite cookies, rotace a odvolání sessions. Soukromé odpovědi no-store, žádné autentizační tokeny ani data v localStorage/IndexedDB.
- Správce vytváří účty, upravuje údaje/role, filtruje a stránkuje seznam a deaktivuje/aktivuje uživatele. Změna má ETag a ochranu před ztracenou editací; citlivé operace potvrzuje aktuálním heslem.
- Jednorázové dočasné heslo s nejméně 128 bity entropie, pouze hash v DB, expirace 24 h, zobrazení správci jen při vydání. Atomické spotřebování a omezená 15minutová session, povinná změna hesla i pro nového ADMIN. Vlastní administrační reset je odmítnutý; vlastní heslo se mění v Nastavení.
- Auth epoch v DB, odvolání starých sessions při resetu, změně hesla/role a deaktivaci. Posledního aktivního ADMIN chrání PostgreSQL transakční zámek i při souběžných požadavcích.
- Databázová ochrana loginu i opětovného potvrzení hesla u citlivých akcí přes django-axes (5 selhání účet+IP / 15 min), doplňkový nginx IP limit. Základní audit bez hesel a pouze čtecí auditní API pro ADMIN, bezpečné systémové informace, neveřejná readiness a minimální liveness.
- Vývojový Compose pro nginx/Vite/Django/PostgreSQL, port pouze `127.0.0.1:8080`, hot reload konfigurace. Produkční varianta se sestaveným SPA a Gunicornem, připnutými image digesty, bez host portů a bez vývojových mountů. Připravená sanitizace hlaviček za důvěryhodnou sítí NPM; skutečná síť se nevytvářela.
- `.env.example`, bezpečný lokální generátor bez přepisování existujícího `.env`, `.dockerignore`, strojová kontrola Compose a aktuální generované OpenAPI s chráněným JSON endpointem.

## Datová trvalost a dodatek uživatele

V této fázi jsou všechny účty, hashovaná hesla, profily, motivy, revize, audit, pokusy loginu i session záznamy v PostgreSQL. Smazání cookies jen ztratí identifikátor session; přihlášení stejným účtem obnoví přístup ke stejným datům. Změna jména/motivu není svázaná s konkrétním zařízením. Přechodné formuláře a query cache jsou v paměti a nepředstavují uložený záznam.

Budoucí originály i náhledy účtenek jsou podle aktualizovaného návrhu bytea v DB; žádný privátní souborový svazek není potřeba. Přílohy se stále implementují až ve fázi 3. Provozní secrets/config zůstávají v prostředí. Jediným svazkem trvalých aplikačních dat je `postgres_data`; vývojové `frontend_modules` obsahuje jen závislosti.

## Skutečně provedené kontroly

| Kontrola | Výsledek / rozsah |
| --- | --- |
| Backend pytest nad PostgreSQL | **36 prošlo**, včetně skutečného CSRF, negativních práv, hashů/expirace, resetu, deaktivace, ETag, limitů loginu i reautentizace, persistence profilu a souběžných požadavků |
| Frontend Vitest + Testing Library | **7 prošlo** ve 3 souborech: validace loginu/hesel, zobrazení chyb, směrování, CSRF/ETag a reakce na odvolanou session |
| Playwright Chrome | **6 prošlo**: 3 scénáře v desktopu a mobilu (390×844). Login/profil/logout; vytvoření a první změna hesla; smazání cookies a samostatný browser context se stejným DB profilem/motivem |
| Frontend typecheck + produkční build | Prošlo; administrace/formuláře se načítají po částech, žádný bundle warning nad 500 kB |
| Django `check` | Bez chyb a varování |
| Django `makemigrations --check --dry-run` | No changes detected; úvodní migrace skutečně aplikované na lokální PostgreSQL |
| OpenAPI `spectacular --validate --fail-on-warn` | Prošlo bez varování, aktuální výstup v `docs/openapi.yaml` |
| Ruff a formátování Python/TypeScript | Zkontrolováno; finální stav bez nalezených chyb |
| `uv lock --check`, `uv sync --frozen --dry-run` | Zámek konzistentní, 24 instalovaných balíčků beze změn |
| npm instalace / audit | Instalace podle přesných verzí; audit při instalaci hlásil 0 známých zranitelností |
| Dev + prod Compose `config --quiet` a kontrola JSON | Prošlo samostatným oficiálním Compose 5.6.1. Ověřeny sítě, jediný dev port, neveřejná DB/backend, svazky, oddělení variant a build targety |
| Pokus `compose up --build -d` | **Nelze spustit:** `/var/run/docker.sock` neexistuje. Žádný kontejner neběžel; výsledek není nahrazen tvrzením o úspěchu |
| Nativní Gunicorn s production settings | Skutečný start workeru, readiness/liveness 200, HTTP→HTTPS 301, neautorizované API za syntetickou HTTPS proxy hlavičkou 403 JSON; bez skutečného TLS/NPM |
| `check --deploy` s produkčními settings | Bez chyb, **jediné varování security.W004**: HSTS záměrně 0 do ověření skutečné HTTPS domény ve fázi 7. Varování není umlčené |
| Vizuální kontrola screenshotů | Prohlédnutý desktop i mobil; následně použita neutrální paleta a odstraněn přesah dekorace do mobilního textu |
| Kontrasty hlavních tokenů nové palety | 11,92; 5,77; 6,37; 15,87; 7,37; 7,47 : 1, všechny nad 4,5 : 1. Nejde o úplný audit přístupnosti fáze 5 |
| Čistota předávaných souborů | 89 zamýšlených souborů, 40 funkčních lokálních odkazů, bez provozních dat a místních secrets; výsledný frontend neobsahuje testovací hesla ani hodnoty z místního `.env` |
| Idempotence generátoru `.env` | Opakované spuštění nezměnilo existující obsah ani práva 600 |

Nativní prostředí: macOS ARM64, Python 3.14.6, Node 26.3.1, PostgreSQL 18.6. Image připravené pro Docker používají Python 3.14.10, Node 26.13.0, PostgreSQL 18.6 a nginx 1.30.2 na ověřených digestech. Test nativně nedokládá běh těchto image v Linuxu.

Pro backendové ověření byl lokálně doinstalovaný PostgreSQL 18 přes Homebrew (včetně jeho závislostí), bez zapnutí systémové služby. Testovací cluster je izolovaný v ignorovaném `.runtime/postgres` na localhost:55432; běžná DB, pytest DB a E2E DB jsou odlišné. Pomocné uv/Compose nástroje, cache, testovací data a screenshoty jsou ignorované. Žádná produkční data nebyla použita nebo přepsána. Po ověření se vlastní testovací servery zastaví, data se nemažou.

## Přesné ověřovací příkazy

Běžné spuštění i ruční scénáře jsou v [README](../README.md). S nainstalovaným Dockerem lze zopakovat konfigurační kontrolu bez kontaktování serveru NPM:

```sh
python3 infra/setup_env.py
python3 infra/verify_compose.py
```

Skript do podprocesu vkládá pouze syntetický CIDR/doménu pro kontrolu produkční topologie. Nevypisuje `.env`/secrets a nevytváří sítě ani kontejnery.

V tomto prostředí se skutečně použil samostatný lokální nástroj:

```sh
COMPOSE_COMMAND=.tools/docker-compose python3 infra/verify_compose.py
DOCKER_HOST=unix:///var/run/docker.sock .tools/docker-compose --env-file .env -f compose.yaml -f compose.dev.yaml up --build -d
```

Druhý příkaz skončil chybou připojení k chybějícímu lokálnímu daemonu. Ke kontrole nebyl použit žádný vzdálený Docker host. Připravený produkční build lze **po instalaci místního Dockeru** ověřit bez spuštění nebo vytvoření sítě NPM takto:

```sh
NPM_TRUSTED_CIDR=172.30.0.0/24 NPM_NETWORK_NAME=tanklog-verification-only docker compose -f compose.yaml -f compose.prod.yaml build backend web
```

Hodnoty zde jsou pouze pro build/konfigurační ověření, ne pro reálné nasazení. Nyní tento Docker build nebyl možný.

Nativní běhy v připraveném lokálním clusteru (cesty a port jsou specifické pro tento ověřovací prostředek):

```sh
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/pytest -q
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py check
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py makemigrations --check --dry-run
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py spectacular --file ../docs/openapi.yaml --validate --fail-on-warn
cd frontend
npm run test
npm run build
cd ..
```

Backend `.venv` vznikl přes `uv sync --frozen` z `backend/`; frontend potřebuje Node 26 a `npm ci`. Pytest vždy používá testovací settings podle `addopts` v pyproject. `infra/backend_command.py` načte `.env` a dovolí přepsat DB host/port pro nativní testování; secrets nevypisuje.

### Izolované E2E

Pro opakování vytvořte samostatnou DB `tanklog_e2e` ve svém **lokálním testovacím PostgreSQL**, přidělte přístup vývojovému DB účtu a proveďte:

```sh
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py migrate
TANKLOG_E2E=1 POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python tests/prepare_e2e.py
# První terminál:
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py runserver 127.0.0.1:8000
# Druhý terminál, z kořene:
API_PROXY_TARGET=http://127.0.0.1:8000 HMR_CLIENT_PORT=8080 npm run dev --prefix frontend -- --host 127.0.0.1 --port 8080
# Třetí terminál, z kořene:
npm run test:e2e --prefix frontend
```

Použijte Node 26 v PATH. Playwright zde používá nainstalovaný Chrome v oddělených testovacích kontextech, nikoli osobní profil. Alternativně nainstalujte Playwright Chromium a nastavte `E2E_BROWSER_CHANNEL=chromium`. Syntetický seed odmítá běžnou DB (vyžaduje `TANKLOG_E2E=1` a název končící `_e2e`). Nikdy ho nepouštějte nad skutečnými daty. Testy vytvářejí další syntetické účty a nic automaticky nemažou.

## Zbývající omezení a ruční Docker akceptace

1. Po instalaci Dockeru zopakovat čistý build/start, migrace a založení vlastního ADMIN podle README; ověřit `ps` healthchecky a localhost:8080.
2. Uložit profil/motiv, restartovat kontejnery a ověřit stejná data. Tato persistence je zajištěná DB svazkem v konfiguraci, ale restart kontejnerů zde neproběhl.
3. Upravit malý frontendový text a ověřit HMR bez ručního obnovení; obdobně backendový reload. Nativní vývojový server byl ověřen, Docker websocket/proxy cesta dosud neběžela.
4. Sestavit produkční image lokálně. Skutečný nginx runtime v image, skutečné předávání hlaviček přes NPM, certifikát a produkční restore jsou zatím neověřené; patří také do etap 5/7.
5. HSTS aktivovat až po ověření reálné HTTPS domény; před produkcí znovu `check --deploy` a bezpečnostní revize.
6. Před produkcí oddělit inicializační/správcovskou DB roli od aplikační role s minimálními právy. Současný lokální Compose používá `POSTGRES_USER` oficiálního image i pro Django, tedy vývojovou inicializační roli. Tato konfigurace není doporučením použít DB superuser pro veřejný provoz.

Vozidla, sdílení, tankování/přílohy, výpočty, XLSX, VIN, OCR a PWA zůstávají neimplementované podle roadmapy. Žádný GitHub remote/push, vzdálená síť ani produkční nasazení nevznikly. Fáze 2 vyžaduje další výslovný pokyn.

## Změněné části repozitáře

- Kořen: `AGENTS.md`, `README.md`, `.gitignore`, `.dockerignore`, `.env.example`, `compose.yaml`, `compose.dev.yaml`, `compose.prod.yaml`.
- `backend/`: pyproject/uv.lock/manage, settings a URL/WSGI, accounts (model, migrace, autentizace, práva, serializery, služby, views), audit (model/migrace), core (chyby, middleware, stránkování, schéma), testy a chráněná příprava E2E dat.
- `frontend/`: package/lock, Vite/TypeScript, React shell, UI, API klient a typy, login/profil/hesla/uživatelé/audit/systém, styly, komponentové/API testy, Playwright konfigurace a scénáře.
- `infra/`: Dockerfiles, nginx konfigurace a pomocné lokální/ověřovací skripty.
- Dokumentace: architektura, specifikace, datový model, API, UI/UX, bezpečnost, roadmapa, rozhodnutí, OpenAPI a toto předání. Historické ověření fáze 0 je zachované.

Přesný souborový seznam a lokální commit lze zkontrolovat pomocí `git show --stat --oneline HEAD`. Pracovní změny se předávají lokálním commitem, bez push.
