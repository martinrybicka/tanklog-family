# TankLog

Česká self-hosted webová aplikace pro vozidla, tankování, výdaje a výpočet spotřeby. Určená pro jednotlivce i malou skupinu uživatelů se sdílenými vozidly. Mobilní zadání tankování má být zvládnutelné za 15–30 sekund.

## Aktuální stav

**Fáze 0 – projektový návrh, připravený ke schválení (2. 11. 2026).** Při zahájení byl pracovní adresář prázdný a neobsahoval Git repozitář. V této etapě vzniká pouze dokumentace a lokální Git. Aplikace, Docker konfigurace, databáze ani běžící web zatím neexistují. Návrh není dokladem implementovaných nebo otestovaných funkcí.

Další fáze začne výhradně na samostatný pokyn uživatele. Založení soukromého GitHub repozitáře a nasazení vyžadují další výslovné schválení.

## Dokumentace

| Dokument | Obsah |
| --- | --- |
| [Specifikace](docs/SPECIFICATION.md) | Funkce, pravidla, hranice MVP a nejednoznačnosti |
| [Architektura](docs/ARCHITECTURE.md) | Stack, moduly, Docker, provozní topologie a proměnné |
| [Datový model](docs/DATA_MODEL.md) | Entity, vazby, přesnost, integrita a souběh změn |
| [API](docs/API.md) | Plánované endpointy, formáty, validace a oprávnění |
| [UI a UX](docs/UI_UX.md) | Obrazovky, navigace, wireframy a designový systém |
| [Výpočet spotřeby](docs/CONSUMPTION.md) | Přesný algoritmus a předem připravené testovací případy |
| [Bezpečnost](docs/SECURITY.md) | Matice práv, přihlášení, přílohy, zálohy a obnova |
| [Roadmapa](docs/ROADMAP.md) | Fáze 0–8, akceptační kritéria a předávání |
| [Rozhodnutí](docs/DECISIONS.md) | Zdůvodnění návrhu a zásadní body ke schválení |
| [Budoucí integrace](docs/INTEGRATIONS.md) | Průzkum oficiálního API RSV a příprava OCR |
| [Ověření fáze 0](docs/VALIDATION.md) | Skutečné kontroly, omezení a ruční revize |
| [Pravidla pro Codex](AGENTS.md) | Trvalé hranice práce v repozitáři |

## Plán použití

Správce lokálně založí první účet. Další účty vytváří administrátor; veřejná registrace nebude. Uživatel přidá vlastní auto, zadává tankování a sleduje výdaje i spotřebu. Sdílení nastavuje administrátor nad jediným vozidlem a společnou historií.

Výdaje patří do období podle dne nákupu. Spotřeba vzniká pouze mezi platnými plnými nádržemi; do období patří podle koncového tankování. Tyto dvě statistiky mohou vycházet z odlišných záznamů. Chybějící údaje se zobrazí jako „Nedostatek dat“, nikoli jako nula.

## Budoucí lokální spuštění

Cílová adresa je **http://localhost:8080**, frontend i API `/api/` na stejném originu. Následující příkazy jsou plán pro fázi 1; nyní je nelze použít, protože Compose soubory ještě nebyly vytvořeny:

```sh
cp .env.example .env
# Doplnit lokální tajné hodnoty podle budoucího .env.example.
docker compose -f compose.yaml -f compose.dev.yaml config --quiet
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py migrate
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py createsuperuser
```

Docker Compose v2 bude nutnou závislostí. PostgreSQL nebude publikovat port na hostiteli. Vývoj nabídne hot reload, produkce sestavený frontend a Gunicorn. Data a soukromé účtenky budou na persistentních svazcích. Produkční přístup povede přes externí Nginx Proxy Manager s HTTPS.

## Etapy a bezpečné zacházení

Po schválení návrhu následují samostatně schvalované etapy: základ a účty → vozidla a sdílení → tankování a export → spotřeba a dashboard → UX/PWA a bezpečnost → GitHub/CI → nasazení → VIN/OCR. Podmínky dokončení jsou v roadmapě.

Do Gitu nepatří hesla, `.env`, databáze, zálohy ani skutečné účtenky. Bez výslovného souhlasu se nemaže databáze nebo Docker volumes, neprovádějí nucené Git operace a nepřepisují produkční data.
