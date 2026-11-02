# TankLog

Česká self-hosted aplikace pro vozidla, tankování, výdaje a spotřebu, postupně vyvíjená po schválených etapách.

## Aktuální stav

**Implementována fáze 3 – tankování, účtenky, historie a XLSX (2. 11. 2026).** Přesné částky s Decimal, potvrzovaná varování, pořadí dne, mezery v evidenci, autor/plátce, ochrana opakovaného vytvoření, soukromé JPEG/PNG v PostgreSQL, responzivní historie s filtry a typovaný export celého výběru. Navazuje na účty, vozidla, sdílení a převody z fází 1–2. Jeden origin a API pod `/api/v1/`.

Podle doplňujícího požadavku jsou **všechna uložená aplikační data v PostgreSQL**. Cookie pouze identifikuje přihlášení; smazání cookies vás odhlásí, ale po přihlášení zůstane profil i nastavení stejné na všech zařízeních. Osobní data ani motiv nejsou v localStorage/IndexedDB. Originály i očištěné náhledy účtenek jsou v DB jako binární obsah. Citlivá konfigurace je v proměnných prostředí. Vzhled je neutrální modrý/šedý/bílý.

Spotřeba, analytický dashboard a OCR se zatím neimplementují. VIN lze zadat ručně; automatické dohledání a požadované ilustrační fotografie modelu patří do fáze 8 podle [návrhu integrací](docs/INTEGRATIONS.md). Fáze 4 čeká na samostatný pokyn.

**Ověření:** backend a prohlížečové testy běžely lokálně proti skutečnému PostgreSQL. Obě konfigurace Compose byly strojově zkontrolované. Docker daemon zde chybí; kontejnery, jejich restart/persistence a produkční Docker build nebylo možné spustit. Aktuálně prošlo 127 backendových, 17 frontendových a 14 E2E testů. Podrobnosti a omezení jsou v [předání fáze 3](docs/PHASE_3.md), historicky také v [předání fáze 1](docs/PHASE_1.md).

## Lokální spuštění přes Docker

Předpoklady: běžící Docker Engine nebo Docker Desktop, plugin Compose alespoň 2.24.4 (používá se `!reset`) a Python 3 pro bezpečné vygenerování `.env`. Node/Python pro samotnou aplikaci jsou v image. Příkazy spouštějte z kořene repozitáře:

```sh
python3 infra/setup_env.py
docker compose -f compose.yaml -f compose.dev.yaml config --quiet
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py migrate
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py createsuperuser
```

Otevřete **http://localhost:8080**. `createsuperuser` automaticky nastaví systémovou roli ADMIN; zvolte vlastní jméno a silné heslo. Žádný výchozí účet/heslo neexistuje. Skript `setup_env.py` generuje náhodné lokální secrets, nastaví práva 600 a existující `.env` nikdy nepřepíše. Změny prostředí řešte úpravou místního `.env`, ne souboru v Gitu.

Web publikuje pouze `127.0.0.1:8080`, PostgreSQL ani Django nemají host port. Frontend a API jsou na stejném originu. React používá HMR přes webovou proxy, Django automatický reload. Při změně JS závislostí/locku obnovte obsah vývojového modulu příkazem `docker compose -f compose.yaml -f compose.dev.yaml exec frontend npm ci` a případně rebuildem.

Další bezpečné provozní příkazy:

```sh
docker compose -f compose.yaml -f compose.dev.yaml ps
docker compose -f compose.yaml -f compose.dev.yaml logs --tail=100 backend web frontend
docker compose -f compose.yaml -f compose.dev.yaml restart
# Zastavení zachovávající databázový svazek:
docker compose -f compose.yaml -f compose.dev.yaml stop
```

Nespouštějte `down -v` ani žádné mazání volumes. Data jsou v pojmenovaném svazku `tanklog-dev_postgres_data`; restart kontejneru je neodstraňuje. Vývoj a budoucí produkce mají různá jména projektu/svazků. Samotný svazek není záloha.

## Testování

Po spuštění vývojového prostředí:

```sh
docker compose -f compose.yaml -f compose.dev.yaml exec backend pytest
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py check
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py makemigrations --check --dry-run
docker compose -f compose.yaml -f compose.dev.yaml exec frontend npm run test
docker compose -f compose.yaml -f compose.dev.yaml exec frontend npm run build
python3 infra/verify_compose.py
```

Pytest explicitně používá testovací settings a vlastní databázi `test_tanklog`, nikoli běžná data. Pro Playwright je nutný testovací účet a **samostatná E2E databáze**; přesný izolovaný postup i příkazy pro nativní ověření jsou v [PHASE_1.md](docs/PHASE_1.md). Nevytvářejte syntetické účty v produkční DB.

## Ruční ověření

1. Přihlaste se prvním ADMIN. Přehled ukazuje stav fáze 3 a odkazy na skutečně dostupné funkce.
2. V Nastavení změňte zobrazované jméno, kontakt a motiv. Uložte, obnovte stránku a ověřte zachování údajů.
3. Smažte cookies pro localhost; po novém přihlášení zůstanou stejné údaje i motiv. Totéž ověřte v anonymním okně nebo druhém prohlížeči.
4. V administraci vytvořte USER. Vlastní heslo správce potvrzuje operaci; jednorázové heslo si přečtěte před zavřením dialogu a předejte soukromě.
5. V druhém okně se přihlaste novým účtem, nastavte nové heslo. Před změnou se nelze dostat do profilu ani administrace; původní dočasné heslo už podruhé nefunguje.
6. ADMIN účet USER deaktivuje, ověří odhlášení jeho session, znovu aktivuje a případně vydá nový reset. Změnu vlastního hesla provádí každý přes Nastavení; ADMIN nemůže tímto dialogem resetovat sám sebe.
7. Projděte audit, filtry účtů a systémové informace. Běžný USER administrační API nepoužije ani přímou URL.
8. Restartujte kontejnery a zkontrolujte zachování účtů, profilu a auditu. Tento konkrétní krok je zde kvůli chybějícímu Docker daemonu zatím neověřený.

## Ruční ověření vozidel a sdílení (fáze 2)

1. Jako USER otevřete Moje auta → Přidat auto. Vyplňte název/značku/model/palivo/počáteční tachometr, případně ruční VIN a normu (např. 5,125 s metodikou WLTP).
2. Ověřte detail, upravte RZ a normu. Smažte cookies a přihlaste se znovu nebo z dalšího zařízení: auto i uložené údaje zůstávají.
3. Archivujte auto, přepněte seznam na Archivovaná a auto obnovte. Data se neodstraňují.
4. Jako ADMIN otevřete Vozidla a sdílení → detail téhož auta. Přidejte aktivního uživatele jako Čtenář a jiného jako Přispěvatel. Hledání i stránkování výběru účtů jsou dostupné pouze ADMIN.
5. V oddělených prohlížečích ověřte sdílenou kartu a správnou roli. VIEWER ani CONTRIBUTOR nemohou měnit metadata/archivovat/sdílet; CONTRIBUTOR může přidávat a upravovat vlastní aktivní tankování, VIEWER pouze čte.
6. ADMIN převede vlastnictví s potvrzením vlastního hesla. Výslovně zvolí odebrání přístupu starému vlastníkovi nebo nový grant; nový vlastník už nemá samostatný grant. Systémový ADMIN má vždy globální přístup.
7. ADMIN odebere grant. Při novém načtení už daný USER nevidí kartu ani detail (API vrátí 404); dříve doručená data nelze zpětně odvolat.
8. Ve dvou oknech otevřete editaci. Po uložení v prvním druhé oznámí konflikt a nabídne nové načtení. Stejně je chráněný rozpracovaný převod po změně sdílení.
9. Zkontrolujte audit vytvoření/úprav/archivace/grantů/převodu. Po restartu Dockeru mají údaje zůstat; tento kontejnerový krok zde není ověřený.

## Ruční ověření tankování a účtenek (fáze 3)

1. Z karty/detailu aktivního auta zvolte Zadat tankování. Dnešní datum je podle Prahy, plná nádrž je výchozí ne. Zadejte například 12,345 l, cenu 38,90 a přesnou částku 480,00 Kč: částka zůstane 480,00, návrh je 480,22.
2. Nechte tachometr prázdný, potvrďte upozornění. Ověřte autora, skutečnou částku, zdroj částky a upozornění v detailu. Zkuste nulu jen s výslovnou nulovou částkou; neplatná přesnost nebo budoucí datum se neuloží.
3. V detailu nahrajte syntetickou JPEG/PNG účtenku. Zkuste nejprve vadný soubor: tankování zůstane existovat, lze nahrát správný obrázek k témuž záznamu. Prohlédněte náhled, stáhněte originál, případně nahraďte/smažte jen účtenku.
4. V historii filtrujte auto, datumy, palivo, stanici a hledání. Exportujte XLSX; obsahuje všechny vyfiltrované řádky, ne jen stránku. Prázdný výběr vrátí sešit se záhlavím, nad 50 000 řádků API vyžádá užší filtr.
5. Vložte další záznam ve stejném dni, potvrďte/změňte pozici. OWNER/ADMIN může na detailu uložit celé pořadí dne. Stará editace po přesunu vrátí konflikt místo přepsání změn.
6. Jako CONTRIBUTOR ověřte úpravu a účtenku vlastního aktivního tankování; cizí neupraví a vlastní nesmaže. VIEWER jen čte. Po archivaci opravuje historii jen OWNER/ADMIN; nové tankování není povolené nikomu.
7. Jako ADMIN odeberte sdílení. Uživatel po novém načtení neotevře historii ani přímý receipt endpoint, i pokud dané tankování sám vytvořil. Autor/plátce nejsou přístupová oprávnění.
8. OWNER/ADMIN může se jmenovitým potvrzením smazat tankování i jeho přílohu; audit zůstane. Smažte cookies, přihlaste se na dalším zařízení a ověřte ostatní uložené údaje. Po instalaci Dockeru zopakujte také restart kontejnerů bez mazání volumes.

## Nativní náhled na tomto Macu

Docker zde není dostupný, ale již připravený místní náhled běží na `http://127.0.0.1:8080` s oddělenou syntetickou databází `tanklog_e2e`. Není to produkční instalace. Přesné příkazy pro opakované spuštění tohoto existujícího prostředí, testy a ruční Docker akceptaci jsou v [PHASE_3.md](docs/PHASE_3.md). Testovací účet je definovaný pouze v chráněné E2E přípravě; do běžné DB se žádné výchozí heslo nezavádí.

## Produkční varianta

`compose.prod.yaml` používá sestavený frontend, nginx a Gunicorn bez veřejných host portů; web se později připojí k existující síti NPM. Vyžaduje skutečnou HTTPS doménu, přesné hosty/originy a `NPM_TRUSTED_CIDR`. Image jsou připnuté na tag i digest; dependencies jsou zamknuté. Produkční HSTS zůstává do ověření HTTPS domény na 0 (zdokumentované varování `security.W004`). Produkční start ani vzdálené nasazení zatím nejsou povoleny.

## Dokumentace

| Dokument | Obsah |
| --- | --- |
| [Předání fáze 3](docs/PHASE_3.md) | Tankování/účtenky/XLSX, aktuální ověření a přesné příkazy |
| [Předání fáze 2](docs/PHASE_2.md) | Vozidla, sdílení, aktuální testy a omezení |
| [Předání fáze 1](docs/PHASE_1.md) | Funkce, skutečné testy, přesné ověření a omezení |
| [Specifikace](docs/SPECIFICATION.md) | Pravidla a hranice MVP |
| [Architektura](docs/ARCHITECTURE.md) | Moduly, Docker, síť a proměnné |
| [Datový model](docs/DATA_MODEL.md) | Implementované účty i návrh dalších entit |
| [API](docs/API.md), [OpenAPI](docs/openapi.yaml) | Kontrakt endpointů; OpenAPI generuje aktuální implementace fází 1–3 |
| [UI a UX](docs/UI_UX.md) | Navigace a neutrální designový systém |
| [Výpočty](docs/CONSUMPTION.md) | Budoucí algoritmus a 34 testovacích specifikací pro fázi 4 |
| [Bezpečnost](docs/SECURITY.md) | Práva, ochrany a budoucí obnova |
| [Roadmapa](docs/ROADMAP.md), [Rozhodnutí](docs/DECISIONS.md) | Etapy, akceptace a změny návrhu |
| [Integrace](docs/INTEGRATIONS.md) | Budoucí VIN/OCR |
| [Ověření fáze 0](docs/VALIDATION.md) | Historický záznam návrhové etapy |
| [AGENTS.md](AGENTS.md) | Trvalá pravidla práce |

Do Gitu nepatří `.env`, hesla, databáze, zálohy ani skutečné účtenky. Bez výslovného souhlasu se nepushuje, nenasazuje, nemaže databáze/volumes ani neprovádějí nucené Git operace.
