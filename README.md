# TankLog

Česká self-hosted aplikace pro vozidla, tankování, výdaje a spotřebu, postupně vyvíjená po schválených etapách.

## Aktuální stav

**Připravena lokální část fáze 6 – CI a audit repozitáře (3. 11. 2026).** Čtyři kontrolní úlohy pro historii/bezpečnost, backend s PostgreSQL, frontend a izolovaný Docker/E2E. Instalace z locků a testy byly ověřené v čistém exportu na tomto Macu. GitHub repozitář, push ani skutečný CI běh nebyly podle výslovného zákazu provedené. Celá fáze 6 proto ještě nesplňuje vzdálená akceptační kritéria. Přesné výsledky: [PHASE_6.md](docs/PHASE_6.md), opakování kontrol: [CI.md](docs/CI.md).

**Implementována fáze 5 – responzivita, UX, přístupnost, PWA základ a bezpečnost (2. 11. 2026).** Instalovatelný veřejný shell, obecná offline stránka bez soukromých dat, potvrzované aktualizace, motiv podle zařízení i DB profilu, focus a popisky formulářů, tablet/mobil a odhlášení více oken. Navazuje na účty, vozidla, sdílení, tankování, soukromé účtenky, XLSX a analytiku fází 1–4. Akceptační ověření má níže uvedená omezení; nejde o schválení produkčního provozu.

Podle doplňujícího požadavku jsou **všechna uložená aplikační data v PostgreSQL**. Cookie pouze identifikuje přihlášení; smazání cookies vás odhlásí, ale po přihlášení zůstane profil i nastavení stejné na všech zařízeních. Osobní data ani motiv nejsou v localStorage/IndexedDB. Originály i očištěné náhledy účtenek jsou v DB jako binární obsah. Citlivá konfigurace je v proměnných prostředí. Vzhled je neutrální modrý/šedý/bílý.

OCR se zatím neimplementuje. VIN lze zadat ručně; automatické dohledání a požadované ilustrační fotografie modelu patří do fáze 8 podle [návrhu integrací](docs/INTEGRATIONS.md). Fáze 6 ani další nezačínají bez samostatného pokynu.

**Ověření fáze 5:** 192 backendových, 28 frontendových testů a 22 regresních E2E prošlo; dalších 6 E2E ověřilo skutečný lokální produkční build přes HTTPS nginx/Gunicorn (cookies, fallback, chyby, PWA, výpadek a retry). Prošly lint/typecheck/build, OpenAPI a konfigurace Compose. **Docker start/build/restart zůstává neověřený**, daemon chybí. Automatická přístupnost a ruční klávesnice prošly; skutečný zoom 200 %, poslech VoiceOver a reprezentativní měření člověkem nejsou ověřené. Přesné výsledky, příkazy a limity jsou v [předání fáze 5](docs/PHASE_5.md).

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
docker compose -f compose.yaml -f compose.dev.yaml exec frontend npm run lint
docker compose -f compose.yaml -f compose.dev.yaml exec frontend npm run build
python3 infra/verify_compose.py
```

Pytest explicitně používá testovací settings a vlastní databázi `test_tanklog`, nikoli běžná data. Pro Playwright je nutný testovací účet a **samostatná E2E databáze**; přesný izolovaný postup i příkazy pro nativní ověření jsou v [PHASE_1.md](docs/PHASE_1.md). Nevytvářejte syntetické účty v produkční DB.

## Ruční ověření

1. Přihlaste se prvním ADMIN. Přehled ukazuje nákupní součty a podložené měření za výchozí měsíc; bez dat vysvětlí nedostatek podkladů.
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

## Ruční ověření spotřeby a dashboardu (fáze 4)

1. Přidejte syntetické auto s počátečním tachometrem 0, palivem Benzín a normou 6 l/100 km (WLTP, zdroj „Syntetická norma“).
2. Vložte 31. 1. 2026 plnou při 10 000 km / 50 l / 2 000 Kč, 1. 2. částečnou při 10 300 km / 20 l / 800 Kč a 5. 2. plnou při 10 600 km / 25 l / 1 000 Kč.
3. Na detailu auta otevřete Statistiky a spotřeba a vyberte únor 2026. Nákupy jsou 45 l / 1 800 Kč, spotřeba 7,50 l/100 km, nákupní náklad 300 Kč/100 km. Pokrytí 600 km, porovnání normy +1,50 a +25 %.
4. Rozbalte pokrytí → Prohlédnout intervaly a podklady → hranice intervalu. Kotva 31. 1. je mimo filtr a její 50 l / 2 000 Kč se do měření nezapočte. Zkontrolujte všechny tři řádky.
5. Přepněte vlastní rozsah jen 1. 2.: nákup 20 l zůstane, spotřeba je Nedostatek dat. Šipky posunou stejně dlouhý rozsah; týden vždy začíná pondělím. Vyzkoušejte měsíce/rok a tabulkové alternativy grafů.
6. Opravte prostřední nákup na 15 l / 600 Kč. Únorová spotřeba se přepočte na 6,67. Označte u něj mezeru: interval bude vyřazený s důvodem a graf bez platného bodu. Po opravě se výsledek vrátí.
7. Vyzkoušejte sdílený VIEWER, archivaci a odebrání grantu: archivace zachová statistiky, odebrání přístupu po novém načtení vrátí 404. Různá paliva mají samostatné výsledky. Po smazání cookies nebo na druhém zařízení se čtou stejné podklady z DB.
8. Po instalaci Dockeru proveďte start/migrace a restart bez mazání volumes; ověřte zachování stejných statistik a příloh. Tento kontejnerový krok zde zůstává neověřený.

## Ruční ověření UX a PWA (fáze 5)

1. Vyzkoušejte šířky 360/390/768/1024/1440 px a zvětšení 200 %. Navigace, formuláře a poslední akce nesmějí být zakryté; tabulky mají vlastní posuv.
2. Použijte jen Tab/Shift+Tab/Enter/Escape: chybné přihlášení přesune focus na pole, dialog drží focus a vrátí jej. Zkontrolujte i čtečkou názvy polí, chyby a tabulky grafů. Automatický axe ani dílčí AX kontrola nenahrazují úplný test čtečky.
3. V Nastavení uložte motiv Podle zařízení, měňte světlý/tmavý systém. Poté zkuste pevný motiv, odhlášení a jiné zařízení. Preference zůstává v DB; veřejný login respektuje zařízení.
4. Pro PWA použijte lokální **produkční build** podle PHASE_5.md, nikoli vývojový Vite. Instalaci vyzkoušejte přes nabídku prohlížeče nebo dostupné tlačítko v Nastavení. Poté vypněte síť a obnovte stránku: zobrazí se pouze obecné Chybí připojení, žádná osobní data.
5. V rozepsaném formuláři vypněte síť a zkuste uložit. Údaje zůstanou v současném okně, po připojení lze zkusit stejný nákup znovu bez duplicity. Offline zápisy se neukládají.
6. Otevřete dvě okna, v jednom se odhlaste. Druhé se také vrátí na login. Po odebrání grantu nové načtení nesmí zobrazit původní kartu, historii ani obrázek.
7. Při nové verzi se nabízí načtení s upozorněním na neuložené údaje. Uložené údaje v DB se aktualizací neztrácejí. Skutečné uživatelské měření průchodu tankování 15–30 s zůstává k doplnění; asistované ověření bylo 7,298 s.

## Nativní náhled na tomto Macu

Docker zde není dostupný, ale již připravený místní náhled běží na `http://127.0.0.1:8080` s oddělenou syntetickou databází `tanklog_e2e`. Není to produkční instalace. Přesné příkazy pro opakované spuštění tohoto existujícího prostředí, testy a ruční Docker akceptaci jsou v [PHASE_5.md](docs/PHASE_5.md). Testovací účet je definovaný pouze v chráněné E2E přípravě; do běžné DB se žádné výchozí heslo nezavádí.

## Produkční varianta

`compose.prod.yaml` používá sestavený frontend, nginx a Gunicorn bez veřejných host portů; web se později připojí k existující síti NPM. Vyžaduje skutečnou HTTPS doménu, přesné hosty/originy a `NPM_TRUSTED_CIDR`. Image jsou připnuté na tag i digest; dependencies jsou zamknuté. Produkční HSTS zůstává do ověření HTTPS domény na 0 (zdokumentované varování `security.W004`). Produkční start ani vzdálené nasazení zatím nejsou povoleny.

## Dokumentace

| Dokument | Obsah |
| --- | --- |
| [Předání lokální části fáze 6](docs/PHASE_6.md) | CI, audit historie, čistá instalace a neprovedená vzdálená akceptace |
| [CI](docs/CI.md) | Workflow, připnuté nástroje a bezpečné lokální ověření |
| [Předání fáze 5](docs/PHASE_5.md) | PWA/UX/přístupnost, lokální HTTPS ověření, přesné příkazy a zbývající limity |
| [Předání fáze 4](docs/PHASE_4.md) | Spotřeba, intervaly, dashboard, ověření a přesné příkazy |
| [Předání fáze 3](docs/PHASE_3.md) | Tankování/účtenky/XLSX, aktuální ověření a přesné příkazy |
| [Předání fáze 2](docs/PHASE_2.md) | Vozidla, sdílení, aktuální testy a omezení |
| [Předání fáze 1](docs/PHASE_1.md) | Funkce, skutečné testy, přesné ověření a omezení |
| [Specifikace](docs/SPECIFICATION.md) | Pravidla a hranice MVP |
| [Architektura](docs/ARCHITECTURE.md) | Moduly, Docker, síť a proměnné |
| [Datový model](docs/DATA_MODEL.md) | Implementované účty i návrh dalších entit |
| [API](docs/API.md), [OpenAPI](docs/openapi.yaml) | Kontrakt endpointů; OpenAPI generuje aktuální implementace fází 1–5 |
| [UI a UX](docs/UI_UX.md) | Navigace a neutrální designový systém |
| [Výpočty](docs/CONSUMPTION.md) | Implementovaný algoritmus a 34 skutečně testovaných scénářů |
| [Bezpečnost](docs/SECURITY.md) | Práva, ochrany a budoucí obnova |
| [Roadmapa](docs/ROADMAP.md), [Rozhodnutí](docs/DECISIONS.md) | Etapy, akceptace a změny návrhu |
| [Integrace](docs/INTEGRATIONS.md) | Budoucí VIN/OCR |
| [Ověření fáze 0](docs/VALIDATION.md) | Historický záznam návrhové etapy |
| [AGENTS.md](AGENTS.md) | Trvalá pravidla práce |

Do Gitu nepatří `.env`, hesla, databáze, zálohy ani skutečné účtenky. Bez výslovného souhlasu se nepushuje, nenasazuje, nemaže databáze/volumes ani neprovádějí nucené Git operace.
