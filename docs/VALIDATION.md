# Ověření a předání fáze 0

Datum: 2. 11. 2026. Rozsah této etapy je dokumentace a lokální Git. Žádná aplikace, migrace, Compose, test runner ani produkční prostředí se v této fázi nevytváří.

## Výsledky kontrol

Provedeno lokálně pomocí Python standardní knihovny, Gitu a čtení oficiálních webových zdrojů:

| Kontrola | Výsledek |
| --- | --- |
| Počáteční inventura `ls -la`, `git status` a hledání AGENTS | Prázdný projekt, bez existujícího repozitáře a bez nalezených nadřazených pravidel |
| Povinné dokumenty a přílohy | 13/13 Markdown souborů existuje a má obsah; navíc `.gitignore` |
| UTF-8, ukončení řádků a párové Markdown code fences | Prošlo ve všech 13 dokumentech |
| Relativní Markdown odkazy | 34/34 existujících cílových souborů |
| Testovací specifikace | C01–C34, bez duplicit/chybějícího ID; **nejde o spuštěné testy aplikace** |
| Nezávislá aritmetika přes Python Decimal | 14 příkladů, včetně vážené spotřeby, nákladů, slevy/zaokrouhlení a procent normy; prošlo |
| Kontrasty šesti dvojic hlavních tokenů | 13,38; 6,02; 4,93; 15,25; 6,95; 8,68 : 1; všechny ≥ 4,5 : 1 |
| Ruční konzistence | Model, matice práv a endpointy zrevidovány; zpřesněno zneplatnění předchozího dotčeného intervalu při poklesu km (C15/C30) |
| Oficiální technické zdroje a RSV dokumentace | Přečteny; odkazy a omezení jsou v architektuře a integracích |
| `git diff --cached --check` a staged obsah | Prošlo; pouze očekávaných 14 dokumentačních/ochranných souborů, bez symlinků a aplikační implementace |
| `.gitignore` | 9/9 případů prošlo: tajná/provozní data ignorována, `.env.example` a dokumentace povoleny |
| Git remotes | Žádné; repozitář zůstává lokální |

Python kontrola aritmetiky porovnává přímo `Decimal` výsledky s očekávanými hodnotami C04/05/10/13/16/17/18/21/22/24/28/30 a dále zaokrouhlení C23 a procentní rozdíl C33. Neimplementuje výpočet intervalů, nepotvrzuje správnost budoucího backendu. Kontrasty jsou vypočtené relativní luminancí sRGB, nikoli měřené na hotových komponentách.

Při prvním průchodu kontroly odkazů ještě chyběl tento ověřovací dokument; byl doplněn a kompletní kontrola opakována úspěšně. Docker CLI nebylo nalezeno v PATH (`command -v docker` / `shutil.which('docker')`). Docker, API, frontendové ani E2E testy nebyly spuštěny; zároveň zatím neexistuje jejich implementace. Nebyl proveden push, založení GitHub repozitáře nebo vzdálený deployment.

## Přesný postup ručního ověření návrhu

1. Otevřít [README](../README.md). Ověřit označení fáze 0 a projít odkazy v přehledu dokumentace. Lokální web na portu 8080 se ještě nespouští.
2. V [DECISIONS.md](DECISIONS.md) projít pět skupin zásadních rozhodnutí. Připomínky lze označit konkrétním ADR ID; automaticky tím nevzniká oprávnění k další etapě.
3. Porovnat matici v [SECURITY.md](SECURITY.md) s endpointy v [API.md](API.md): VIEWER pouze čte, CONTRIBUTOR upraví vlastní aktivní tankování, OWNER spravuje auto/historii a ADMIN sdílení/účty. Odebrané sdílení zruší i přístup k dříve vlastnoručně přidaným záznamům.
4. V [CONSUMPTION.md](CONSUMPTION.md) projít zejména C05 (20 + 25 l / 600 km = 7,50), C06 (mezilehlý chybějící tachometr), C11 (pokles), C13 (vážený průměr 5,33) a C19–C21 (období a náklady). Ověřit, že navržené chování odpovídá zamýšlenému používání.
5. V [UI_UX.md](UI_UX.md) projít mobilní zadání a dashboard. Potvrdit srozumitelnost volby plné nádrže, pořadí ve dni, přesné částky a popisků podkladů statistik. Wireframy jsou textový návrh, nikoli hotový vizuál.
6. V [ARCHITECTURE.md](ARCHITECTURE.md) zkontrolovat plán localhost:8080 a neveřejnou DB. V [ROADMAP.md](ROADMAP.md) projít rozsah a akceptaci fáze 1. Dokumentované příkazy spuštění budou použitelné až po implementaci Compose v další etapě.
7. Po dokončení ověřit lokální commit příkazy níže. Neprovádět push. Případné schválení návrhu a pokyn k fázi 1 jsou dvě samostatné věci.

```sh
git status --short --branch
git log -1 --oneline
git show --stat --oneline HEAD
git remote -v
git show --format= --check HEAD
```

Očekávání po předání: čistý working tree, jeden počáteční dokumentační commit a žádný remote. Poslední kontrola bez hlášených whitespace chyb.

## Soubory vzniklé ve fázi 0

- `README.md`, `AGENTS.md`, `.gitignore`.
- `docs/SPECIFICATION.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/API.md`.
- `docs/UI_UX.md`, `docs/ROADMAP.md`, `docs/SECURITY.md`, `docs/DECISIONS.md`.
- `docs/CONSUMPTION.md`, `docs/INTEGRATIONS.md`, `docs/VALIDATION.md`.

Základních deset dokumentů podle zadání doplňují tři odborné/ověřovací přílohy a `.gitignore` pro bezpečné zahájení lokálního Gitu. Soubory `compose*.yaml`, `.env.example`, `.dockerignore` a aplikační adresáře jsou pouze naplánované do fáze 1.

## Omezení a nezrealizované části

Frontend/backend, databáze, běhové testy, hot reload, skutečné bezpečnostní nastavení, PWA a nasazení zatím neexistují. Nebyl proveden autorizovaný dotaz do RSV, založena registrace ani získán API klíč. U verzí byl ověřen oficiální dokumentovaný stav; přesné patche, vzájemná kompatibilita a locky se ověří až při implementaci. Kontrasty jednotlivých navržených tokenů nejsou test přístupnosti hotového UI.
