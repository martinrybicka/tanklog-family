# Budoucí VIN a OCR integrace

Pouze návrh a průzkum, stav 2. 11. 2026. Fáze 0 nezakládá API účet, nepožaduje klíč, nevolá registr pro skutečné vozidlo a neinstaluje OCR.

## 1. Oficiální API Registru silničních vozidel

Oficiální portál [Data o vozidlech](https://dataovozidlech.cz/) zveřejňuje [dokumentaci Veřejná API Datové kostky RSV v1.0](https://dataovozidlech.cz/data/RSV_Verejna_API_DK_v1_0.pdf), datovanou 21. 1. 2025. Při průzkumu byla dostupná; nebyla ověřena funkčnost autentizovaného požadavku ani přislíbena aktuálnost provozních podmínek.

Dokumentovaný endpoint je `GET https://api.dataovozidlech.cz/api/vehicletechnicaldata/v2`. Používá parametry `vin`, `tp`, `orv`; kombinace se vyhodnocují současně. RZ/SPZ není mezi zdokumentovanými vyhledávacími parametry. Klíč se získává [registrací API](https://dataovozidlech.cz/registraceapi) a předává v HTTP hlavičce `API_KEY`. Dokument uvádí limit 27 požadavků za minutu na klíč. [Zdroj: oficiální API dokumentace, str. 4–5](https://dataovozidlech.cz/data/RSV_Verejna_API_DK_v1_0.pdf).

Příklad odpovědi obsahuje značku, typ/obchodní označení, palivo, objem motoru, výkon a registrační datumy. U spotřeby uvádí `SpotrebaMetodika` a `SpotrebaNa100Km`, včetně více hodnot v jednom řetězci; neprokazuje jejich univerzální význam nebo dostupnost přesné kombinované spotřeby. Datum první registrace nelze automaticky považovat za rok výroby. [Zdroj: oficiální API dokumentace, str. 6](https://dataovozidlech.cz/data/RSV_Verejna_API_DK_v1_0.pdf).

## 2. Návrh adaptéru pro fázi 8

Následující body jsou vlastní návrh TankLog, nikoli další zjištěné vlastnosti RSV:

- Backendový adaptér `VehicleDataProvider` oddělí HTTP klienta a mapování do návrhu údajů vozidla. Povolený cílový host je pevný; uživatel nemůže zadat libovolnou URL. API klíč je výhradně v backend env `RSV_API_KEY`.
- Lookup provádí pouze uživatel, který smí vytvářet/upravovat cílové auto; limit na účet i společný klíč. Konzervativní lokální rozpočet pod publikovaným limitem, timeout, omezené retry s backoff a zpracování limitu/chyby i v těle odpovědi. Nestavět úspěch pouze na HTTP 200.
- Návrh zobrazí porovnání starých a nových hodnot a uživatel výslovně vybere změny. Ruční údaje se automaticky nepřepíšou. Selhání registru nesmí zablokovat ruční formulář.
- Uchovat neveřejný původní payload, datum získání, zdroj, verzi mapování a vybraná potvrzená pole. Přidat samostatný model `VehicleDataSnapshot` až při realizaci; v MVP se taková data nevyrábějí.
- Nejasnou spotřebu uložit jako raw hodnotu a metodiku; bez ručního potvrzení nenastavovat normu. Výkon s otáčkami nebo několik hodnot oddělených lomítky nelze slepě převést na jedno číslo.
- VIN/raw odpovědi nepatří do veřejného logu. Cache a retenci určit až podle podmínek zdroje; nesdílet neveřejná data mezi účty bez autorizace.

Před realizací znovu ověřit poslední oficiální dokument, registraci, oprávnění použití a uchování dat, dostupné identifikátory, provozní limit a chybové stavy. S vlastním autorizovaným klíčem ověřit odpověď nalezeno/nenalezeno, chybějící pole, nejasné spotřeby, timeout a překročení limitu. Konkrétní SLA a dostupnost vyhledání podle SPZ v průzkumu prokázány nebyly.

## 3. Lokální OCR účtenek

Preferovaný směr je lokální engine za rozhraním `ReceiptRecognizer`; konkrétní engine a jeho verzi vybrat až po porovnání přesnosti na syntetických nebo uživatelem výslovně poskytnutých českých účtenkách. Nezavádět předem cloudové odesílání ani další trvale běžící službu.

Tok: autorizovaná existující příloha → validace a bezpečný pracovní náhled → izolované OCR s časovým/paměťovým limitem → návrhy polí a jejich jistota → kontrola uživatelem → běžná validovaná změna tankování. Originál zůstane zachován. OCR nesmí obcházet práva, Decimal validaci, povinné údaje ani CSRF.

Budoucí `ReceiptExtraction`: vazba na konkrétní verzi/hash přílohy, engine/verze, stav, raw text, strukturované návrhy, jistoty a čas. Po výměně účtenky starý návrh označit jako neaktuální. Uživatel vybírá jednotlivé návrhy, nejisté hodnoty jsou zřetelně označené. Rozpoznané datum mimo povolený rozsah, chybný součet nebo palivo vyvolá stejná pravidla jako ruční zadání.

UI v MVP zachová samostatnou oblast účtenky a editovatelná pole, ale nebude zobrazovat nefunkční tlačítko „Rozpoznat“. Pokud se později prokáže potřeba delšího zpracování, zavést samostatnou komponentu/frontu s konkrétním zdůvodněním. Offline rozpracované tankování a synchronizace jsou nezávislé rozšíření, nikoli automatický důsledek OCR nebo PWA.
