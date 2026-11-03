# Fáze 8 – konkrétní specifikace rozšíření

Uživatel 3. 11. 2026 výslovně požádal o všechna rozšíření a pověřil návrhem specifikace. Tento dokument určuje realizovaný rozsah; samotná existence návrhu neznamená hotovou funkci. Žádný GitHub push, produkční zásah ani cloudové OCR není povoleno.

## 8A – VIN a fotografie

VIN se dohledává výslovným tlačítkem, pouze přes backend a oficiální RSV endpoint. Bez nakonfigurovaného klíče je funkce nedostupná, ruční formulář zůstává použitelný. Návrh a raw odpověď jsou neveřejné DB záznamy; uživatel vybírá jednotlivé změny, rok první registrace není rok výroby a nejednoznačný výkon/spotřeba nejsou číslo. Při uložení se zaznamená skutečně přijatá část návrhu. Autorizace se opakuje po externím volání; expirace návrhu 24 h. Limit 5/účet/min a 20/klíč/min, žádné automatické retry.

Po potvrzeném VIN lze pro uložené auto hledat nejvýše 3 fotografie podle potvrzené značky/modelu. Commons nikdy nedostává VIN, RZ ani údaje účtu. Povolené jsou pouze JPEG/PNG, pevné oficiální hosty bez redirectů, limit 5 MiB/12 MP. Licence CC0, CC BY 4.0 a CC BY-SA 4.0 musí mít úplná metadata včetně autora a zdroje. Uživatel výslovně potvrdí model/generaci/karoserii; algoritmus negarantuje shodu. Bez shody zůstává ikona. Stažený obrázek, očištěný náhled a původ/licence jsou v DB, podávané pouze s právy k vozidlu, nikdy hotlink. Karta/detail uvádí ilustrační povahu a atribuci. Změna značky/modelu/VIN zneplatní dřívější potvrzení shody.

## 8B – OCR

Pouze existující autorizovaná JPEG/PNG účtenka. Lokální Tesseract, pevná verze a zamčená data eng+ces, bezpečný pracovní obrázek, konečný čas/CPU/paměť/výstup a nejvýše 2 současná zpracování. Žádné síťové odesílání ani fronta nové služby. Výsledek v DB obsahuje engine/modely, raw text, jistoty a návrhy data/litrů/ceny/částky/tachometru/stanice. Uživatel vybírá pole a poté ukládá standardní editaci s ETag/Decimal/varováními. Příloha zůstává beze změn. Výsledek pro jiný hash/verzi účtenky je neaktuální a nelze jej použít. Bez enginu nebo při timeoutu zůstává ruční editace.

## 8C – servis, STK, pojištění a připomínky

Společný modul událostí vozidla s explicitním druhem SERVICE, INSPECTION, INSURANCE, REMINDER, ENERGY. Pole: název, datum, poznámka, částka CZK (Decimal 2 místa), tachometr, další datum/km, předstih dnů/km a uzavření. Servis je skutečný minulý výkon; STK/pojištění evidují datum a platnost, případně dodavatele/číslo smlouvy v soukromé poznámce. Nevytváří se právní výklad platnosti ani automatické propojení s úřady/pojišťovnami. Přílohy servisních faktur/PDF nejsou v této podetapě, existující účtenky tankování zůstávají zachované.

VIEWER čte, CONTRIBUTOR vytváří a upravuje vlastní aktivní události, OWNER/ADMIN spravují vše včetně archivované historie a mazání. Cizí UUID vrací 404. Zápisy mají ETag a idempotency key, audit neobsahuje dokumenty. Sdílené auto má jedinou historii.

Připomínky jsou pouze uvnitř aplikace, bez e-mailu/push/SMS a bez externího scheduleru. Termín je opožděný při překročení data nebo dosažení známého tachometru, blížící se dle zadaného předstihu (výchozí 30 dní/1000 km). Použije se poslední datovaný známý odečet, ne odhad. Neznámé km se označí. Uzavřené události a archivovaná auta se nepřipomínají. Všechny seznamy/počty/součty respektují práva; události se nepromítají do nákupů paliva nebo plná–plná.

## 8D – CNG a elektřina

Primární paliva CNG a ELECTRIC a samostatné nákupy ENERGY s jednotkou kg nebo kWh, množstvím Decimal (3 místa), částkou CZK a datem/km. Žádné převody na litry, žádný odhad plná–plná nebo směšování kg/kWh/l. Pro tyto primární pohony je litrové tankování odmítnuté a norma l/100 km vypnutá. Výdaje a množství jsou v samostatném přehledu po jednotkách; lze evidovat i doplňkové nabíjení hybridu. Nové jednotky nemění výsledky starých kapalných paliv.

## 8E – import

Výslovně vybrané existující vozidlo, CSV UTF-8, nejvýše 128 KiB/200 řádků. Import ruční historie tankování (datum, litry, částka/cena, km/plná, palivo, stanice, poznámka) podle zveřejněné šablony; nepřijímá vlastníky/role/URL ani binární přílohy. Náhled vypíše chyby a varování po řádcích a nic nezapíše do historie. Raw a normalizovaný návrh jsou v DB, soukromé pro autora a dostupné pouze při trvajícím přístupu k autu, expirace 24 h. Potvrzení je atomické, prochází běžnou validací/varováními a znovu ověřuje oprávnění. Opakování stejné potvrzené dávky nic nezdvojí. Nejde o univerzální import cizích XLSX/PDF bez mapování. Události/energie mají vlastní CSV šablonu a stejný potvrzovaný tok.

## 8F – offline zápisy

Výslovné tlačítko zařadí nový záznam do dočasné fronty; běžné Uložit při výpadku zachová původní ruční retry formuláře. Dočasná fronta nových tankování v paměti aktuálního přihlášeného okna, nejvýše 20 položek; žádná soukromá data v localStorage/IndexedDB/SW cache. Jasné označení neuloženo, možnost opravy/zahození a ručně spuštěná synchronizace po připojení. Ukládá se původní idempotency key, opakování po nejasné odpovědi neduplikuje záznam. Chyby/nová varování/odebrání přístupu zastaví položku a vyžadují zásah; serverová pravidla se neobcházejí. Logout, změna účtu a zavření/reload okna frontu zruší; beforeunload na neuložená data upozorní. Bez instalovaného/cachovaného veřejného shellu nelze poprvé spustit aplikaci bez sítě. Offline účtenky a editace existujících záznamů nejsou automaticky synchronizované.

## Akceptační matice

VIN: normalizace, nalezeno/nenalezeno/limit/neúplné pole/timeout/chybný klíč, ruční fallback, selektivní potvrzení a provenance. Fotografie: licence/atribuce, neshoda, SSRF/redirect/limity, odebrání přístupu a DB trvalost. OCR: skutečná syntetická česká účtenka a srovnání konfigurací, parse/Decimal/jistoty, timeout/limit, neaktuální výsledek, práva a nezměněný originál. Události: role/archivace/ETag/idempotence, termíny Praha a přesné součty po jednotkách. Import: suchý náhled, neplatné řádky, rollback celé dávky, varování/retry/IDOR. Offline: bez persistentního úložiště, logout purge, konflikt/varování a jediný serverový záznam po retry. Skutečné a fixture integrace se vykazují odděleně. Chybějící API klíč, Docker nebo nemožnost reálného externího testu se uvede jako omezení, nikoli úspěch.
