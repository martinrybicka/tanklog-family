# Plán API v1

Kontrakt API v1. Implementované jsou autentizace, profil, uživatelé, systém, audit, health, vozidla/sdílení a od fáze 3 tankování/účtenky/XLSX; od fáze 4 také statistiky/dashboard a intervalové podklady. Základ `/api/v1/` pod stejným originem jako SPA. Všechny cesty níže mají koncové lomítko. Strojově generovaný aktuální kontrakt je [openapi.yaml](openapi.yaml), také dostupný přihlášenému ADMIN na `admin/schema/`. Aktuální výsledky a limity ověření jsou v PHASE_4.md.

## 1. Společná pravidla

- JSON, UUID jako řetězce, datum `YYYY-MM-DD`, technický timestamp ISO 8601 UTC (`...Z`). Decimal vstupy/výstupy jako řetězce s tečkou; UI přijímá českou čárku a před odesláním ji bezpečně normalizuje.
- Session cookie HttpOnly, `credentials: same-origin`. CSRF token z bootstrap endpointu a hlavička `X-CSRFToken` u každé mutace včetně přihlášení a odhlášení. Žádné mutace přes GET.
- Výchozí oprávnění vyžaduje aktivní účet s plnou session. Omezená session po dočasném hesle smí jen CSRF, minimální `me`, změnu hesla a logout. Výjimky pro veřejné cesty jsou výslovné.
- Nepřihlášený požadavek podle standardní DRF SessionAuthentication vrací 403 s `authentication_required`; přihlášený bez akčního práva 403 `permission_denied`. Nepřístupné objektové ID nebo cizí FK vrací 404. Klient rozlišuje strojový kód, nikoli pouze HTTP 403. [DRF popis autentizace](https://www.django-rest-framework.org/api-guide/authentication/).
- 400 pro nevalidní vstup, 409 pro konfliktní doménový stav/potřebné potvrzení, 412 pro starou verzi, 413 pro velký upload, 415 pro nepodporovaný formát, 428 při chybějící předepsané podmínce změny, 429 s `Retry-After` pro limit. Chyby mají jednotnou podobu, i CSRF chyby; žádné HTML tracebacky.
- PATCH/DELETE existujících měnitelných objektů vyžadují `If-Match` s ETag z detailu. ETag je silný a zahrnuje typ, ID a verzi. Zápis pod zámkem znovu ověří práva i verzi. Neúspěšný zápis nemění data. Pouze výslovně popsané příkazové endpointy používají místo ETag požadavek na aktuální heslo/reautentizaci.
- Seznam: `page` od 1, `page_size` výchozí 25/max. 100; odpověď `{count, next, previous, results}`. Whitelist řazení, stabilní sekundární pořadí, validace neznámých parametrů/JSON polí. `count` jen z přístupné množiny.
- Soukromá API data, resetovací odpovědi, exporty a přílohy: `Cache-Control: private, no-store`; žádná CDN nebo service-worker cache. Po ztrátě přístupu se kontroluje i download.

Příklad chyby:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Zkontrolujte zadané údaje.",
    "fields": {"liters": [{"code": "positive_required", "message": "Zadejte více než 0 litrů."}]},
    "request_id": "f3c2d67c-0235-43de-ac19-c69928ebfa85"
  }
}
```

## 2. Autentizace a profil – fáze 1

| Metoda a cesta | Přístup | Chování |
| --- | --- | --- |
| GET `auth/csrf/` | Veřejné | Nastaví CSRF cookie a vrátí maskovaný `csrf_token`, bez cache |
| POST `auth/login/` | Veřejné + CSRF + limity | `{username, password}`; 200 s minimálním uživatelem a `must_change_password`; rotace session a CSRF |
| POST `auth/logout/` | Session + CSRF | 204, zrušení aktuální session; idempotentní výsledek i při již odhlášeném klientovi |
| GET `auth/me/` | Session | 200 `{id, username, display_name, system_role, must_change_password, theme}`; omezené session jen údaje nutné ke změně hesla |
| PATCH `profile/` | Plná session + If-Match | Jen `display_name`, `email`, `theme`; žádná role/aktivace/username |
| GET `profile/` | Plná session | Vlastní profil s ETag |
| POST `auth/password/change/` | Session + CSRF | Běžně `{current_password, new_password}`; omezená session jen `{new_password}`. Vždy validátory, zneplatnění starých sessions a založení aktuální plné session |

Po loginu klient obnoví CSRF token, protože se rotuje. Selhání přihlášení používá stejné sdělení pro neexistující, deaktivovaný účet a nesprávné/propadlé heslo. Resetovací heslo ani nové heslo se nevracejí z loginu. Neexistují veřejné `register` nebo `forgot-password` endpointy.

## 3. Uživatelé a systém – fáze 1, průběžně rozšiřované

Prefix `admin/`, vždy systémový ADMIN s plnou session. Citlivé akce (reset, změna role, deaktivace, převod) navíc vyžadují v těle `current_password` jako aktuální reautentizaci správce; nezapisovat jej do logu nebo auditu.

| Metoda a cesta | Chování |
| --- | --- |
| GET `admin/users/` | Stránkované účty; filtry aktivace/role/hledání, bez hashů a tajných polí |
| POST `admin/users/` | `{username, display_name, email?, system_role, current_password}`; vytvoření a jednorázové vydání dočasného hesla, 201 |
| GET `admin/users/{id}/` | Detail s ETag; žádný návrat dříve vydaného hesla |
| PATCH `admin/users/{id}/` | If-Match; jméno, kontakt, role; citlivá změna s current_password |
| POST `admin/users/{id}/deactivate/` | If-Match + current_password; 200; revokace sessions, ochrana posledního ADMIN |
| POST `admin/users/{id}/activate/` | If-Match + current_password; 200, vyžádat nový reset pokud nejsou platné přihlašovací údaje |
| POST `admin/users/{id}/password-reset/` | If-Match + current_password; vydat nové jednorázové dočasné heslo, expirovat staré a sessions |
| GET `admin/system/` | Verze aplikace, bezpečné health informace; žádné kompletní env, adresáře a secrets |
| GET `admin/audit/` | Stránkovaný audit s filtry času/akce/objektu; bez zapisovacího endpointu |

Vydání dočasného hesla vrátí pouze v dané odpovědi `{user_id, temporary_password, expires_at, must_change_password: true}` s no-store. Při ztrátě odpovědi se vydá nové heslo, původní nelze znovu přečíst. UI ho zobrazí jednorázově správci pro předání soukromým kanálem mimo aplikaci. Nemá vlastní tlačítko automatického odeslání e-mailu.

Reset vlastního účtu tímto administračním endpointem vrátí 409 `self_reset_forbidden`; vlastní heslo se mění přes `auth/password/change/`. Předejde se odhlášení správce před bezpečným přečtením jednorázového hesla. Nové uživatelské jméno je ASCII a normalizované na malá písmena. Profil/motiv jsou uložené v DB a čtou se shodně po novém přihlášení i z jiného zařízení.

## 4. Vozidla a sdílení – fáze 2

| Metoda a cesta | Právo a chování |
| --- | --- |
| GET `vehicles/` | Všechna přístupná auta; filtr `status=active|archived|all`, výchozí active; pole `effective_role`, `permissions` |
| POST `vehicles/` | USER/ADMIN vytvoří vlastní auto; vlastník se odvodí ze session, 201 |
| GET `vehicles/{id}/` | VIEWER+, detail a ETag; práva a `history_revision` |
| PATCH `vehicles/{id}/` | OWNER/ADMIN + If-Match; pouze metadatová pole, nikoli vlastnictví |
| POST `vehicles/{id}/archive/` | OWNER/ADMIN + If-Match, 200, bez odstranění historie |
| POST `vehicles/{id}/restore/` | OWNER/ADMIN + If-Match, 200 |
| GET `admin/vehicles/` | ADMIN, všechna auta včetně archivovaných |
| GET `admin/vehicles/{id}/access/` | ADMIN, granty s vlastními ETag; vlastník odděleně |
| POST `admin/vehicles/{id}/access/` | ADMIN, `{user_id, role}` VIEWER/CONTRIBUTOR, 201; duplicita 409 |
| GET `admin/vehicle-access/{id}/` | ADMIN, detail grantu a ETag |
| PATCH `admin/vehicle-access/{id}/` | ADMIN + If-Match, změna role grantu |
| DELETE `admin/vehicle-access/{id}/` | ADMIN + If-Match, 204 |
| POST `admin/vehicles/{id}/transfer-owner/` | ADMIN + If-Match vozidla + current_password; `{new_owner_id, previous_owner_role?}`; absence role odebere přístup původního vlastníka |

Seznamy vehicles jsou stránkované `{count, next, previous, results}` se stabilním řazením podle názvu a UUID; `admin/vehicles/` má výchozí status all a podporuje jen čtení. Běžný seznam má výchozí active (ADMIN i zde vidí všechna vozidla dle filtru). Detail vozidla vrací ETag `"vehicle:<id>:<version>"`, grant `"vehicle-access:<id>:<version>"`. Každá změna sdílení zvyšuje i version vozidla; zastaralý převod vrátí 412. Missing If-Match vrací 428. Archive/restore přijímají prázdný JSON objekt a vracejí detail vozidla. Veřejné mazání vozidla není implementované; použijte archivaci.

Access seznam vrací `{owner_id, owner: {username, display_name}, results: [...]}` bez dalších údajů účtů. Grant obsahuje id/vehicle_id/user_id, username/display_name/is_active, role/granted_by_id/version a timestamps. Neaktivní účet nelze nově sdílet ani zvolit jako nového vlastníka. Explicitní grant původnímu vlastníkovi lze zachovat i při jeho neaktivitě; aktivní přístup tím nevzniká. Systémový ADMIN má vždy globální oprávnění, i po převodu či odebrání grantu.

Norma a technické údaje odpovídají datovému modelu. Neexistuje veřejný seznam všech uživatelů pro běžného uživatele. Od fáze 3 pro volbu plátce slouží GET `vehicles/{id}/payer-options/` (právo přidat/upravit tankování), vrátí pouze ID a zobrazované jméno aktivních účtů s přístupem k danému autu; e-maily a systémové role nevrací.

## 5. Tankování a účtenky – fáze 3

| Metoda a cesta | Právo a chování |
| --- | --- |
| GET `refuelings/` | Přístupná auta, filtry níže; stránkovaný seznam |
| POST `refuelings/` | CONTRIBUTOR/OWNER/ADMIN na aktivním autě; povinný `Idempotency-Key` UUID; 201 |
| GET `refuelings/{id}/` | VIEWER+, detail s ETag a oprávněními |
| PATCH `refuelings/{id}/` | CONTRIBUTOR vlastní na aktivním autě, OWNER/ADMIN libovolné i archivované; If-Match |
| DELETE `refuelings/{id}/` | OWNER/ADMIN + If-Match, 204; audit a nové intervaly |
| GET `vehicles/{id}/refueling-order/` | VIEWER+, `date=YYYY-MM-DD`; aktuální seznam ID a ETag historie |
| PUT `vehicles/{id}/refueling-order/` | OWNER/ADMIN + If-Match historie; `{date, ordered_ids}` musí obsahovat přesně všechna ID dne jednou |
| GET `refuelings/export/` | VIEWER+, shodné filtry/řazení jako seznam, bez paginace; XLSX |
| POST `refuelings/{id}/receipt/` | Právo upravit záznam + If-Match tankování; multipart `file`, 201, pokud ještě není účtenka |
| PUT `refuelings/{id}/receipt/` | Stejné právo + If-Match tankování; atomická náhrada, 200 |
| GET `refuelings/{id}/receipt/` | VIEWER+, autorizovaný originál; parametr `variant=preview` pro náhled |
| DELETE `refuelings/{id}/receipt/` | Právo upravit záznam + If-Match tankování, 204 |

Exportní cesta musí mít přednost před routerem detailu. API nepovolí přepsání `vehicle_id`, autora, verze nebo storage key přes PATCH. Přílohy se nahrávají po vytvoření tankování; úspěšné tankování nezmizí při chybě souboru. Všechny změny přílohy zvýší verzi tankování, aby neproběhly dvě náhrady nad starým formulářem.

Vstup vytvoření (bez nepovinných polí přílohy):

```json
{
  "vehicle_id": "31cdd7a5-d6e8-4a95-9b5d-9673be6abeaf",
  "date": "2026-11-02",
  "liters": "42.350",
  "unit_price_entered": "38.9000",
  "total_amount": "1647.00",
  "odometer_km": 10600,
  "is_full_tank": true,
  "fuel_type": "PETROL",
  "station_code": "ORLEN",
  "break_before": false,
  "note": "",
  "confirmed_warning_codes": ["amount_difference"]
}
```

Při vynechání `total_amount` jej server vypočte z litrů/ceny. Nulová částka vyžaduje výslovně zadané `total_amount="0.00"` a potvrzení varování; nelze ji získat jen vynecháním částky a nulovou cenou. Při změně litrů/ceny v PATCH se vypočtená částka znovu navrhne pouze u `amount_source=CALCULATED`; explicitně zadaná částka se bez zásahu uživatele nepřepisuje. Výstup vždy vrací `amount_source`, `effective_unit_price`, `quality_warnings`, dostupné akce a revizi historie.

`day_sequence` se nabízí jako poslední pozice dne. Zvolenou pozici lze při tvorbě nebo editaci vlastního záznamu změnit s potvrzením; servis posune ostatní čísla, zachová jejich vzájemné pořadí a změnu audituje. Kompletní přeuspořádání cizích záznamů smí jen OWNER/ADMIN.

Varování bez potvrzení vrací 409 `confirmation_required` s aktuálními kódy a českým vysvětlením. Opakovaný požadavek obsahuje `confirmed_warning_codes`; server varování znovu spočítá nad aktuální historií. Idempotency klíč je stejný; hash ukládaného normalizovaného doménového vstupu ignoruje samotný transportní seznam potvrzení. Přesný retry mechanismus a minimální platnost 24 h jsou v [DATA_MODEL.md](DATA_MODEL.md). Opakování po úspěchu vrátí 200 s `Idempotency-Replayed: true` po nové kontrole přístupu; nikdy druhý záznam. Změněný payload pod již použitým klíčem vrací 409.

Filtry: `vehicle_id` (jedno UUID), `date_from`, `date_to` (inkluzivní), `fuel_type`, `station_code`, `search` max. 200 znaků. `ordering=date|-date|total_amount|-total_amount|liters|-liters|odometer_km|-odometer_km`, doplněné stabilním datum/pořadí/ID podle směru; null tachometr vždy na konci. Výchozí `-date` s klesajícím pořadím dne. Neplatný rozsah je 400, nepřístupný explicitní vehicle filtr 404, nikoli celosystémový seznam. Seznam i export využijí shodný selektor.

## 6. Statistika – fáze 4

| Metoda a cesta | Chování |
| --- | --- |
| GET `dashboard/` | Nákupní součty, intervalové součty, grafy, pokrytí a poslední tankování |
| GET `vehicles/{id}/statistics/` | Stejná metodika pro konkrétní auto včetně normy |
| GET `vehicles/{id}/consumption-intervals/` | Stránkované platné i vyloučené kandidáty, s vysvětlením |
| GET `vehicles/{id}/consumption-intervals/detail/` | `start_id`, `end_id`; znovu vypočtený aktuální kandidát a použité záznamy; 404 pokud již neexistuje |

Období: `period=day|week|month|year|custom` (výchozí month), `anchor_date` pro kalendářní období (výchozí dnešek Prague); custom vyžaduje `date_from` a `date_to`. Pro custom se anchor_date nepřijímá, kombinace nesmějí být nejednoznačné. `vehicle_id` nepovinný, bez něj množina všech přístupných aut včetně archivovaných. `group_by=day|week|month` je whitelist, výchozí granularitu určí rozsah. Pro intervalový seznam platí filtr podle koncového data.

Odpověď obsahuje konkrétní vyřešené období a `timezone`, `purchases` (výdaje, litry, počet, realizovaná cena), `consumption_by_fuel`, `coverage` (počet platných/vyloučených intervalů, km, mezní datumy, příčiny), `charts` a `recent_refuelings`. Všechny Decimal hodnoty jsou řetězce. U intervalové karty se vrací `assignment_rule=end_refueling_date` a vysvětlení; chybějící spotřeba `null` s důvodem, ne samotná nula. Detaily odkazují jen na autorizované objekty.

## 7. Technické endpointy a pozdější rozšíření

GET `/api/health/live/`: veřejná stručná živost, bez verze/DB/konfigurace. GET `/api/health/ready/`: dostupný internímu healthchecku, kontroluje DB, nevrací credentials ani chyby připojení. Tyto cesty nejsou doménové API v1.

VIN lookup a OCR budou mít nové backendové endpointy až ve fázi 8, s vlastními limity a oprávněním upravovat cílové auto/záznam. Nedeklarovat je jako dostupné a nerezervovat veřejné nechráněné uploady. Klient nikdy nevolá RSV přímo. Návrhy z externích dat/OCR se neukládají automaticky.

## 8. Implementovaný kontrakt fáze 3 – doplnění

Refueling detail i položka seznamu vracejí účetní pole modelu (UUID/datumy/Decimal řetězce), názvy auta/autora/editora/plátce, effective_unit_price (4 desetinná místa), permissions create/edit/delete/reorder, history_revision, quality_warnings a nullable receipt pouze s metadaty id/content_type/size_bytes/width/height/original_filename/version. Žádné binární pole není v JSON. Detail má ETag `"refueling:<id>:<version>"`. Seznam má výchozí stránku 25, volitelně page_size 1–100; UI načítá všechny stránky volby aut a export vynechá parametr page.

Chyba potvrzení má `error.code=confirmation_required` a `error.warnings=[{code,message}]`. Kódy: fuel_mismatch, amount_difference, tank_capacity_exceeded, missing_odometer, odometer_below_initial, odometer_decrease, similar_record, day_order, zero_amount. Potvrzují se v confirmed_warning_codes; nejde o obcházení tvrdé validace. Pole date je při vytvoření nepovinné (server Prague), při PATCH se vynechaná pole zachovávají. Prázdná stanice je `station_code=""`, ostatní stanice vyžaduje station_custom_name. Nový plátce vyžaduje aktivní přístup, neplatné/cizí ID plátce má jednotnou validační chybu 400 bez údajů účtu. Neplatný související vehicle_id/detail zůstává 404.

Payer-options vrací `{results:[{id,display_name}],today:"YYYY-MM-DD"}` s pražským dnem. Obsahuje aktivního vlastníka, grantované účty a systémové ADMIN (ti mají přístup ke všem autům), bez e-mailu nebo role. VIEWER volby nedostane.

History GET vrací `{date,ordered_ids}` a ETag `"history:<vehicle_id>:<history_revision>"`. PUT vyžaduje tentýž ETag a přesnou permutaci všech ID daného dne; vrací history_revision a nový ETag. CONTRIBUTOR může v editaci přesunout vlastní záznam, ne přeuspořádat celý den.

Receipt GET variant=original (výchozí) vrací autorizovaný originál jako attachment, variant=preview vrací image/jpeg inline bez EXIF. Neplatný variant je 400. POST/PUT multipart obsahuje právě jediný soubor file a If-Match tankování; vrací aktualizovaný detail tankování s novým ETag (201/200). DELETE vrací 204 a nový detail/ETag získá klient opětovným GET. Poškozený/neodpovídající MIME/nepovolený/animovaný obrázek je 400, překročená velikost 413, chybějící účtenka 404, POST přes existující účtenku 409, starý ETag 412. Výchozí parser mimo tento endpoint stále přijímá jen JSON. Úspěch ani neúspěch uploadu nikdy nezakládá další tankování.

DB upload limit je 20 pokusů/min/účet, nginx 30 požadavků/min/IP s burst 10. Limit vrací 429 upload_limited a Retry-After 60. Nginx request body receipt má 12 MiB, samotný soubor 10 MiB / 24 MP; dočasné request/decoder soubory nejsou trvalým úložištěm. Download/export i chybové odpovědi zůstávají private,no-store.

Export je application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, příloha tankovani.xlsx. Limit je 50 000 datových řádků (REFUELING_EXPORT_LIMIT v serverovém nastavení); překročení vrací 400 export_limit. Prázdný výsledek je validní sešit se záhlavím. Číselné/datumové typy a výslovné textové buňky se ověřují znovuotevřením sešitu v testech. Expirovaný klíč create vrací 409 idempotency_expired; jiný payload pod stejným klíčem 409 idempotency_conflict; nepřístupný/smazaný výsledek 404, bez dalšího vytvoření.

## 9. Implementovaný kontrakt fáze 4 – doplnění

Všechny čtyři statistické GET endpointy vyžadují aktivní účet a plnou session, VIEWER může číst. Čtení se provádí ve vlastním read-only REPEATABLE READ snapshotu se znovu ověřeným účtem a selektorem přístupných vozidel. Nepřístupné explicitní auto vrací 404, neshodné vehicle_id v URL a filtru 400. Neznámé filtry/nesprávné kombinace období jsou 400. Seznam intervalů přijímá page a page_size 1–100, výchozí 25. Detail vyžaduje start_id a end_id, stejné období jako seznam; při zániku hranic nebo jejich umístění mimo filtr 404. JSON neobsahuje binární účtenky ani uživatele cizích aut.

Dashboard obsahuje `available_vehicles=[{id,name,status}]` ze všech přístupných aut pro přepínač (i při aktivním vehicle filtru), konkrétní `period={period,anchor_date,date_from,date_to,timezone,group_by}`, `assignment_rule=end_refueling_date` a české `explanation`. `purchases={amount,liters,count,realized_unit_price}` používá vlastní data nákupů. `consumption_by_fuel` obsahuje fuel_type, liters, amount, distance_km, valid_intervals, excluded_intervals, consumption_l_100km a purchase_cost_czk_100km; litry/částka zde patří pouze platným měřicím intervalům. Stejnojmenné dvě globální poměrové hodnoty jsou null při různých skupinách paliv nebo bez platné vzdálenosti.

`comparison` je null nebo `{standard,difference_l_100km,difference_percent,methodology,source,source_note}` pouze při explicitním jednom autě s kladnou normou a jednou skupinou odpovídajícího paliva. `coverage` obsahuje valid_intervals, excluded_intervals, distance_km, start_date/end_date platných hranic nebo null, reasons s code/count a vehicles s vehicle_id/name/status/reasons/history_revision/missing_odometer_ids/open_record_ids a intervalovými součty. Varování missing_odometer_ids se vztahuje k celé načtené historii, ne jen nákupnímu filtru.

`charts.purchases` je vyplněná řada skupin `{date,amount,liters,count,unit_price}`; prázdná skupina má částku/litry/počet 0 a cenu null. Týdenní date je pondělí (může být před začátkem filtru), ale skupina obsahuje jen nákupy uvnitř filtru. Výchozí group_by je day do 60 dnů, week do 366 dnů, jinak month. Více než 5 000 skupin vrací 400 s vysvětlením. `charts.consumption` je chronologický seznam platných i vyloučených kandidátů s null hodnotou u neplatných. `recent_refuelings` obsahuje posledních nejvýše 5 nákupů ve filtru s vehicle_name/vehicle_id a podklady záznamu.

Interval obsahuje vehicle_id, start_id/end_id, start_date/end_date, start_odometer_km/end_odometer_km, liters/amount (nákupy po kotvě), distance_km, fuel_type, status, reasons, warnings, oba poměry, crosses_period_start, assignment_rule/explanation a record_ids. Detail navíc period, history_revision a records (id/date/day_sequence/liters/total_amount/fuel_type/odometer_km/is_full_tank/break_before/used_for_totals). První záznam je počáteční kotva s used_for_totals=false. Vyloučené kandidáty nikdy neředit do váženého součtu; neúplné údaje neodhadovat. Poměry mají 6 desetinných míst, částky 2, litry 3 jako řetězce. Odpovědi jsou private,no-store.
