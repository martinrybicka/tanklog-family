# Jednoduché rodinné rozhraní

Samostatný pokyn uživatele z 4. 11. 2026: zachovat plnou verzi a vytvořit jednoduché moderní rozhraní pro rodinu, s minimem práce při přidání účtenky a s nastavováním členů správcem. Nejde o povolení publikace nebo nasazení.

## Zachování původní verze

- Původní kompletní aplikace: větev `codex/tanklog-kompletni-faze-8`, commit `4f43558`.
- Nové rozhraní: větev `codex/rodinne-rozhrani`, stejný React/Django/PostgreSQL projekt.
- Podrobný dashboard dál běží na `/prehled`, původní auta/tankování/servis/import a administrace mají dosavadní cesty. Každodenní práce začíná na `/`.
- Návrat k původnímu zdroji po uložení vlastní práce: `git switch codex/tanklog-kompletni-faze-8`. Návrat do nové varianty: `git switch codex/rodinne-rozhrani`. Nemažte DB ani nevracejte migrace kvůli prohlídce starého UI; nové tabulky mohou v DB zůstat.

## Co je implementované

1. Jednoduchá domovská obrazovka, přechodová ilustrace s autem, konzistentní Lucide ikony a bílé karty s pastelovými akcenty. Skutečné měsíční nákupní součty, poslední tankování a stručná garáž; bez vymyšlených grafů.
2. Tři položky navigace: Domů / Přidat účtenku / Historie. Na mobilu dostupné dole, účet v horní nabídce. Nastavení a pokročilé nástroje neblokují základní cestu.
3. Účtenka jako první: fotoaparát nebo existující JPEG/PNG → soukromý DB návrh → skutečné lokální OCR → kontrola → uložení. Vznik návrhu nevytvoří fiktivní nákup. Fotografie i tankování se při potvrzení uloží v jediné transakci.
4. Předvyplněné auto od správce, při jediném dostupném autě automatická volba; datum je předvyplněné. Uživatel kontroluje datum/litry/částku, může doplnit km a plnou nádrž. Částka účtenky má nadále přednost, chybějící km a další varování musí potvrdit.
5. Ruční cesta bez účtenky a fallback při nefunkčním OCR. Neúspěšný upload ani opakované potvrzení nevytváří duplicity. Přečtení podléhá původním lokálním limitům, nikoli cloudové službě.
6. Fotka a uložené návrhy OCR čekají v PostgreSQL i po odhlášení nebo na jiném zařízení; Domů nabídne pokračování. Neuložené ruční opravy polí se zatím neautosavují, při reloadu/zavření se ztratí.
7. Jednoduchá historie s filtrem auta a stránkováním, čitelný detail a soukromá účtenka. Oprava již uloženého záznamu používá dosavadní úplný formulář, aby se zachovala jeho pravidla.
8. Správa rodiny jen pro ADMIN: odkazy na účty, auta/granty a podrobné přehledy; vyhledání člena a nastavení jeho výchozího auta. Nastavení platí na všech zařízeních, nepřidává práva a server nepovolí auto bez přístupu či zápisového oprávnění.
9. Původní bezpečnost, aktivní účet, omezená session, CSRF, objektová oprávnění, Decimal, varování, zámky, ETag a idempotence se používají i na nové cestě. Soukromá data nejsou v localStorage/IndexedDB/SW cache.
10. Nginx dává novému upload endpointu stejný omezený 12 MiB průchod jako původním účtenkám; aplikační limit je 10 MiB/24 MP. Ostatní API dál používá limit 1 MiB.

## Skutečné ověření

| Kontrola | Výsledek |
| --- | --- |
| Backend pytest nad PostgreSQL | **236 prošlo / 47,96 s**, včetně 10 nových testů rodinné cesty. |
| Frontend | **30 prošlo**, lint/TypeScript/Vite/PWA build a formátování prošly. |
| HTTP E2E | **28 prošlo** ve společném běhu; dva staré testy logoutu očekávaly staré tlačítko místo nové nabídky účtu. Po aktualizaci ovládání nabídky **oba prošly (6,5 s)**. Celkem ověřeno všech 30 scénářů, desktop i mobil. |
| Nové rodinné E2E | Člen rodiny: skutečné OCR syntetické účtenky, kontrola, návrat k DB návrhu, potvrzení a detail s obrázkem; ruční zápis/varování; ADMIN konfigurace. Oba viewporty prošly. |
| Přístupnost | Axe bez nálezů na Domů, kontrole účtenky, detailu a správě rodiny v E2E. Dodatečná kontrola Domů / upload / historie na mobilu ve světlém i tmavém motivu: **6/6 bez nálezů**. Není to úplný audit skutečnou čtečkou. |
| Vizuální kontrola | Prohlédnuté vlastní syntetické screenshoty domovské stránky na desktopu a mobilu; obrázky/logy jen v ignorovaném `.runtime`. |
| Migrace a Django | `family/0001` skutečně aplikována v izolované testovací/E2E/CI a běžné místní DB, check bez chyb, makemigrations bez změn. |
| OpenAPI | Opravené unikátní ID list endpointu, aktuální `docs/openapi.yaml` generováno s validate/fail-on-warn bez varování. Původní společný kontrolní příkaz se na této kolizi zastavil; testy v něm předtím prošly a po opravě byla úspěšně zopakována generace schématu. |
| Infrastruktura | 11 testů CI a 10 provozních pravidel prošlo; Ruff, actionlint a workflow politika prošly. |
| Produkční build přes lokální HTTPS | **12 prošlo / 24,8 s**: původních 6 produkčních/PWA scénářů a 6 rodinných scénářů přes nginx/Gunicorn. Ověřené jsou i limity nového uploadu, cookies/CSRF a soukromá cache. Jen místní syntetická DB a testovací certifikát. |
| `check --deploy` | Pouze dříve známé security.W004 (HSTS=0 podle ADR-027 do konkrétního ověřeného HTTPS nasazení). |
| Compose | Dev/prod/CI/operations/restore konfigurační kontrola prošla. Skutečný dev start znovu skončil na chybějícím `/var/run/docker.sock`; běh kontejnerů není ověřený. |

Nativní ověření používá macOS, Python 3.14.6, Node 26.13.0, PostgreSQL 18.6 a Tesseract 5.5.4 s uzamčenými modely. Nic nebylo odeslané na GitHub/produkci. Změna nezavádí nové Python/npm závislosti ani externí fontovou či grafickou službu.

## Otevření a přihlášení

V připraveném místním náhledu otevřete **http://127.0.0.1:8080**. Používá oddělenou syntetickou DB `tanklog_e2e`.

- Správce: dosavadní `e2e-admin`.
- Běžný ukázkový člen: `family-desktop` nebo `family-mobile`.
- Heslo těchto výhradně syntetických účtů: `Synthetic-Test-Account-2026!`.

Jsou to veřejně známé testovací údaje pouze pro lokální E2E náhled. Běžná DB `tanklog` je samostatná; vytvořte si v ní vlastní účet, pro vlastní data nepoužívejte testovací přihlášení.

## Lokální spuštění

S Docker daemonem z kořene projektu:

```sh
python3 infra/setup_env.py
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py migrate
docker compose -f compose.yaml -f compose.dev.yaml exec backend python manage.py createsuperuser
```

Nativně na již připraveném Macu se zdejším PostgreSQL na 55432, každý server ve vlastním terminálu:

```sh
export PATH="$PWD/.tools/node-ci/node-v26.13.0-darwin-arm64/bin:$PATH"
# Vlastní evidence: DB tanklog; před spuštěním zastavte dřívější vlastní proces na 8000.
POSTGRES_DB=tanklog POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py migrate
POSTGRES_DB=tanklog POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py createsuperuser
POSTGRES_DB=tanklog POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python manage.py runserver 127.0.0.1:8000
# Druhý terminál, po zastavení dřívějšího vlastního Vite na 8080:
export PATH="$PWD/.tools/node-ci/node-v26.13.0-darwin-arm64/bin:$PATH"
API_PROXY_TARGET=http://127.0.0.1:8000 HMR_CLIENT_PORT=8080 npm run dev --prefix frontend -- --host 127.0.0.1 --port 8080
```

Pro opětovný testovací náhled nahraďte explicitně DB názvem `tanklog_e2e`. Nezakládejte syntetické účty v běžné DB. Postup nainstalování již zamčených závislostí/modelů je v PHASE_8.md. API_PROXY_TARGET je u nativního Vite důležité; Docker používá interní backend:8000. Nová migrace nepřevádí ani nemaže původní data.

## Ruční průchod

1. Přihlaste správce a otevřete Správa rodiny. Připravte účty a auta, členům dejte vlastnictví nebo grant Přispěvatel. Potom vyhledejte člena a nastavte výchozí auto. Neplatná volba právo nepřidá.
2. Přihlaste běžného člena. Domů má tři navigační položky a výrazné Přidat účtenku; nevypisuje VIN, normy, audit ani pokročilé tabulky.
3. Vyfoťte nebo vyberte vlastní testovací JPEG/PNG. Auto je předvyplněné, pokud ho správce nastavil nebo je dostupné jediné. Přečíst účtenku → zkontrolovat datum/litry/částku, případně km/plnou → Potvrdit a uložit.
4. Potvrďte případná varování; vznikne jediné tankování a účtenka. V Historii otevřete detail a zkontrolujte obrázek i přesnou částku. Opakování po výpadku nesmí udělat duplicitu.
5. Zvolte Dokončit později, odhlaste se nebo přejděte na další zařízení. Z Domů znovu otevřete uloženou fotografii/OCR návrhy. Neuložené ruční korekce se zatím nepřenášejí.
6. Zkuste Nemám účtenku, doplním ručně; datum je předvyplněné a stačí litry/částka. Bez OCR nebo při chybě se dá fotografie uložit a data zadat ručně.
7. Otevřete účet → odhlášení, také se druhým otevřeným oknem. Přihlášená soukromá data musí zmizet. Odeberte grant a ověřte nedostupnost přímého obrázku/návrhu. Běžný člen nesmí otevřít Správu rodiny.
8. Správce otevře Podrobné přehledy a původní nástroje. Na mobilu ověřte výběr existujícího souboru i fotoaparát, fokus a oba motivy.

## Omezení

OCR zůstává pomocník s povinnou kontrolou, skutečné fotografie mohou potřebovat ruční opravu. Podporuje JPEG/PNG, nikoli HEIC/PDF; fyzický fotoaparát telefonu a reálná čtečka nebyly tímto headless testem ověřené. Vyzkoušena je vlastní syntetická česká účtenka.

Nehotové návrhy zatím nemají automatickou retenci, seznam nabízí nejnovějších 20 a dokončené podklady zůstávají vedle přílohy v DB. Ruční změny polí nejsou automaticky ukládané; trvale uložené jsou fotografie a původní OCR návrhy, pak potvrzený záznam. Již uložená tankování se opravují původním formulářem. Plná správa účtů/grantů stále používá existující administrační obrazovky.

Docker/Linux image, vzdálený CI, skutečné nasazení a živé VIN/foto propojení zůstávají v dříve popsaném stavu, nejsou touto UI úpravou ověřené ani povolené. Běží jen místní náhled; pro dokončení nebyly použité skutečné doklady ani produkční data.
