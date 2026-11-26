# Integrace implementované ve fázi 8

Podrobný rozsah: [PHASE_8_SPECIFICATION.md](PHASE_8_SPECIFICATION.md), skutečné testy a otevřené body: [PHASE_8.md](PHASE_8.md). Adaptéry jsou pouze na backendu a data v PostgreSQL. Selhání zdroje zachovává ruční formuláře.

## RSV – technické údaje podle VIN

Oficiální [dokumentace RSV v1.0](https://dataovozidlech.cz/data/RSV_Verejna_API_DK_v1_0.pdf) ověřena 3. 11. 2026: `GET https://api.dataovozidlech.cz/api/vehicletechnicaldata/v2?vin=...`, hlavička `API_KEY`, dokumentovaný limit 27/min. Naše sdílená klouzavá kvóta je konzervativně 20/min a 5/účet/min, bez retry. Správce nastavuje klíč ve Správě rodiny; šifrovaná hodnota v DB má přednost před výchozím `RSV_API_KEY` v prostředí. Vyhledávání podle TP/ORV není implementované.

Kontroluje se Status a shodný VIN, normalizuje se značka/model/objem a pouze jednoznačný číselný výkon a známé palivo. Více hodnot, nejednoznačná spotřeba a první registrace se nepovažují za výrobní rok/normu. Raw snapshot v DB, mapovací verze rsv-1, čas a skutečně přijatá pole uchovávají původ. Uživatel vybírá jednotlivá pole, následně uloží auto obvyklým formulářem. Návrh platí 24 h; změněná práva/identita potvrzení zablokují. Chybějící klíč vrací 503 a ruční fallback. Původní akceptace fáze 8 neměla klíč; 15. 11. 2026 již živý dotaz se stávajícím produkčním klíčem vrátil Status 1 a vozidlo; testy používají syntetické odpovědi včetně chyb a limitu vráceného s HTTP 200.

## Wikimedia Commons – ilustrační fotografie

Používá se oficiální [MediaWiki imageinfo](https://www.mediawiki.org/wiki/API:Imageinfo) a [pravidla User-Agent](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy). Nastavte `COMMONS_USER_AGENT` na identifikaci vlastní instalace s reálným kontaktem. Nepoužívejte cizí nebo smyšlený e-mail. Provozovatel musí respektovat [podmínky opětovného užití](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia).

Jen potvrzená značka/model z VIN, nejvýše 3 kandidáti, žádný VIN/RZ/uživatelská data. Hosty commons.wikimedia.org a upload.wikimedia.org jsou pevné; HTTPS bez redirectů, jen veřejné DNS, JPEG/PNG 5 MiB/12 MP. Metadata se čistí na text. Whitelist licence: CC0, CC BY 4.0, CC BY-SA 4.0; bez licence/zdroje/autora se návrh nepoužije. Uloží se autor, licence a odkaz, zdrojová stránka, credit/attribution, zdrojový čas/SHA1 a SHA256 staženého obsahu, údaje o úpravě náhledu. Originál a náhled jsou soukromé DB bytea. Karta/detail mají označení ilustrační fotografie, autora, licenční a zdrojový odkaz a atribuci, odkazy podtržené pro přístupnost.

Uživatel výslovně potvrdí model/generaci/karoserii; automatická přesnost není garantovaná. Změna identity auta zneplatní foto a staré potvrzení. Bez použitelných návrhů zůstává ikona. Veřejný metadata endpoint byl skutečně sondován; celý autorizovaný aplikační průchod kvůli chybějícímu RSV klíči a kontaktní konfiguraci ověřený není. E2E fotografie jsou vlastní syntetické obrázky, nikoli důkaz živého vyhledání.

## Lokální OCR

[Tesseract 5.5.4](https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.4), [ces/eng tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast), PSM 6 a OEM 1. `infra/ocr/dependencies.lock.json` zamyká tarball a modely SHA-256, modelový commit i Debian snapshot 20261103T000000Z. Docker sestavuje engine v odděleném stage, runtime dostává jen potřebné knihovny/modely. Přesná verze a modelové hashe se kontrolují před spuštěním. Nativně lze použít Tesseract 5.5.4 a `python3 infra/ocr/install_models.py`; binární cestu případně nastavte `OCR_BINARY`.

Jen již uložená autorizovaná JPEG/PNG účtenka; bez cloudu. Rozpoznání vrací raw text a návrhy data/litrů/ceny/částky/km/stanice s jistotou enginu, nikoli zárukou správnosti. Nejednoznačné hodnoty se vynechají; záměna l/I/1 má sníženou jistotu. Výsledek obsahuje hash/verzi původní přílohy. Výběr jednotlivých polí a následné standardní uložení vynucují Decimal, varování a ETag; starý výsledek se odmítne.

15 s wall time, CPU 10 s, na macOS RSS dohled 512 MiB na macOS, Linux AS 1 GiB, výstup max. 2 MiB a nejvýše dva souběžné sloty; žádné automatické retry. Soukromý pomocný PNG se uklidí. Linux resource limity/image čekají na běhové ověření, macOS engine byl skutečně spuštěn. Srovnání PSM 6/11 na vlastní syntetické české účtence rozpoznalo u obou 6/6 očekávaných polí; není to měření přesnosti na reálných účtenkách. Při selhání zůstává ruční editace/originál.


Nasazení 6. 11. 2026: historický zmrazený Debian snapshot v linuxovém buildu nahradily oficiální podepsané Bookworm a Bookworm-security repozitáře kvůli nedostupnému stahování snapshot balíčků. Základní image zůstává připnutý digestem a zdroj Tesseract/modely mají stejné SHA-256; tranzitivní systémové knihovny získávají aktuální opravy Bookworm. Starší tvrzení o plně zmrazených OS balíčcích se tímto zpřesňuje.


## Vlastní fotografie auta

Nezávisle na Commons a VIN lze v detailu auta nahrát vlastní JPEG/PNG (10 MiB, 24 MP). Ukládá se jen očištěný JPEG nejvýše 1600 × 1600 px bez EXIF do DB; předchozí snímek se nahradí. Správce/vlastník nahrává, každý oprávněný čtenář auta vidí snímek. Odebrání je dostupné v témže panelu. Fotografie se objeví i v rodinné garáži, odkud název auta vede na jeho detail. Commons ilustrace v garáži zachovávají atribuci a licenční/zdrojové odkazy.

## Oprava čtení čísel účtenek – 15. 11. 2026

Parser nyní přijímá mezery tisíců v celkové částce (i nezalomitelné), celý popisek „Celkem k úhradě“ a množství za názvem paliva včetně oktanového čísla. U palivového řádku umí rozpoznat cenu za litr, pokud násobení Decimal souhlasí s částkou řádku do 0,01 Kč. Záměnu jednotky l za číslici 1 přijme pouze při této číselné kontrole a se sníženou jistotou, nikoli jako dodatečnou desetinnou číslici. Hodnoty DPH, neplatné skupiny číslic a konfliktní množství/částky se nepřebírají jako jistý výsledek. Návrhy stále vyžadují uživatelskou kontrolu.

Na obrázku dodaném uživatelem bylo skutečně spuštěno lokální Tesseract 5.5.4 se zamčenými ces+eng modely a dosavadním PSM 6. Původní výstup neměl litry a celkovou částku zkrátil na 1. Po opravě stejný obrázek vrací datum 2025-01-17, litry 42.37, cenu 36.90 a celkovou částku 1563.45. Obrázek ani úplný OCR přepis se nepřidávají do repozitáře; regresní testy obsahují pouze syntetické řádky bez osobních údajů.

### Nasazení a skutečné ověření OCR

Oprava je zveřejněná v commitech 86cc735 a a8bafc2 a nasazená jako backend 0.9.5 ve stávajícím stacku na DOCKER01. Frontend je obsahově nezměněný, pouze přetagovaný; PostgreSQL zůstává 0.9.0 a všechny služby jsou healthy. Žádné migrace ani nové závislosti. Před aktualizací vznikla šifrovaná záloha v ignorovaném souboru `.runtime/production-backup-20261115/tanklog-before-ocr-numbers.dump.age` se stávající soukromou identitou. Kontrolní hashe stávajících aplikačních dat jsou shodné.

Skutečné výsledky: celá sada 269 backendových testů prošla; po doplnění podpory slovní jednotky litru prošlo dalších 21 cílených regresí (včetně všech 13 nových případů). Ruff, formátování, Gitleaks nad zveřejňovaným patchem, Compose config a serverový build/runtime prošly. Frontend se neměnil a jeho testy nebyly znovu spouštěny.

Dodaný ilustrativní obrázek byl skutečně zpracován také linuxovým Tesseractem v nově nasazeném backendu se zamčenými modely a původním PSM 6. Výsledky byly programově ověřené: datum 2025-01-17, litry 42.37, cena za litr 36.90, částka 1563.45. Dočasný obrazový obsah byl po testu odstraněn; nevzniklo testovací tankování, účet ani návrh účtenky. Test neodesílal obrázek žádnému externímu OCR. Jediný ilustrativní snímek nedokládá přesnost všech typů účtenek; nejednoznačné návrhy se nadále potvrzují ručně.

Dříve uložené výsledky OCR se automaticky nepřepisují. V rozpracované rodinné účtence použijte **Přečíst znovu**, u uloženého tankování v podrobném rozhraní **Rozpoznat účtenku** a následně potvrďte vybraná pole.

## OCR paliva a názvu stanice – 15. 11. 2026

Návrhy zahrnují fuel_type z palivového řádku nebo explicitního označení paliva: benzín/Natural → PETROL, nafta/Diesel → DIESEL, LPG/autoplyn → LPG, ethanol/E85 → ETHANOL. Pouhý seznam paliv v reklamě se nepřebírá; různé typy z více položek se neodhadují jako jednoznačný druh.

Známé řetězce používají stávající station_code. Pro neznámou stanici se z hlavičky obchodníka s právní formou nebo explicitního názvu stanice nabídne station_custom_name a station_code OTHER. Názvy/adresy se nezískávají z internetu. Lokalita typu Praha 5 není zaměněna za název stanice. Více různých názvů vede k vynechání návrhu; známý řetězec má přednost před názvem provozovatele.

Rodinná kontrola účtenky nově předvyplní palivo, stanici i její vlastní název, otevře příslušné doplňující údaje a po uživatelském potvrzení je odešle stejnému API. Vše lze opravit. Při změně na známý řetězec se původní vlastní název neposílá, aby nedošlo ke konfliktu validace. Bez návrhu se používá primární palivo auta. Neshoda paliva nadále vyžaduje standardní potvrzení upozornění. Původní podrobný formulář podporuje stejné návrhy jednotlivých polí.

Na dodaném ilustrativním snímku lokální engine skutečně doplnil PETROL a název PetrolFlex (OTHER) při zachování data, litrů a cen. Obrázek není ve verzovaných souborech.

## Automatické čtení mobilních fotografií – 26. 11. 2026

Rodinný formulář po vyfocení nebo výběru fotky rovnou nahraje soukromý návrh a spustí čtení. Pokud je nutné vybrat auto, čtení počká na výběr. Uživatel kontroluje zjištěné údaje před uložením. Při prázdném výsledku formulář výslovně nabídne zopakování nebo ruční doplnění.

První průchod zachovává PSM 6 a rozlišení nejvýše 2000 px. Při chybějícím datu, litrech nebo částce následuje nejvýše jeden podrobnější průchod v PSM 4 do 3800 px. Oba sdílejí patnáctisekundový limit rozpoznávání. Neúspěšný druhý průchod ponechá první návrhy. Parser zpracovává doslovné uvozovky v TSV jako znak, aby se nesloučily sousední řádky. Rozdělené palivové tabulky bez čitelné jednotky předvyplní množství jen při jednoznačném souhlasu sloupce množství, druhu paliva, ceny a částky. Návrh má sníženou jistotu. Název stanice se při nejednoznačném textu vynechá.

Ověření nad jedinou skutečnou uloženou účtenkou běželo jen v paměti na aplikačním serveru. První průchod nenabídl použitelná pole. Upravené zpracování přečetlo datum, litry, celkovou částku a druh paliva. Název stanice spolehlivě neurčilo. Fotografie ani surový OCR výstup nejsou součástí repozitáře a ověření záznam neměnilo.
