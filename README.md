# TankLog

Česká self-hosted aplikace pro vozidla, tankování, výdaje a spotřebu, postupně vyvíjená po schválených etapách.

## Aktuální stav

**Implementována fáze 1 – základ aplikace, účty a zabezpečení (2. 11. 2026).** Přihlášení/odhlášení, vlastní profil a motiv, změna hesla, administrace účtů, jednorázová dočasná hesla, aktivace/deaktivace, ochrana loginu, audit a bezpečné systémové informace. React/TypeScript/Vite + Django/DRF/PostgreSQL, jeden origin a API pod `/api/v1/`.

Podle doplňujícího požadavku jsou **všechna uložená aplikační data v PostgreSQL**. Cookie pouze identifikuje přihlášení; smazání cookies vás odhlásí, ale po přihlášení zůstane profil i nastavení stejné na všech zařízeních. Osobní data ani motiv nejsou v localStorage/IndexedDB. Budoucí účtenky budou také v DB jako binární obsah. Citlivá konfigurace je v proměnných prostředí. Vzhled je neutrální modrý/šedý/bílý.

Vozidla, tankování, spotřeba, exporty, VIN a OCR se v této etapě neimplementují. Rozhraní je výslovně označuje jako budoucí funkce. Fáze 2 čeká na další pokyn.

**Ověření:** backend a prohlížečové testy běžely lokálně proti skutečnému PostgreSQL. Obě konfigurace Compose byly strojově zkontrolované. Docker daemon zde chybí; kontejnery, jejich restart/persistence a produkční Docker build nebylo možné spustit. Podrobné výsledky a omezení jsou v [předání fáze 1](docs/PHASE_1.md).

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

1. Přihlaste se prvním ADMIN. Přehled ukazuje stav fáze 1 a odkazy na skutečně dostupné funkce.
2. V Nastavení změňte zobrazované jméno, kontakt a motiv. Uložte, obnovte stránku a ověřte zachování údajů.
3. Smažte cookies pro localhost; po novém přihlášení zůstanou stejné údaje i motiv. Totéž ověřte v anonymním okně nebo druhém prohlížeči.
4. V administraci vytvořte USER. Vlastní heslo správce potvrzuje operaci; jednorázové heslo si přečtěte před zavřením dialogu a předejte soukromě.
5. V druhém okně se přihlaste novým účtem, nastavte nové heslo. Před změnou se nelze dostat do profilu ani administrace; původní dočasné heslo už podruhé nefunguje.
6. ADMIN účet USER deaktivuje, ověří odhlášení jeho session, znovu aktivuje a případně vydá nový reset. Změnu vlastního hesla provádí každý přes Nastavení; ADMIN nemůže tímto dialogem resetovat sám sebe.
7. Projděte audit, filtry účtů a systémové informace. Běžný USER administrační API nepoužije ani přímou URL.
8. Restartujte kontejnery a zkontrolujte zachování účtů, profilu a auditu. Tento konkrétní krok je zde kvůli chybějícímu Docker daemonu zatím neověřený.

## Produkční varianta

`compose.prod.yaml` používá sestavený frontend, nginx a Gunicorn bez veřejných host portů; web se později připojí k existující síti NPM. Vyžaduje skutečnou HTTPS doménu, přesné hosty/originy a `NPM_TRUSTED_CIDR`. Image jsou připnuté na tag i digest; dependencies jsou zamknuté. Produkční HSTS zůstává do ověření HTTPS domény na 0 (zdokumentované varování `security.W004`). Produkční start ani vzdálené nasazení zatím nejsou povoleny.

## Dokumentace

| Dokument | Obsah |
| --- | --- |
| [Předání fáze 1](docs/PHASE_1.md) | Funkce, skutečné testy, přesné ověření a omezení |
| [Specifikace](docs/SPECIFICATION.md) | Pravidla a hranice MVP |
| [Architektura](docs/ARCHITECTURE.md) | Moduly, Docker, síť a proměnné |
| [Datový model](docs/DATA_MODEL.md) | Implementované účty i návrh dalších entit |
| [API](docs/API.md), [OpenAPI](docs/openapi.yaml) | Kontrakt endpointů; OpenAPI generuje implementace fáze 1 |
| [UI a UX](docs/UI_UX.md) | Navigace a neutrální designový systém |
| [Výpočty](docs/CONSUMPTION.md) | Budoucí algoritmus a 34 testovacích specifikací pro fázi 4 |
| [Bezpečnost](docs/SECURITY.md) | Práva, ochrany a budoucí obnova |
| [Roadmapa](docs/ROADMAP.md), [Rozhodnutí](docs/DECISIONS.md) | Etapy, akceptace a změny návrhu |
| [Integrace](docs/INTEGRATIONS.md) | Budoucí VIN/OCR |
| [Ověření fáze 0](docs/VALIDATION.md) | Historický záznam návrhové etapy |
| [AGENTS.md](AGENTS.md) | Trvalá pravidla práce |

Do Gitu nepatří `.env`, hesla, databáze, zálohy ani skutečné účtenky. Bez výslovného souhlasu se nepushuje, nenasazuje, nemaže databáze/volumes ani neprovádějí nucené Git operace.
