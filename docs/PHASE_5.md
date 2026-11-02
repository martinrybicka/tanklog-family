# Fáze 5 – responzivita, UX, PWA základ a bezpečnost

Datum: 2. 11. 2026. Výslovně povolená je jen fáze 5. Architektura React/TypeScript/Vite + Django/DRF/PostgreSQL, jeden origin, sessions a CSRF zůstává. Nic nebylo odesláno na GitHub ani na produkční server. Fáze 6 se nezahajuje.

## Stav a hranice akceptace

Funkce fáze 5 jsou implementované a lokálně testované. **Akceptace není plně ověřená:** stále chybí běh Docker images/restart/persistence, skutečný nativní zoom 200 %, poslech VoiceOver a reprezentativní měření člověkem. Tyto části se nepovažují za prošlé. Automatický reflow při odpovídající CSS šířce, axe v obou motivech a ruční klávesnice/AX prošly.

Docker daemon ani CLI nejsou dostupné, samostatný Compose 5.6.1 ověřil konfigurace. Skutečný dev up i produkční build selhaly na chybějícím socketu `/var/run/docker.sock`, build také hlásil nepřítomný buildx. Jako doplňkové ověření byl instalován místní nginx 1.31.7 přes Homebrew (bez systémové služby) a spuštěn skutečný Vite build/Gunicorn 26.2.0/production settings přes lokální HTTPS proxy. To ověřuje šablony a chování aplikace, **nenahrazuje pinned Docker nginx 1.30.2 ani skutečnou NPM síť**.

Žádná běžná databáze nebo volume nebyly odstraněné. Testy používaly pytest databázi a syntetickou tanklog_e2e. TLS certifikát/klíč, logy a screenshoty jsou jen v ignorované .runtime; klíč má práva 600 a nebyl instalován do důvěry OS. Všechny náhledové porty jsou jen loopback. Vývojový náhled zůstává dostupný na http://127.0.0.1:8080.

## Implementované funkce

- Manifest s vlastním názvem, scope/id/start_url, standalone a ikonami 192/512, maskable a apple-touch. Vlastní pumpa má SVG zdroj a reprodukovatelný Pillow generátor; žádné externí fotografie nebo loga.
- Build generuje service worker z pevného allowlistu veřejných assets/ikon/offline stránky/manifestu. Instalace bez cookies, žádné dynamické ukládání navštívených URL. API, receipt, XLSX, mutace a cizí originy se nikdy neobsluhují z cache. Offline navigace má obecnou českou stránku bez účtu a záznamů.
- Aktualizace čeká; načtení nové verze vyžaduje upozornění na neuložený formulář. Aktivace odstraní staré veřejné cache. PWA se registruje pouze v produkčním buildu. Nastavení nabízí informace a podle podpory instalační tlačítko prohlížeče.
- Offline stav vysvětluje nutnost serveru a dočasnost vstupů. Chyba spojení zachová formulář v paměti okna, retry drží původní idempotency klíč. ErrorBoundary zachytí chybu rozhraní/chybějící chunk a nabídne obnovu.
- Tablet do 1023 px používá mobilní navigaci. Min. 44 px pro dotykové akce, zalamování nadpisů/akcí, vlastní posuv tabulek, odstranění plovoucího odhlášení překrývajícího obsah. Vizuálně nalezené zúžení mobilního obsahu je opravené a test hlídá plnou šířku.
- Focus hlavního obsahu a název dokumentu při navigaci, zachovaný focus trap/Escape/návrat dialogů. Field propojí hint/error přes aria-describedby a označí vadná pole. Login má správnou hierarchii nadpisů a logo název odvozený z viditelného textu.
- Systémový motiv před přihlášením i na loginu, DB preference po přihlášení. Světlá/tmavá neutrální paleta a reduced-motion. Globální zadání přebírá právě vybrané auto z URL, bez klientské uložené preference.
- Query/mutation gcTime=0; při 403/404 se odstraní stará úspěšná data vadného query. Logout vymaže cache a CSRF bez další závislosti na síti, BroadcastChannel odhlásí ostatní okna. Návrat z BFCache ověří session reloadem. Žádná osobní data v localStorage/sessionStorage/IndexedDB/CacheStorage.
- JSON a bezpečnostní hlavičky u proxy chyb 413/429/503 a skrytého readiness 404; samotné /api nikdy není HTML fallback. Django chybný Host/JSON vrací soukromý JSON 400. Produkční fallback, Secure cookies a sanitizace forwarded proto ověřené lokálně.
- Přesně zamčený Oxlint a axe-core Playwright, reprodukovatelné testy veřejné cache, offline retry, více oken, rozvržení a přístupnosti. Systémové API verze 0.5.0/fáze 5, OpenAPI popis odpovídá aktuální aplikaci. Bez změny DB schématu.

## Skutečné výsledky

| Kontrola | Výsledek |
| --- | --- |
| Pytest nad PostgreSQL 18.6 | **192 prošlo** (189 předchozích + HTTPS/CSRF/chyby/forwarded testy) |
| Vitest + Testing Library | **28 prošlo**, 8 souborů; nově odebraná query data a čtyři bezpečnostní testy workeru |
| Regresní Playwright Chrome | **22 prošlo**, desktop + 390×844, 3,3 min; účty/vozidla/tankování/analytika a nové quality scénáře |
| Produkční HTTPS Playwright | **6 prošlo**, 3 scénáře × desktop/mobil: nginx/cookies/JSON/PWA/offline/retry |
| Axe WCAG 2 A/AA + 2.1 A/AA | Žádné hlášené porušení v testovaných obrazovkách a dialogu ve světle/tmě na desktopu/mobilu; poslední 4 quality průchody znovu prošly po opravě mobilní šířky |
| Šířky a reflow | 360/390/768/1024/1440 px; 720×450 CSS px pro reflow odpovídající 1440/200 %; bez přesahu stránky, mobilní obsah má plnou šířku |
| Ruční klávesnice / AX | Tab/Enter prázdného loginu → české chyby a focus uživatelského jména; mobilní uložení a focus detailu |
| Skutečný zoom / VoiceOver | **Neověřeno**; nativní browser ovládání bylo nástrojem zablokované kvůli aktuální URL, zvukový výstup čtečky nebyl posouzen |
| Mobilní čas | Asistované vyplnění **7,298 s**, nikoli reprezentativní měření člověkem cíle 15–30 s |
| Typecheck / Oxlint / Vite build | Prošlo, bez chyb a varování velkého chunku; sw.js skutečně generovaný |
| Ruff / Prettier | Kód i formátování zkontrolované |
| Django check / migrace / OpenAPI | Bez problémů, No changes detected, schema validate/fail-on-warn prošlo |
| check --deploy | Pouze známé **security.W004**, HSTS=0 podle ADR-027; nic není potlačené |
| Npm audit | **0 známých zranitelností** |
| pip-audit 2.10.1 | **No known vulnerabilities found**, audit všech připnutých produkčních Python závislostí z uv export |
| uv lock --check | Konzistentní, backendové závislosti se neměnily |
| Compose dev/prod config | Obojí prošlo, včetně portů/sítí/svazků/build targetů |
| Docker up / produkční build | **Nelze spustit**, chybí daemon/socket; nativní HTTPS test je doplněk |
| Nginx při zastavení backendu | Skutečný **JSON 503**, private,no-store a nosniff; následně backend znovu spuštěn |
| Nginx login limit | Skutečný **JSON 429**, Retry-After 900 a bezpečnostní hlavičky; test bez CSRF nezatěžoval účet heslovými pokusy |

První pokusy testů odhalily neúplný přístupný název loga, rozvržení mobilního odhlášení a testovací chybějící HTTPS Origin; opraveno a znovu ověřeno. Paralelní Playwright procesy původně kolidovaly v artefaktech (ENOENT při uzavírání trace); konfigurace nyní odděluje .runtime/playwright-production a .runtime/playwright-development a produkční sada poté prošla. Finální výsledek není tvrzení, že všechny průběžné pokusy prošly.

Oxlint 1.90.0 a @axe-core/playwright 4.14.0 byly ověřené v oficiálním npm registru a uzamčené v package-lock.json. Dokumentace: [Oxlint konfigurace](https://oxc.rs/docs/guide/usage/linter/config), [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing), [MDN service worker](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API). Nepřidává se React Compiler, proto se nevynucuje incompatible-library nad RHF. Prefer-tag-over-role je vypnuté pro legitimní role status/img; input/td u statického názvu kontroluje výsledné DOM pomocí axe. Ostatní correctness/a11y kontroly běží bez varování. Pip-audit je dočasný izolovaný auditní nástroj, nikoli backendový runtime dependency.

## Přesné lokální spuštění

Z kořene, s místním Dockerem a Compose ≥ 2.24.4:

```sh
cd /Users/mrybicka/Documents/Codex/tankovaci_aplikace
python3 infra/setup_env.py
docker compose -f compose.yaml -f compose.dev.yaml config --quiet
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py migrate
# Jen nová prázdná DB:
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py createsuperuser
# Při existujícím frontend_modules po změně locku:
docker compose -f compose.yaml -f compose.dev.yaml exec frontend npm ci
```

Otevřít http://localhost:8080. Vývojový Vite neregistruje worker; PWA se testuje z produkčního buildu. Stop zachovávající data: `docker compose -f compose.yaml -f compose.dev.yaml stop`. Pro persistence test použijte restart; nikdy down -v. Produkční build lze lokálně sestavit, ale tím není povolené nasazení nebo vytvoření NPM sítě.

Připravený nativní Mac náhled (použít start jen pokud procesy neběží):

```sh
cd /Users/mrybicka/Documents/Codex/tankovaci_aplikace
/opt/homebrew/opt/postgresql@18/bin/pg_ctl -D "$PWD/.runtime/postgres" -l "$PWD/.runtime/postgres.log" -o "-h 127.0.0.1 -p 55432 -k $PWD/.runtime" start
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py migrate
# Terminál 1:
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py runserver 127.0.0.1:8000
# Terminál 2:
PATH=/opt/homebrew/opt/node@26/bin:$PATH API_PROXY_TARGET=http://127.0.0.1:8000 HMR_CLIENT_PORT=8080 npm run dev --prefix frontend -- --host 127.0.0.1 --port 8080
```

Závislosti: Python 3.14, Node 26, PostgreSQL 18, instalace přes uv sync --frozen v backend/ a npm ci ve frontend/. Syntetický E2E správce se připravuje pouze chráněným backend/tests/prepare_e2e.py nad *_e2e DB podle PHASE_1.md. Běžná uživatelská DB nemá výchozí účet/heslo.

## Lokální produkční HTTPS ověření bez Dockeru

Vyžaduje nginx a OpenSSL; na tomto Macu byl použit Homebrew nginx 1.31.7 bez `brew services start`. Nezasahuje do běžícího vývojového náhledu ani do serveru. Backend musí běžet nad **syntetickou tanklog_e2e**, ne běžnými daty:

```sh
# Z kořene, sestavit nejdříve:
PATH=/opt/homebrew/opt/node@26/bin:$PATH npm run build --prefix frontend
# Terminál 3:
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 DJANGO_SETTINGS_MODULE=config.settings.production DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost:8443 DJANGO_DEBUG=false DJANGO_SECURE_COOKIES=true python3 infra/backend_command.py .venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8001 --workers 2 --timeout 35 --error-logfile -
# Terminál 4:
python3 infra/local_production_preview.py
# Terminál 5, po připravenosti:
E2E_PRODUCTION=1 E2E_HTTPS=1 E2E_BASE_URL=https://localhost:8443 PATH=/opt/homebrew/opt/node@26/bin:$PATH npm run test:e2e --prefix frontend -- --grep 'produkční nginx:|PWA:'
```

Testovací certifikát je samopodepsaný. Pouze izolované headless E2E na localhost ignoruje jeho nedůvěru; konfigurace odmítne takový test proti vzdálenému hostu. Žádná změna systémové důvěry ani obcházení uživatelova browser varování se neprovádí. Pro ruční instalaci PWA na fyzickém zařízení je potřeba důvěryhodný HTTPS origin; zde se nepředstírá její ověření. Nginx config lze jen zkontrolovat `python3 infra/local_production_preview.py --check`; na jiném systému případně nastavte NGINX_MIME_TYPES. Terminály 3/4 ukončete Ctrl+C; nic z DB se nemaže. Vnější testovací proxy má limit 16 MiB, aby skutečné aplikační limity 1/12 MiB vrátily JSON; při budoucím NPM provozu nesmí vnější proxy tyto požadavky odříznout vlastním HTML limitem.

## Provedené příkazy kontrol

```sh
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/pytest -q
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py check
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py makemigrations --check --dry-run
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py spectacular --file ../docs/openapi.yaml --validate --fail-on-warn
PATH=/opt/homebrew/opt/node@26/bin:$PATH npm run test --prefix frontend
PATH=/opt/homebrew/opt/node@26/bin:$PATH npm run lint --prefix frontend
PATH=/opt/homebrew/opt/node@26/bin:$PATH npm run build --prefix frontend
PATH=/opt/homebrew/opt/node@26/bin:$PATH npm run test:e2e --prefix frontend -- --grep-invert 'produkční nginx:|PWA:'
COMPOSE_COMMAND=.tools/docker-compose python3 infra/verify_compose.py
PATH=/opt/homebrew/opt/node@26/bin:$PATH npm audit --prefix frontend --audit-level=low
.tools/python/bin/uv lock --check --project backend
.tools/python/bin/uv export --frozen --no-dev --no-hashes --project backend --output-file .runtime/backend-audit.txt
.tools/python/bin/uv tool run --from pip-audit==2.10.1 pip-audit --no-deps --disable-pip -r .runtime/backend-audit.txt --progress-spinner off
```

`check --deploy` použil stejné produkční proměnné jako terminál 3 a manage.py check --deploy. Ruff kontroluje backend, local_production_preview.py i generátor ikon; Prettier frontend, E2E a veřejné HTML/CSS/manifest. Skutečné neúspěšné Docker pokusy:

```sh
DOCKER_HOST=unix:///var/run/docker.sock .tools/docker-compose --env-file .env -f compose.yaml -f compose.dev.yaml up --build -d
DOCKER_HOST=unix:///var/run/docker.sock NPM_TRUSTED_CIDR=172.30.0.0/24 NPM_NETWORK_NAME=tanklog-verification-only .tools/docker-compose --env-file .env -f compose.yaml -f compose.prod.yaml build backend web
```

## Ruční postup a známé meze

Sedm kroků v README („Ruční ověření UX a PWA“) zahrnuje klávesnici/dialog, všechny šířky/zoom, systémový i pevný motiv, instalaci, offline navigaci, retry a více oken. Pro doménovou regresi zůstává scénář 50 l kotva → 20 l částečně → 25 l koncová plná / 600 km = 7,50 z PHASE_4.md.

Asistované ruční měření při 390×844: předvybrané uložené auto a dnešní datum, 42,350 l / 38,90 Kč/l / 10 000 km, částečná nádrž, uložit → detail 1 647,42 Kč. Od prvního vstupu po načtený detail 7,298 s, bez přihlášení/volby auta/účtenky. Je rychlejší díky asistovanému vyplnění; cíl 15–30 s s člověkem nebyl ověřený. Provedené UX opravy jsou předvyplnění auta a odstranění překrývajícího odhlášení.

Pokus o nativní kontrolu zoomu byl nástrojem zastaven kvůli aktuální URL. Po zastavení se v nativním prohlížeči nepokračovalo. Hlasový výstup čtečky nebyl posouzen. Žádná automatická kontrola ani AX strom se nepovažuje za úplný audit VoiceOver/NVDA. Ruční ověření skutečného 200% zoomu, čtečky a uživatelského času proto zůstává otevřené, stejně jako fyzická instalace Android/iOS. Nativní screenshoty světla/tmy byly vizuálně prohlédnuté, jsou jen v .runtime.

Další známé hranice: HSTS=0 do konkrétního schváleného HTTPS nasazení; chybějící Docker daemon; nevykonané zálohy/restore a produkční DB role podle fáze 7. PWA není offline databáze. Již doručené údaje nelze zpětně odvolat a rozepsaný formulář se po reloadu ztratí. Fáze 6/GitHub ani nasazení nejsou součástí tohoto předání.

## Změněné části

Frontend public/ (manifest/ikony/offline), scripts/ (worker a ikony), nové Pwa/RouteFocus/AppErrorBoundary, queryClient/sessionEvents a testy. Změněný shell, Field, login, nastavení, CSS, API bootstrap, build/lint skripty, lock a Playwright konfigurace. Nové quality/production E2E a worker/cache unit testy. Backend přidává JSON 400 handler, produkční bezpečnostní testy a fázi/verzi/schema popis. Nginx doplňuje veřejný PWA routing a bezpečné JSON chyby; nový lokální HTTPS helper. README/AGENTS a relevantní kontrakty, roadmapa a rozhodnutí jsou aktualizované. Žádná migrace. Přesný seznam je v lokálním git show --stat HEAD po commitu.
