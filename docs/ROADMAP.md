# Roadmapa a akceptační kritéria

Každá fáze má vlastní pokyn k zahájení. Lokální dokončení aplikace a testů předchází GitHubu; GitHub a produkce mají další výslovné schválení. Odhady termínů a kapacity nejsou součást zadání.

Aktuálně uživatel výslovně povolil fázi 1. Její implementaci a přesné výsledky ověření sleduje PHASE_1.md. Dodatek během této fáze ukládá všechna trvalá aplikační data do DB, vyžaduje zachování profilu a motivu po smazání cookies / na dalším zařízení a neutrální modrošedý/bílý vzhled. Funkce dalších etap se nepřidávají.

## Fáze 0 – návrh a dokumentace

Rozsah: prozkoumat adresář, připravit README, AGENTS a konkrétní specifikaci, architekturu, model, API, UX, bezpečnost a etapy. Doplnit přesnou metodiku spotřeby a testovací matici, průzkum VIN a rozhodnutí k odsouhlasení. Inicializovat pouze lokální Git, připravit bezpečný ignore a dokumentační commit.

Akceptace: všechny požadované dokumenty existují a odkazují na sebe; role, model a endpointy si neodporují; výpočet má jednoznačné pořadí, hranice a očekávané výsledky; plán Compose zachovává jeden origin a neveřejnou DB. Skutečné kontroly jsou oddělené od budoucích testů v [VALIDATION.md](VALIDATION.md). Aplikace ani Compose se v této fázi neimplementují. Následuje schválení návrhu a samostatný pokyn k fázi 1.

## Fáze 1 – Docker, základ, autentizace a účty

Rozsah: adresáře frontend/backend/infra, base/dev/prod Compose struktura bez vzdáleného nasazení, Dockerfiles, `.env.example`, `.dockerignore`, uzamčené závislosti, vlastní User a migrace, session/CSRF, profil, změna hesla, správa účtů, jednorázové dočasné heslo, deaktivace, ochrana loginu a minimální audit. Funkční český shell s navigací podle role a stránkami účtů; prázdné budoucí moduly nevydávat za hotové.

Akceptace:

- Lokální čistý start na `http://localhost:8080`; frontend/API jeden origin, HMR pro React a reload Django. Restart kontejnerů zachová DB. Databáze ani backend nemají veřejný port.
- Ruční migrace, vytvoření prvního ADMIN bez hesla v repozitáři; login/logout/profil a správa účtů fungují. Žádná veřejná registrace.
- Reset je jednorázový a expirovatelný, omezená session neotevře doménová data ani ADMIN endpointy. Změna hesla/deaktivace odvolá staré sessions.
- Lokálně sestavit produkční image a zkontrolovat výslednou produkční Compose konfiguraci; bez připojení na produkční síť/server. Budoucí NPM síť ověřit jako konfigurační podmínku, ne vytvářet na vzdáleném serveru.

Testy: backend pytest/pytest-django nad PostgreSQL, skutečné CSRF testy se zapnutým enforcementem (login včetně anonymního), role a poslední ADMIN, expirace/reset/souběžné použití hesla, login limity a rotace sessions. Frontend Vitest + Testing Library pro login a chyby formuláře; Playwright smoke login → profil → logout, povinná změna a zachování profilu/motivu po smazání cookies i z druhého prohlížeče. `docker compose config --quiet`, migrační kontrola, frontend typecheck/build a backend systémové kontroly. Pokud Docker chybí, uvést neověřenou část a přesné příkazy; fáze není plně ověřená jen díky statickému návrhu.

## Fáze 2 – vozidla a sdílení

Rozsah: modely/migrace Vehicle a VehicleAccess, servisní autorizační selektory, CRUD metadat, archivace/obnovení, administrační granty a převody, karty/detail/formulář auta. Manuální VIN bez integrace, technické parametry a norma.

Akceptace: jedno auto má jednoho vlastníka, sdílení nezakládá kopii; USER vidí jen svá/přístupná auta; role jsou vynucené na API; sdílení spravuje jen ADMIN. Převod atomicky nastaví nového vlastníka a explicitní přístup starého. Archivace zachovává historii. Žádný seznam účtů nebo konflikt VIN neprozradí cizí data.

Testy: oprávnění všech rolí, IDOR přes URL/tělo, duplicita grantů, grant vlastníkovi, neaktivní účet, souběh převodu a sdílení, validace VIN/počátečního tachometru a ETag. Frontend klíčové validační chyby a sdílené karty. E2E vytvořit auto → sdílet → přihlásit VIEWER/CONTRIBUTOR → odebrat přístup.

## Fáze 3 – ruční tankování, účtenky, historie, XLSX

Rozsah: přesná Decimal pole a částka, varování/potvrzení, pořadí dne a mezera v evidenci, autor/plátce, idempotentní vytvoření, soukromá JPEG/PNG příloha, přehled/detail/editace/mazání, filtry a typovaný bezpečný export. Audit změn. Ještě bez hotového dashboardu spotřeby.

Akceptace: rychlý mobilní formulář zachová zadanou částku; retry nevytvoří duplicitu. Chybějící tachometr je přijat a označen. CONTRIBUTOR edituje pouze své aktivní záznamy, nesmaže je; OWNER/ADMIN spravují i archivovanou historii. Příloha nemá veřejnou URL, chyba uploadu nezduplikuje tankování. Export přesně odpovídá celému filtru včetně prázdného výsledku a limitu.

Testy: Decimal a zaokrouhlení/slevy, nulová částka s potvrzením, odmítnutí špatné přesnosti, datum v Prague, více tankování za den, ETag/souběh/idempotency. Upload MIME spoofing, velikost/rozměry, poškozený/animovaný obrázek, traversal, zánik přístupu a přímý pokus o stažení. Filtry a stabilní řazení; XLSX otevřít přes openpyxl a ověřit datum/číselné typy, žádné vzorce v textech včetně whitespace prefixů. E2E vytvořit → nahrát → filtrovat → exportovat → opravit/smazat dle role. V této fázi připravit data fixtures pro budoucí spotřebu, nepředstírat její výsledky.

## Fáze 4 – výpočet spotřeby a dashboard

Postup: nejprve přepsat [C01–C34](CONSUMPTION.md) do skutečných jednotkových testů a ověřit, že před implementací chybějí očekávané funkce; následně implementovat čistou servisní vrstvu, API a UI. Doplnit intervalový detail, vysvětlení pokrytí a různé druhy paliv.

Akceptace: všechny testované očekávané výsledky platí; vážený výpočet, plná–plná, chybějící odečty, poklesy, zpětné změny a sdílená auta jsou bez tichých odhadů. Nákupní součty a spotřeba používají správná období. Výchozí měsíc, pondělní týdny, vlastní rozsah a přechod období fungují. Grafy mají jednotky a srozumitelně chybějící data. Normu nelze dělit nulou.

Testy: čisté výpočty s Decimal, API agregace nad PostgreSQL, přestupný den/rok a změny letního času, souběžné čtení a zápis, zpětné vložení/úprava/smazání, nepřístupné intervaly a žádná duplikace přes granty. Frontend období, stavy null a detail podkladů; E2E syntetický scénář 50 l kotva → 20 l částečně → 25 l koncová plná / 600 km = 7,50.

## Fáze 5 – responzivita, UX, PWA základ, bezpečnost

Rozsah: dokončení motivů, interakcí, prázdných/chybových stavů, dotykového ovládání a přístupnosti, manifest/ikony a opatrný service worker pouze pro veřejný app shell. Bez offline ukládání soukromých API dat a bez offline tankování. Bezpečnost se kontroluje průběžně, neodkládá až sem.

Akceptace: šířky 360/390/768/1024/1440 px, klávesnice, focus, dialogy, kontrasty, zoom 200 %, tabulková alternativa grafů a motiv dle systému. Naměřený standardní mobilní průchod 15–30 sekund nebo zdokumentovaná odchylka a oprava. Logout/odebrání práv nezanechá soukromá data v cache. Produkční build funguje lokálně, přímé frontendové cesty mají správný fallback a API chyby zůstanou JSON.

Testy: frontend typecheck/lint/build, vybrané komponentové testy, Playwright klíčové toky v mobilním i desktop viewportu, automatizovaná přístupnost doplněná ruční klávesnicí/čtečkou. Kompletní bezpečnostní negativní scénáře z SECURITY, test hlaviček a cookies v lokálním produkčním testovacím prostředí, `check --deploy`, revize závislostí a tajných údajů. Výsledek představuje lokálně ověřené MVP, ne oprávnění publikovat.

## Fáze 6 – soukromý GitHub a CI

Zahájení jen po výslovném souhlasu s GitHubem. Rozsah: soukromý repozitář, první autorizovaný push, CI frontend/backend/PostgreSQL, kontrola migrací, build a vybrané E2E podle možností CI. Žádná automatická produkční deploy pipeline bez dalšího souhlasu.

Akceptace: repozitář je skutečně private, historie neobsahuje secrets/data/účtenky, lock soubory reprodukují instalaci, CI na čistém runneru prochází. Kontrola oprávnění workflow a případných secrets; žádné sdílené produkční credentials. Provedené CI běhy doložit odkazem a skutečným stavem, připravený YAML není úspěšný běh.

## Fáze 7 – produkční Docker, NPM, HTTPS a zálohy

Zahájení jen po výslovném souhlasu s konkrétním nasazením. Nejprve zjistit skutečný server, architekturu, doménu, existující NPM síť a úložiště; nic nededukovat z lokální IP. Připravit konkrétní konfiguraci a ověřit ji před zásahem. Migrace/zálohy mají řízený postup.

Akceptace: HTTPS a platný certifikát, sanitizace proxy hlaviček, přesné hosty/originy, secure cookies, DEBUG=False, DB neveřejná a persistence po restartu. Žádný přístup na privátní soubory bez session. Automatická šifrovaná záloha DB+účtenek mimo hostitele a úspěšná obnova do nových izolovaných volumes s kontrolními součty. Zapsané měřené RPO/RTO, retence, vlastník provozu a rollback postup. Bez zkušební obnovy fáze není dokončená.

Testy: `check --deploy` nad skutečnou produkční konfigurací, smoke přes veřejný origin, CSRF a session přes NPM, podvržené hlavičky, síťové porty, autorizované účtenky, restart a restore. Produkční data ani existující volumes se v testu nemažou.

## Fáze 8 – samostatně schvalovaná rozšíření

VIN adaptér: znovu ověřit oficiální API, limity a podmínky, pouze backendový klíč, preview/ruční potvrzení a raw provenance. OCR: lokální engine s limity, návrhy a jistotou, vždy potvrzení, zachovat originál. Viz [INTEGRATIONS.md](INTEGRATIONS.md).

Servis/STK/pojištění/připomínky/import/offline a nová paliva/jednotky jsou další samostatné podetapy s vlastní specifikací, migracemi, právy a akceptací. Nezačínají automaticky dokončením nasazení. Integrace testovat proti kontrolovaným fixture odpovědím i skutečnému autorizovanému zdroji, jasně odlišit obě úrovně.

## Společné podmínky předání každé implementační fáze

1. Dokončit schválený rozsah; vypsat případné nedokončené body, nezakrýt je označením „hotovo“.
2. Spustit přiměřené skutečné testy a opravit chyby v rozsahu etapy. Rozlišit prošlo / selhalo / nespouštěno s důvodem.
3. Aktualizovat README, relevantní kontrakty, rozhodnutí a záznam ověření. U modelů přidat a zkontrolovat migrace.
4. Zkontrolovat diff, soukromá data a secrets, provést lokální Git commit s výstižným popisem; žádný automatický push.
5. Uvést změněné soubory, přesné provedené příkazy/výsledky, kroky pro ruční test a omezení. Po etapě se zastavit a čekat na další pokyn.

Výkonové limity konkrétního serveru se měří na syntetických datech; nepřidávat cache, frontu nebo indexy jen kvůli předpokladu. Při chybě nástroje či chybějícím Dockeru se výsledek nezaměňuje za úspěšné běhové ověření.
