# Fáze 3 – tankování, účtenky, historie a XLSX

Datum: 2. 11. 2026. Uživatel výslovně schválil pouze fázi 3. Zachovaná architektura React/TypeScript/Vite + Django/DRF/PostgreSQL, jeden origin, sessions/CSRF a neutrální vzhled. Fáze 4 se nezahajuje, nic se neodesílá na GitHub ani produkci.

## Stav a omezení akceptace

Funkce fáze 3 jsou implementované a běhově ověřené nativně nad skutečným PostgreSQL. Konfigurace dev/prod Compose prošly. **Kontejnerový start, produkční Docker build, nginx runtime a persistence při restartu kontejnerů zůstávají neověřené**, protože místní Docker daemon neexistuje (`/var/run/docker.sock`). Oba skutečné pokusy o up/build selhaly na tomto důvodu; build navíc hlásí chybějící plugin buildx. Není tedy dokončené běhové Docker ověření a nativní testy je nenahrazují.

Žádná existující DB ani volume nebyly smazané. Migrace přidává nové tabulky do místních tanklog a oddělené syntetické tanklog_e2e. Automatické testy používají samostatnou pytest DB; E2E vytvořené nákupy/účty jsou syntetické, mimo běžná uživatelská data. Původní místní náhled je ponechaný spuštěný na http://127.0.0.1:8080/tankovani, aby šel rovnou otevřít.

## Implementované funkce

- Modely Refueling, ReceiptAttachment a RequestDeduplication s migrací. Decimal litry/cena/částka, DB kontroly kladných/nezáporných hodnot, rozsahu tachometru, plátce, pořadí dne a délky binárních příloh. Autor a editor se odvozují ze session, FK vozidla ani autor nelze přes PATCH měnit.
- Přesná částka z účtenky má prioritu. HALF_UP návrh při chybějící částce, rozlišení ENTERED/CALCULATED, zachování explicitní částky při dalších úpravách, odmítnutí vyšší přesnosti/NaN/Infinity. Nulový nákup vyžaduje výslovnou nulu a potvrzení; z nulové jednotkové ceny se potichu nevytváří.
- Serverový den Europe/Prague, datum bez času, odmítnutí budoucího dne. Volitelný tachometr, plná/částečná nádrž, palivo, stanice/vlastní název, poznámka, autor/plátce a mezera v evidenci. Minimální volby aktivních plátců s přístupem k autu, bez veřejného rosteru.
- Potvrzovaná varování pro odlišné palivo/částku, překročení nádrže, chybějící/klesající/podpočáteční km, podobný záznam, více tankování ve dni a nulu. Server je znovu ověřuje pod zámkem, potvrzení neobchází validaci. Při čtení se varování znovu odvozují z aktuální historie.
- Jednoznačné pořadí dne, vložení na pozici a přesun vlastního záznamu; úplné přeuspořádání jen OWNER/ADMIN s history ETag. Odložitelný UNIQUE a přečíslování dotčených dnů v transakci. Posunuté záznamy mají nové verze/editora a audit.
- Povinný UUID Idempotency-Key, atomický záznam výsledku a klíče, 24 h replay s novou autorizací, 409 při jiném obsahu/expiraci. Opakování po odstranění nebo odebrání přístupu nic nevytvoří ani neodhalí. Chyba validace/varování klíč nespotřebuje; klíče se zatím automaticky nepročišťují.
- Objektová práva navazují na vozidla. VIEWER pouze čte, CONTRIBUTOR přidá/upraví jen své aktivní záznamy a nesmaže je, OWNER/ADMIN opravuje i archivovanou historii. Archivované auto nepřijme nové tankování od nikoho. Historie nepoužívá kopie sdílených aut; autor ani plátce neuděluje přístup.
- JPEG/PNG originál i očištěný JPEG náhled jsou bytea v PostgreSQL. Limit 10 MiB / 24 MP, detekce skutečného formátu a MIME, odmítnutí animace/poškození, sanitizace názvu, hash originálu a odstranění EXIF z náhledu. Náhrada/smazání má práva editace a ETag tankování, znovu ověřené po dekódování. Neúspěšný upload nenaruší tankování ani předchozí přílohu.
- Receipt endpoint vyžaduje aktuální session a přístup, originál jde jako attachment s nosniff/CSP a soukromým no-store. Náhled není veřejný media soubor. Pokusy o upload mají DB limit 20/min/účet; nginx receipt má samostatný body limit 12 MiB a 30 požadavků/min/IP s burst 10 (runtime nginx v Dockeru neověřený).
- Historie s filtrem auta, inkluzivních datumů, paliva, stanice a hledání; stabilní řazení datum/částka/litry/tachometr, null tachometry vždy na konci. Desktopová tabulka, mobilní seznam a filtry v URL při návratu z detailu/editace/mazání.
- XLSX přes stejný autorizační/filtrovací selektor, celá množina do 50 000 řádků. Typované datumy a čísla, explicitní textové buňky včetně prefixů =/+/-/@ a whitespace, odstranění XML-nepřípustných řídicích znaků. Bez vzorců a URL účtenek. Prázdný export má záhlaví, překročený limit vyzve ke zúžení.
- České formuláře s desetinnou čárkou a přesným BigInt návrhem částky, potvrzovací dialogy, zachování hodnot po chybě, samostatné opakování uploadu u existujícího tankování, detail údajů/účtenky a celodenní pořadí. Obnovení focusu po dialogu je opravené také při odstranění spouštěcího ovladače.
- Audit změn, mazání a příloh bez obrázků či hesel. History_revision roste s tankováním, přílohou, pořadím a relevantními metadaty vozidla. Aktualizované kontrakty, OpenAPI, navigace a systémové informace.

Výpočty spotřeby/dashboard, OCR a VIN integrace se neimplementovaly. Syntetické JSON historie C05/C06/C14/C24 jsou připravené jako budoucí vstupy; test ověřuje jejich přijetí a pořadí, nikoli dosud neexistující výpočet. Fotografie po VIN zůstávají ve fázi 8 podle INTEGRATIONS.md.

## Výsledky testů

| Kontrola | Skutečný výsledek |
| --- | --- |
| Pytest / PostgreSQL 18.6 | **127 prošlo**, nad PostgreSQL (75 předchozích + 52 fáze 3) |
| Vitest + Testing Library | **17 prošlo** v 5 souborech (13 předchozích + 4 fáze 3) |
| Playwright Chrome | **14 prošlo** – 7 scénářů v desktopu a mobilu 390×844, přibližně 1,3 min; poslední doplnění refueling/focus ověřeno i samostatnými 4 E2E testy |
| TypeScript + Vite build | Prošlo, bez chyb a varování o velkém chunku |
| Django check | Bez chyb/varování |
| makemigrations --check --dry-run | No changes detected |
| Migrace | Nová úvodní refuelings migrace aplikovaná na místní tanklog/tanklog_e2e; pytest vytváří schéma od začátku |
| OpenAPI --validate --fail-on-warn | Prošlo, bez potlačení varování |
| Ruff / Prettier | Kód a formátování zkontrolované |
| uv lock --check / uv sync --frozen --dry-run | Konzistentní lock, 27 instalovaných balíčků, žádné další změny |
| Compose dev/prod config + JSON assertions | Obojí prošlo samostatným Compose 5.6.1 |
| Compose up / production build | **Nelze ověřit: chybí místní Docker daemon** |
| Vizuální kontrola | Prohlédnuté desktopové i mobilní screenshoty detailu/účtenky, E2E kontroluje vodorovný přesah |
| XLSX čtení | Sešit z API otevřený přes openpyxl: datumové/číselné typy, texty bez formulí, 30 vyfiltrovaných řádků i při stránce 25, prázdný výsledek a test nižšího limitu |

Částkové testy byly napsané a skutečně spuštěné **před** servisní implementací: první běh skončil na ModuleNotFoundError chybějící amounts služby. Potom prošly HALF_UP, priorita slevy/přesné částky, explicitní nula a chování PATCH. Nové závislosti byly ověřené v oficiálním registru a přesně uzamčené: [Pillow 13.0.0](https://pypi.org/project/pillow/), [openpyxl 3.1.5](https://pypi.org/project/openpyxl/); transitive et-xmlfile 2.0.0 je také v uv.lock. Ostatní závislosti nebyly upgradované.

Backend navíc ověřuje negativní role/IDOR, rozsahy a přesnost, pražský den při UTC přechodu, opakování a zánik přístupu/smazaný výsledek, ETag a pořadí dne, úplnost/stabilitu exportu, XML/formula prefixy, MIME spoofing, animovaný/poškozený/nadměrný obrázek, EXIF, průhledný PNG náhled na bílém podkladu, bezpečný název, soukromý download a neúspěšnou náhradu/rate limit. Tři souběžné scénáře fáze 3 pokrývají stejný klíč, dvě různé tvorby a editaci proti uploadu se stejným ETag. Regrese převodů/sdílení ze starších fází zůstávají zahrnuté.

Frontend testuje přesnou BigInt částku, neplatnou přesnost/chybějící cenu, potvrzení se stejným UUID klíčem, zachování částky a vstupů po síťové chybě. Dva nové E2E scénáře se opakují na desktopu/mobilu: kompletní create → vadný upload → úspěšný upload → filtr → XLSX → editace → delete a samostatný CONTRIBUTOR s vlastní/cizí historií, archivací a odebranou účtenkou. Starší E2E účtů/vozidel procházejí dál.

## Přesné příkazy pro lokální spuštění

Z kořene s nainstalovaným a běžícím **místním** Dockerem, Compose ≥ 2.24.4:

```sh
python3 infra/setup_env.py
docker compose -f compose.yaml -f compose.dev.yaml config --quiet
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py migrate
# Pouze první start prázdné databáze:
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py createsuperuser
```

Otevřít http://localhost:8080. Existující účet/DB se nepřepisuje. Stop zachovávající data: `docker compose -f compose.yaml -f compose.dev.yaml stop`. Nikdy nepoužívat down -v; pro ruční persistence test použít restart.

Na tomto Macu je připravený nativní cluster a náhled s oddělenou syntetickou DB tanklog_e2e. Procesy jsou ponechané spuštěné; **následující start použijte jen pokud neběží**:

```sh
cd /Users/mrybicka/Documents/Codex/tankovaci_aplikace
/opt/homebrew/opt/postgresql@18/bin/pg_ctl -D "$PWD/.runtime/postgres" -l "$PWD/.runtime/postgres.log" -o "-h 127.0.0.1 -p 55432 -k $PWD/.runtime" start
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py migrate
# Terminál 1:
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py runserver 127.0.0.1:8000
# Terminál 2, z kořene:
PATH=/opt/homebrew/opt/node@26/bin:$PATH API_PROXY_TARGET=http://127.0.0.1:8000 HMR_CLIENT_PORT=8080 npm run dev --prefix frontend -- --host 127.0.0.1 --port 8080
```

Python 3.14.6 / Node 26.3.1 / PostgreSQL 18.6 na macOS ARM64 jsou nativní QA prostředí, nikoli ověřený běh Docker image. Nainstalované závislosti odpovídají lockům; čistá instalace potřebuje uv sync --frozen v backend/ a npm ci s Node 26 ve frontend/. Příprava syntetického správce je chráněným skriptem backend/tests/prepare_e2e.py pouze pro *_e2e DB, s postupem v PHASE_1.md. Nespouštět jej nad běžnými daty.

## Přesné provedené kontroly

```sh
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/pytest -q
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py check
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py makemigrations --check --dry-run
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py spectacular --file ../docs/openapi.yaml --validate --fail-on-warn
PATH=/opt/homebrew/opt/node@26/bin:$PATH npm run test --prefix frontend
PATH=/opt/homebrew/opt/node@26/bin:$PATH npm run build --prefix frontend
PATH=/opt/homebrew/opt/node@26/bin:$PATH npm run test:e2e --prefix frontend
COMPOSE_COMMAND=.tools/docker-compose python3 infra/verify_compose.py
```

Skutečné neúspěšné pokusy bez vzdáleného Docker hostu:

```sh
DOCKER_HOST=unix:///var/run/docker.sock .tools/docker-compose --env-file .env -f compose.yaml -f compose.dev.yaml up --build -d
DOCKER_HOST=unix:///var/run/docker.sock NPM_TRUSTED_CIDR=172.30.0.0/24 NPM_NETWORK_NAME=tanklog-verification-only .tools/docker-compose --env-file .env -f compose.yaml -f compose.prod.yaml build backend web
```

Po instalaci Dockeru zopakovat up/build běžným docker compose, migrace, localhost/healthchecky, upload 1–10 MiB přes nginx, JSON 413/429, HMR a zachování historie/účtenek/auditu po restartu. Lokální produkční build nesmí vytvářet vzdálenou síť NPM ani připojovat produkční server. Produkční role DB, HTTPS/HSTS a ověřená obnova zůstávají podmínkami fází 5/7 podle předchozích předání.

## Ruční ověření a známé meze

Osmikrokový postup je v README v sekci „Ruční ověření tankování a účtenek“. Pro běžný průchod stačí aktivní auto, datum, litry a cena/částka; účtenka se nahrává až po uložení. Přesná částka se neztrácí po potvrzení ani opravě. Po smazání cookies nebo přihlášení jinde zůstávají historie i binární účtenky v DB; cookies jen identifikují session.

Klíče duplicit a auditní pokusy uploadu zatím nemají automatický cleanup (retenci před produkcí dořešit řízeně). Kompletní pořadí dne přijímá nejvýše 1 000 ID v jednom požadavku; běžné vložení/přesun funguje samostatně. Export 50 000 řádků je záměrný limit; velké exporty mohou vyžadovat užší filtr. Již doručený soubor/obrázek nelze zpětně odvolat z cizího zařízení. Offline ukládání ani měření spotřeby není součástí této fáze. Kompletní přístupnost, měření rychlosti a zálohy/restore se nepovažují za hotové.

## Změněné části

Nový backend/apps/refuelings/ (modely/migrace, Decimal služba, autorizační selektory, varování, transakční služby, obrázky, XLSX, prezentace, serializery/API/URL). Nové test_refueling_amounts.py, test_refuelings.py a JSON fixtures pro budoucí spotřebu. Frontend features/refuelings/ a pages/Refuelings.tsx, E2E refuelings.spec.ts. Upravené registrace backendu, core chyby pro varování, vozidlová práva/history_revision, systém/schema regresní test a lock závislostí. Rozšířené routy/navigace, API klient pro multipart/Blob/Idempotency-Key, typy, dialogový focus, karty/detail vozidel a styly. Nginx má specifické upload limity. README/AGENTS a relevantní kontrakty jsou aktualizované. Přesný seznam poskytne lokální git show --stat HEAD po commitu; provozní soubory, secrets, skutečné účtenky ani QA exporty se neverzují.
