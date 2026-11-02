# Fáze 2 – vozidla a sdílení

Datum: 2. 11. 2026. Uživatel výslovně upřesnil rozpor v zadání odpovědí „Implementovat fázi 2“. Fáze 3 a další nejsou zahájené. Nedošlo k žádnému GitHub push ani produkčnímu nasazení.

## Výsledek a hranice ověření

Funkce fáze 2 jsou implementované a ověřené nativně nad skutečným PostgreSQL. Vývojová i produkční Compose konfigurace prošla kontrolou. **Docker runtime a sestavení image zůstávají neověřené**, protože místní Docker daemon chybí. Pokusy o `up --build -d` i produkční `build backend web` skutečně skončily chybou `/var/run/docker.sock: no such file or directory`; build navíc oznámil chybějící plugin buildx. Nelze tvrdit, že kontejnerová akceptace je kompletní. Zůstává také omezení produkční DB role/HSTS popsané v PHASE_1.md; nebylo předmětem vzdálené konfigurace.

## Implementované funkce

- Vehicle/VehicleAccess s UUID, migračními soubory, jedním vlastníkem, databázovými kontrolami a unikátními granty/VIN. Veškerá uložená data jsou v PostgreSQL, bez persistence v prohlížeči.
- Vytvoření vlastního auta, čtení přístupných aut bez duplikací, editace OWNER/ADMIN, archivace/obnovení bez mazání. Běžný serializer nepřijímá vlastníka, stav, verze ani jiné interní údaje. Veřejný DELETE auta není dostupný; nahrazuje jej archivace podle ADR-030.
- Povinný název/značka/model/palivo/počáteční km. Volitelné rok, RZ, ruční VIN, objem/výkon/nádrž, režim jedné/více nádrží, norma/metodika/zdroj/poznámka. Přesné Decimal hodnoty, číselné rozsahy a odmítnutí vyšší přesnosti; normalizace VIN a RZ. Konflikt VIN má obecnou chybu bez údajů cizího auta.
- Sdílení pouze ADMIN: grant VIEWER/CONTRIBUTOR, změna role a potvrzené odebrání. Aktivní účty se hledají a stránkují přes chráněný administrační endpoint. Vlastníkovi ani duplicitní grant nevzniká; neaktivní účet nelze nově sdílet.
- Převod pouze ADMIN s reautentizací a ETag. Transakčně se odstraní grant nového vlastníka, nastaví jediný nový vlastník a podle výslovné volby vznikne grant původního vlastníka nebo jeho přístup skončí. Neaktivního vlastníka lze převést na aktivní účet. Systémový ADMIN si vždy zachová globální oprávnění.
- Společný řádkový zámek vozidla pro změny metadat, archivaci, granty i převod. Relevantní účty se zamykají nejprve ve stabilním pořadí. Aktuální session/role se znovu ověří. Změna sdílení zvýší i verzi vozidla, takže starý převod/úprava vrátí 412; chybějící If-Match vrací 428.
- Audit v téže transakci, typ entity a vehicle_id i po odebrání grantu. Heslo převodu se neukládá. Aktualizované generované OpenAPI a bezpečné systémové informace fáze 2.
- Česká UI: karty/detail/formulář, editace, oddělený filtr archivovaných v URL, role/permission badge, všechny technické údaje, desetinná čárka, prázdné/chybové stavy, potvrzení archivace a administrační správa grantů/převodu. Zachovány neutrální barvy i motivy z DB. Opravena dostupnost odhlášení při vyšší desktopové navigaci.

Tankování, přílohy, exporty a výpočty zůstávají plánem fází 3–4; jejich dosud neexistující historie se nevyrábí. Zachování auta a současných údajů při archivaci je testované; návaznost na tankování se ověří po zavedení jeho modelu. Payer-options zatím neexistuje a patří s formulářem tankování do fáze 3.

Uživatel navíc požádal o ilustrační fotografie při budoucím dohledání VIN. Požadavek je zachycený v INTEGRATIONS.md, SPECIFICATION.md a ADR-031 pro fázi 8: ověřená shoda/licence/atribuce, potvrzený výběr a binární obrázek/náhled i původ v PostgreSQL. Fáze 2 nevolá externí VIN API ani nestahuje fotografie.

## Skutečné testy

| Kontrola | Výsledek |
| --- | --- |
| Backend pytest / PostgreSQL 18.6 | **75 prošlo** (36 předchozích + 39 fáze 2), 19,75 s |
| Vitest + Testing Library | **13 prošlo** ve 4 souborech (7 předchozích + 6 fáze 2) |
| Playwright / Chrome | **10 prošlo**, 52,7 s: 5 scénářů v desktopu a mobilu 390×844 |
| TypeScript + Vite production build | Prošlo bez chyb a bez varování o velkém chunku |
| Django check | Bez chyb/varování |
| makemigrations --check --dry-run | No changes detected |
| Migrace | Obě nové migrace úspěšně aplikované na místní tanklog i oddělenou tanklog_e2e; testovací DB vytvoří migrace také od začátku |
| OpenAPI --validate --fail-on-warn | Prošlo, sjednocené jméno enumu grantů, bez potlačení varování |
| Ruff / Prettier | Kontrola kódu a formátování bez zbývajících chyb |
| Compose dev/prod config --quiet + JSON assertions | Obojí prošlo pomocí místního oficiálního Compose 5.6.1 |
| Compose up / production build | **Neověřeno: pokusy selhaly kvůli chybějícímu místnímu Docker daemonu** |
| Vizuální ověření | Prohlédnuté screenshoty detailu/sdílení pro desktop a mobil; screenshoty jsou ignorované syntetické QA artefakty |

Backend pokrývá role, URL/body IDOR, CSRF a omezenou/deaktivovanou session, rozsahy km a technických údajů, VIN (včetně obecné duplicity a prázdných hodnot), ETag vozidla/grantu, archivaci/obnovení, grant vlastníkovi/duplicitě/neaktivnímu účtu, změnu/odebrání a okamžité následné odmítnutí čtení, převod s/bez přístupu starého vlastníka a neplatné heslo. Tři souběžné scénáře ověřují převod vs. sdílení, dvě založení téhož grantu a převod vs. úpravu původním vlastníkem. Kontrolují výsledné vlastnictví, počet grantů/aut a audit.

Frontend testuje prázdná pole, neplatný VIN/normu, desetinnou čárku a null, zachování formuláře po konfliktu a karty obou sdílených rolí. E2E navíc projde vytvoření/úpravu/archivaci/obnovení a trvalost po smazání cookies; druhý scénář používá oddělené browser contexts vlastníka, VIEWER a CONTRIBUTOR, admin sdílení/převod/odebrání a následnou API 404. Regrese účtů/profilu z fáze 1 stále procházejí.

První prohlížečový běh odhalil a vedl k opravě odhlášení mimo viewport při delší navigaci. Následný meziběh zasáhl automatický reload při souběžných úpravách zdrojů; finální běh nad ustálenými zdroji prošel všech 10 scénářů. Nepřidávaly se automatické retry pro zakrytí selhání.

## Přesné příkazy pro spuštění

Z kořene repozitáře s nainstalovaným a běžícím **místním** Dockerem (Compose ≥ 2.24.4):

```sh
python3 infra/setup_env.py
docker compose -f compose.yaml -f compose.dev.yaml config --quiet
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py migrate
# Jen při prvním startu prázdné DB, nepřepisuje existující účty:
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py createsuperuser
```

Otevřít http://localhost:8080. Již existující DB stačí migrovat; nezakládat znovu existujícího správce. Data/volumes se nemažou. Kontejnery lze bezpečně zastavit příkazem `docker compose -f compose.yaml -f compose.dev.yaml stop`. Pro ruční test restart/persistence použít `restart`, nikdy `down -v`.

### Již připravený nativní náhled na tomto Macu

Náhled z předchozího požadavku je ponechaný spuštěný na http://127.0.0.1:8080, backend na 127.0.0.1:8000 a lokální PostgreSQL na 127.0.0.1:55432. Používá oddělenou syntetickou databázi `tanklog_e2e`, nikoli produkční data. Opětovný start **pouze pokud příslušné procesy neběží**:

```sh
cd /Users/mrybicka/Documents/Codex/tankovaci_aplikace
/opt/homebrew/opt/postgresql@18/bin/pg_ctl -D "$PWD/.runtime/postgres" -l "$PWD/.runtime/postgres.log" -o "-h 127.0.0.1 -p 55432 -k $PWD/.runtime" start
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py migrate
# Terminál 1:
POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py runserver 127.0.0.1:8000
# Terminál 2, opět v kořeni:
PATH=/opt/homebrew/opt/node@26/bin:$PATH API_PROXY_TARGET=http://127.0.0.1:8000 HMR_CLIENT_PORT=8080 npm run dev --prefix frontend -- --host 127.0.0.1 --port 8080
```

Cesty výše patří existujícímu izolovanému místnímu clusteru, nejde o univerzální instalátor PostgreSQL. Závislosti už jsou instalované podle locků; čistá instalace vyžaduje Python 3.14, `uv sync --frozen` v backend/ a Node 26 s `npm ci` ve frontend/. Syntetická E2E příprava a testovací přihlašovací údaje jsou v `backend/tests/prepare_e2e.py`; seed se nespouští nad běžnou DB. Přístupové údaje nepatří do produkce.

## Přesné provedené kontroly

Z kořene při běžícím lokálním PostgreSQL:

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

Pytest používá vlastní testovací DB, E2E samostatnou tanklog_e2e a syntetické účty. Nativní úspěch není dokladem běhu Linux image. Nové balíčky ani změny verzí nebyly potřeba, locky se neměnily. E2E se nepouští nad skutečnými uživatelskými daty.

Skutečné neúspěšné Docker pokusy (bez vzdáleného Docker hostu):

```sh
DOCKER_HOST=unix:///var/run/docker.sock .tools/docker-compose --env-file .env -f compose.yaml -f compose.dev.yaml up --build -d
DOCKER_HOST=unix:///var/run/docker.sock NPM_TRUSTED_CIDR=172.30.0.0/24 NPM_NETWORK_NAME=tanklog-verification-only .tools/docker-compose --env-file .env -f compose.yaml -f compose.prod.yaml build backend web
```

Po instalaci Dockeru zopakovat tyto kontroly běžným `docker compose`, migrace a ruční start. Ověřit localhost, healthchecky, HMR a zachování aut/grantů/auditu po restartu; produkční síť NPM ani produkční server se při lokálním buildu nevytvářejí.

## Ruční ověření a změněné soubory

Postup s 9 kroky je v README v sekci „Ruční ověření vozidel a sdílení“. Nejdůležitější je stejná identita auta pro vlastníka i sdílené uživatele, práva obou rolí, převod s explicitním rozhodnutím a následná 404 po odebrání přístupu. Sdílení poskytuje historii bez časového omezení; dříve doručená data nelze zpětně vymazat z jiného zařízení.

Nové části: `backend/apps/vehicles/` (modely, migrace, selektory, služby, API/URL/serializery), `backend/apps/audit/migrations/0002_auditevent_vehicle_id.py`, `backend/tests/test_vehicles.py`, `frontend/src/features/vehicles/` (formulář, sdílení, testy), `frontend/src/pages/Vehicles.tsx`, `frontend/e2e/vehicles.spec.ts`, toto předání. Upravené: registrace backend modulu/URL/schema, audit/system, schema regresní test, React routy/navigace/typy/styly, AGENTS/README a aktuální kontrakty v docs. Přesný seznam poskytne lokální `git show --stat HEAD` po commitu. Žádná provozní data, místní secrets ani testovací screenshoty se neverzují.
