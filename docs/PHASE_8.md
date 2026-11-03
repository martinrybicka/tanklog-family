# Fáze 8 – implementace a předání

Stav 3. 11. 2026. Uživatel výslovně schválil všechna rozšíření a návrh chybějící specifikace. Rozsah určuje [PHASE_8_SPECIFICATION.md](PHASE_8_SPECIFICATION.md). Implementace je lokální; žádný GitHub push, vzdálený CI běh, nasazení ani zásah do produkce neproběhl. Chybějící Docker a živé RSV ověření jsou otevřené akceptační body, nikoli úspěšné testy. Další etapa není zahájena.

## Implementované funkce

- VIN: backendový RSV adaptér, ruční fallback, uložené návrhy a raw provenance, výběr jednotlivých polí a potvrzení při uložení auta. Nejednoznačný výkon/spotřeba nebo první registrace se nevydávají za spolehlivý číselný parametr/rok výroby. Platnost 24 h, klouzavé DB kvóty, opětovná autorizace po externím volání.
- Ilustrační fotografie modelu: Commons kandidáti až po výslovném přijetí značky/modelu z VIN, kontrola hostů/obsahu/velikosti/licence, potvrzení shody, atribuce a odkazy. Originál, náhled a původ v PostgreSQL; čtení přes neveřejné API. Změněná identita auta zneplatní fotografii.
- Lokální OCR uložené účtenky: Tesseract 5.5.4, zamčené české/anglické modely, návrhy šesti polí s jistotou, výběr a standardní potvrzení formulářem. Původní účtenka se nemění. Nová verze/hash přílohy zablokuje starý výsledek; omezený podproces a dva souběžné sloty.
- Události SERVICE/INSPECTION/INSURANCE/REMINDER/ENERGY: servisní historie, platnost STK a pojištění, termíny podle data/km, částky a poznámky. Přístupové role, archivace, ETag, idempotence, audit a revize historie. Termíny se zobrazují jen v aplikaci a respektují přístup k autům.
- CNG a elektřina: nákupy v kg/kWh se samostatnými Decimal součty. Primární CNG/ELECTRIC nepřijímají nové litrové tankování a nemají litrovou normu/plná–plná. Existující kapalná historie a metodika zůstávají zachované.
- CSV import tankování i událostí/energie: UTF-8, 128 KiB/200 řádků, šablony, uložený soukromý náhled, chyby/varování, 24 h a revize historie. Potvrzení celé dávky nebo rollback; opakované potvrzení neduplikuje zápisy. Nová varování uvnitř dávky mají číslo řádku a lze je znovu potvrdit.
- Výslovná offline fronta nových tankování: nejvýše 20 neuložených položek v paměti okna, oprava/zahození/ruční synchronizace a původní idempotency UUID. Logout/změna účtu/reload frontu zruší, zavření upozorní. Žádná soukromá data v persistentním úložišti prohlížeče. Běžné Uložit zachovává původní retry formuláře.
- UI v neutrální modré/šedé/bílé, mobilní navigace, popisky, dostupný posuvný náhled importu, podtržené textové odkazy. Nové modely/přílohy/návrhy pokrývá existující šifrovaná záloha celé DB.

## Skutečné výsledky kontrol

| Kontrola | Výsledek |
| --- | --- |
| Backend, PostgreSQL | **226 prošlo / 46,73 s**, včetně původních C01–C34 a negativních rolí/IDOR/CSRF/ETag; 34 nových testů rozšíření. |
| Frontend Vitest | **30 prošlo**; lint, TypeScript/Vite/PWA build a Prettier prošly. |
| Pravidla CI a provozu | **11 + 10 prošlo**, Ruff backend/infra, frozen lock, actionlint a politika workflow prošly. |
| HTTP Playwright desktop/mobil | **24 prošlo / 3,6 min** v jednom závěrečném běhu, včetně obou nových scénářů, axe kontrol servisního přehledu/importu a původních regresí. |
| Produkční build na místním HTTPS nginx/Gunicorn | **6 prošlo / 13,4 s**: cookies/CSRF, proxy a JSON chyby, veřejná PWA cache, offline a jediný zápis při retry. Pouze syntetická DB, místní samopodepsaný certifikát; není to vzdálené nasazení. |
| OCR skutečný engine | PSM 6 i 11: **6/6 očekávaných polí** vlastní syntetické české účtenky. Opravená záměna l/I má sníženou jistotu 50. Nejde o garantovanou přesnost na reálných účtenkách. |
| Migrace/check/OpenAPI | Nové migrace skutečně aplikovány v izolované CI/E2E i prázdné běžné lokální DB; Django check bez problémů, makemigrations bez změn, generované OpenAPI shodné a bez varování. |
| `check --deploy` | Pouze známé **security.W004**: HSTS=0 podle ADR-027 do ověřeného konkrétního HTTPS nasazení. Varování není umlčené. |
| Compose konfigurace | Dev/prod/CI/operations/restore prošly: syntaxe, sítě, porty, svazky a build targety. |
| Skutečný Docker start/build | **Nelze spustit:** `/var/run/docker.sock` neexistuje, Docker daemon není instalovaný. Pokus o dev up i prod build skončil chybou připojení. Linux OCR image/limity, restart a persistence kontejnerů nejsou ověřené. |
| Šifrovaná záloha a obnova rozšířené DB | **27 tabulek** v novém fyzickém PostgreSQL clusteru, hashe včetně bytea/JSON, neprivilegovaná aplikační role, API a přístupy, konzistentní snapshot při souběžném zápisu. Chybný klíč, poškozený ciphertext a existující cíl odmítnuty. |
| Malé syntetické restore cvičení | Záloha 0,118 s; restore/hash 0,151 s; nový cluster + restore + kontroly aplikace **2,197 s**; stáří snapshotu 0,965 s. Není to produkční RPO/RTO ani off-host test. |
| Živé externí zdroje | Ověřena oficiální dokumentace/verze/hash a veřejný Commons metadata endpoint. **Úplný živý VIN/foto průchod neověřený:** chybí RSV_API_KEY a reálný kontaktní COMMONS_USER_AGENT. VIN/foto v E2E jsou syntetické fixtures; OCR je skutečné. |

Během implementace testy zachytily nedostupný lazy chunk offline obrazovky, nerozlišené textové odkazy, chybějící revizi servisní historie a neúplné potvrzování nových varování v dávce. Opraveno a související testy opakovány. Dřívější selhání kvůli opakovanému použití změněných fixtures a restartu vývojového serveru nejsou označena za úspěch; finální ověření používá nové fixtures a stabilní zdrojové soubory.

## Přesné lokální spuštění

Z kořene projektu. Docker cesta vyžaduje skutečně běžící místní Engine/Desktop; zde zatím chybí:

```sh
cd /Users/mrybicka/Documents/Codex/tankovaci_aplikace
python3 infra/setup_env.py
docker compose -f compose.yaml -f compose.dev.yaml config --quiet
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py migrate
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py createsuperuser
```

Otevřete **http://localhost:8080**. Existující `.env` se nepřepíše; vlastní ADMIN vznikne interaktivním příkazem, bez výchozího produkčního hesla. Po aktualizaci existující instalace nejprve záloha podle OPERATIONS.md a pak migrace. Nepoužívejte `down -v`. DB nemá veřejný port.

VIN/foto jsou volitelné: do místního `.env` nastavte vlastní `RSV_API_KEY` a `COMMONS_USER_AGENT` s identifikací instalace a reálným kontaktem. Poté obnovte backend kvůli změně prostředí:

```sh
docker compose -f compose.yaml -f compose.dev.yaml up -d --force-recreate backend
```

Klíč nepřidávejte do Gitu, frontendu, URL prohlížeče ani logů. OCR engine/modely obsahuje backend image; `BACKEND_TMPFS_SIZE` má výchozí hodnotu 268435456 bajtů pro dočasný pracovní prostor, podle skutečného zatížení jej lze upravit.

Nativní alternativa pro již připravený lokální PostgreSQL cluster na tomto Macu (port 55432, bez spuštění systémové služby):

```sh
# Použijte Node 26.13.0 a Python 3.14 / uv 0.13.6.
export PATH="$PWD/.tools/node-ci/node-v26.13.0-darwin-arm64/bin:$PATH"
.tools/python/bin/uv sync --frozen --project backend
npm ci --prefix frontend
python3 infra/setup_env.py
# Pro OCR musí být nainstalovaný Tesseract přesně 5.5.4.
tesseract --version
python3 infra/ocr/install_models.py
# Je-li zdejší cluster zastavený (nespouštějte druhý na stejném portu):
/opt/homebrew/opt/postgresql@18/bin/pg_ctl -D "$PWD/.runtime/postgres" status
# /opt/homebrew/opt/postgresql@18/bin/pg_ctl -D "$PWD/.runtime/postgres" -l "$PWD/.runtime/postgres.log" start
POSTGRES_DB=tanklog POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py migrate
POSTGRES_DB=tanklog POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py createsuperuser
# Terminál 1 (nejprve zastavte dřívější vlastní backend na 8000):
POSTGRES_DB=tanklog POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py runserver 127.0.0.1:8000
# Terminál 2 (nejprve zastavte dřívější vlastní Vite na 8080):
export PATH="$PWD/.tools/node-ci/node-v26.13.0-darwin-arm64/bin:$PATH"
npm run dev --prefix frontend -- --host 127.0.0.1 --port 8080
```

Jde o příkazy pro tento připravený Mac, nikoli univerzální instalátor PostgreSQL. Na konci ověření ponechaný HTTP náhled na 8080 používá **výhradně syntetickou tanklog_e2e DB**; běžná tanklog DB je oddělená, má nové migrace a zatím žádný účet. Pro vlastní evidenci použijte běžnou DB a vlastní interaktivně vytvořený účet. Přepnutí není mazání testovacích dat.

## Opakování automatických kontrol

```sh
export PATH="$PWD/.tools/node-ci/node-v26.13.0-darwin-arm64/bin:$PATH"
TANKLOG_CI=1 POSTGRES_DB=tanklog_phase6_ci POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 UV_COMMAND="$PWD/.tools/python/bin/uv" python3 infra/ci/run_checks.py backend
python3 infra/ci/run_checks.py frontend
COMPOSE_COMMAND=.tools/docker-compose python3 infra/verify_compose.py
backend/.venv/bin/python infra/ci/verify_workflow.py
actionlint
# Skutečný lokální OCR benchmark:
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python ../infra/ocr/benchmark.py
```

HTTP E2E vyžaduje běžící backend nad explicitní `tanklog_e2e` DB a Vite 8080; tuto DB nikdy nenahrazujte běžnou/prod DB. Příprava zakládá pouze nové syntetické objekty, nic nemaže:

```sh
TANKLOG_E2E=1 POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python tests/prepare_e2e.py
TANKLOG_E2E=1 POSTGRES_DB=tanklog_e2e POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python tests/prepare_extensions_e2e.py > .runtime/phase8-extensions-e2e.json
chmod 600 .runtime/phase8-extensions-e2e.json
E2E_EXTENSIONS_FIXTURE="$PWD/.runtime/phase8-extensions-e2e.json" E2E_BROWSER_CHANNEL=chromium E2E_BASE_URL=http://127.0.0.1:8080 npm run test:e2e --prefix frontend -- --grep-invert 'produkční nginx:|PWA:'
```

Ochranný fixture skript vyžaduje TANKLOG_E2E=1 a název DB končící `_e2e`. Před opakováním vytvořte nové fixtures. Bez E2E_EXTENSIONS_FIXTURE se nové testy přeskočí. HTTPS postup je shodný s PHASE_5.md (Gunicorn 8001 + `infra/local_production_preview.py` a grep `'produkční nginx:|PWA:'`), vždy nad syntetickou DB. Dočasné HTTPS procesy byly po testu zastaveny.

Restore cvičení: `TANKLOG_DRILL=1 POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python ../infra/ops/drill.py`. Vyžaduje místní PostgreSQL 18 binárky/age na PATH. Založí nové náhodně pojmenované zdrojové/restore DB a druhý cluster; žádný existující cíl nemaže. Artefakty v ignorovaném `.runtime/phase7-drill-*` zůstávají privátní, název pomocníka historicky pochází z fáze 7. Testovací klíč nelze používat pro skutečné zálohy.

## Ruční ověření

1. Přihlaste vlastní ADMIN do běžné lokální DB, vytvořte auto; bez klíče stiskněte Dohledat VIN a ověřte srozumitelný fallback bez ztráty formuláře. S vlastním klíčem a oprávněným VIN vyberte pouze některá navržená pole, zkontrolujte nejednoznačný výkon/spotřebu a uložte. Návrh načtěte i po novém přihlášení.
2. Po výslovném přijetí značky/modelu vyhledejte fotografii. Ověřte generaci/karoserii, autora, licenci a zdroj, potvrďte a vyberte. Karta/detail ukazují ilustrační označení. Změna VIN/modelu fotografii zneplatní. Bez shody ponechte ikonu; odeberte fotografii. Cizí přímá URL musí vrátit 404.
3. Na uloženém tankování nahrajte vlastní testovací JPEG/PNG účtenku, spusťte OCR, vyberte jen zkontrolovaná pole a uložte běžným formulářem. Originál zůstane stejný. Nahraďte účtenku: starý OCR návrh má být neaktuální a odmítnutý při uložení.
4. V detailu auta otevřete Servis a energie. Přidejte servis s částkou a termínem/km, STK a pojištění s platností. Ověřte Připomínky, předstih a uzavření. VIEWER pouze čte; CONTRIBUTOR upravuje vlastní aktivní zápisy, ale nemaže je. Archivované auto se nepřipomíná, OWNER/ADMIN jeho historii dál spravují.
5. Vytvořte CNG/elektrické auto, přidejte ENERGY s 3,001 kg nebo 12,345 kWh a přesnou částkou. Součty mají vlastní jednotky a české desetinné zobrazení, litrové tankování/norma se nenabízejí. U hybridu lze energii evidovat doplňkově, bez převodu na litry.
6. Otevřete Import historie, použijte přímo zobrazenou šablonu UTF-8. Zkontrolujte všechny řádky; chyba nesmí nic zapsat. Opravte CSV, potvrďte upozornění a dávku. Nově zjištěná upozornění se ukážou s řádkem a vyžadují nové potvrzení. Opakujte potvrzení a ověřte stejná ID/počet. Změna historie po náhledu vyžaduje nový náhled, ne tichý import.
7. Načtěte nový formulář tankování, odpojte síť a výslovně zvolte Zařadit do dočasné offline fronty. Zkontrolujte označení neuloženo, opravte částku nebo položku zahoďte. Připojte síť a ručně synchronizujte; varování/práva platí i tady a retry nesmí vytvořit duplicitu. Logout/reload frontu zruší, uložené serverové záznamy zachová. Offline přílohy nejsou podporované.
8. Smažte cookies/přihlaste se z druhého zařízení: uložené profily, auta, fotky, události, potvrzené importy a OCR podklady se načtou z DB. Odebrání grantu odebere i přístup k návrhům/přílohám. Zopakujte ve světlém/tmavém motivu na mobilu a klávesnicí.
9. Po instalaci Dockeru proveďte build/start/migrace/restart bez mazání volumes a znovu ověřte data a skutečné OCR uvnitř kontejneru. Tento krok zde čeká na daemon.

## Omezení a otevřené body

- Úplná integrační/provozní akceptace čeká na autorizovaný živý RSV test, skutečný kontaktní Commons User-Agent a běžící Docker. API klíč ani kontakt nebyly vymyšleny. Fotografie modelu negarantuje přesnou generaci/barvu/výbavu.
- OCR rozpoznává omezený soubor českých štítků a šest polí; reálné nekvalitní účtenky mohou vyžadovat ruční zadání. Jistota není kalibrovaná pravděpodobnost správnosti. CPU/memory limity nejsou OS sandbox; linuxová image/resource limity nejsou skutečně spuštěné.
- Připomínky pouze uvnitř aplikace, bez e-mailu/push/SMS; platnost STK/pojištění uživatel zadává a kontroluje sám. U odečtů ve stejném dni mají přednost poslední pořadím určené tankování před servisní událostí; nedochází k odhadu nájezdu.
- Energie má přesné nákupní množství a výdaje, bez metodiky kg/kWh na 100 km a bez míchání s litrovou analytikou. Servisní PDF/přílohy, offline účtenky a obecný cizí XLSX/PDF import nejsou v konkrétní specifikaci této fáze.
- Offline fronta se po reloadu/zavření ztratí; garantovanou databází je server. Bez dříve načteného veřejného shellu aplikaci poprvé offline neotevřete. Žádná automatická synchronizace na pozadí.
- Expirace návrhů omezuje použití, není automatickým mazáním. Retence uložených návrhů/kvót zatím nemá automatický cleanup; velikost DB a záloh je nutné sledovat podle provozu.
- Automatizovaný audit a prohlédnuté screenshoty nenahrazují uživatelské měření, poslech čtečky ani test skutečných mobilních zařízení. HSTS a produkční/off-host akceptace fází 6–7 zůstávají otevřené.

## Změněné části

Nový backendový modul `apps/extensions`, jeho dvě migrace a testy/fixtures; migrace a doplnění vehicles/refuelings/analytics/settings/URL. Frontendové návrhy VIN/OCR, soukromé fotografie, události/import/připomínky/offline a testy. OCR lock/instalační/benchmark nástroje, backend Dockerfile a tmpfs Compose konfigurace, doplnění CI a restore fixture. Aktualizované AGENTS, README, API/OpenAPI, model, architektura, bezpečnost, UI, integrace, roadmapa a ADR-052–060. Přesný seznam zachycuje lokální `git show --stat HEAD`; testovací data, modelové binárky, secrets, logy a screenshoty jsou pouze v ignorovaných adresářích.
