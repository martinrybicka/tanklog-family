# Funkční specifikace

Stav: aplikační specifikace fází 1–5 a provozní doplňky fází 6–7, aktualizováno 3. 11. 2026. Účty, vozidla, sdílení, tankování, účtenky, XLSX, spotřeba a analytický dashboard jsou implementované; fáze 5 doplňuje responzivitu, přístupnost, PWA shell a bezpečnostní ověření; fáze 6 má od 3. 11. 2026 připravenou lokální část CI podle [CI.md](CI.md). GitHub/push/skutečný CI běh jsou podle zákazu uživatele neprovedené, fáze 7 má připravenou pouze lokální provozní část podle OPERATIONS.md; skutečné nasazení je zakázané a fáze 8 zůstává plán. Zásadní doplnění zadání jsou označena v [rozhodnutích](DECISIONS.md). Změny rozsahu vyžadují aktualizaci dokumentace.

## 1. Cíl a hranice první verze

TankLog umožní malé skupině uživatelů bezpečně spravovat auta, sdílet historii a evidovat nákupy paliva. Rozhraní je české, mobile-first, s podporou klávesnice, světlým i tmavým režimem a shodnými funkcemi na telefonu i desktopu.

Dodatek uživatele během fáze 1: **všechna trvalá aplikační data jsou v PostgreSQL**, včetně profilu, uživatelského nastavení a budoucích binárních účtenek/náhledů. Smazání cookies pouze odhlásí účet; po přihlášení na libovolném zařízení jsou uložené údaje stejné. Klientská paměť je jen dočasná cache, ne zdroj pravdy; localStorage, sessionStorage ani IndexedDB neuchovávají osobní data nebo preference. Neukládaný rozepsaný formulář není uloženým záznamem. Konfigurace a tajné hodnoty infrastruktury zůstávají v prostředí. Vzhled používá neutrální modré/šedé odstíny a bílé plochy.

První ucelené MVP vznikne dokončením fází 1–5. Obsahuje ruční zadání vozidel a tankování, soukromé obrázky účtenek, filtrování, XLSX, spotřebu, dashboard a administraci. VIN, OCR, servis, STK, pojištění, připomínky, import historie a offline zápisy patří do fáze 8. PWA základ ve fázi 5 znamená instalovatelné rozhraní; neznamená offline přístup k soukromým datům.

Navržené omezení MVP: CZK, kilometry a litry; paliva PETROL, DIESEL, LPG, ETHANOL a OTHER_LIQUID. CNG v kg a elektřina v kWh potřebují odlišný model jednotek a nebudou převáděny na litry. Více nádrží nebo souběžně používaná různá paliva nelze spolehlivě měřit jednou metodou plné nádrže. Takové auto lze evidovat pro výdaje, ale výpočet spotřeby bude vypnutý. Hybrid s jednou kapalnou nádrží může vykazovat pouze spotřebu kapalného paliva, bez závěru o celkové energetické účinnosti.

## 2. Účty a role

- Přihlášení uživatelským jménem a heslem, odhlášení, vlastní profil a změna hesla. Uživatelské jméno je po vytvoření neměnné a jedinečné bez ohledu na velikost písmen; e-mail je nepovinný kontaktní údaj, nikoli přihlašovací identita.
- Žádná veřejná registrace ani veřejný reset e-mailem. Administrátor vytvoří účet, vydá jednorázové dočasné heslo, deaktivuje nebo reaktivuje účet.
- Dočasné heslo platí nejvýše 24 hodin a po použití dovolí pouze nastavit nové heslo v omezené session. Proces a zneplatnění sessions popisuje [bezpečnost](SECURITY.md).
- ADMIN je systémová role spravující všechny objekty. USER má pouze přístup k vlastním a sdíleným vozidlům.
- OWNER je právě jeden vlastník na vozidle. VIEWER a CONTRIBUTOR jsou granty sdílení. Práva se nekopírují do jednotlivých tankování.
- CONTRIBUTOR přidává a upravuje vlastní tankování, ale podle navrženého konzervativního pravidla je nemaže. OWNER a ADMIN upravují a mažou všechna tankování vozidla. Sdílení i převod vlastnictví provádí pouze ADMIN. Úplná matice je v [SECURITY.md](SECURITY.md).

Odebráním sdílení končí i přístup k záznamům, které uživatel dříve sám vytvořil. Autorství samo není oprávněním k cizímu vozidlu. Nové sdílení zpřístupní celou historii včetně účtenek; omezení sdílení na období není součást MVP.

## 3. Vozidla

Povinné údaje: vlastní název, značka, model, primární palivo, počáteční stav tachometru; vlastník se nastaví z přihlášeného uživatele. Volitelné: rok výroby, RZ, VIN, objem motoru v cm³, výkon v kW, objem nádrže v litrech, normovaná spotřeba, zdroj, metodika a poznámka ke zdroji.

Normovaná spotřeba může chybět; nula ji nenahrazuje. Metodika: WLTP, NEDC, MANUFACTURER, USER_ESTIMATE nebo UNKNOWN. Srovnání se zobrazuje pouze pro konkrétní vozidlo se známým kladným údajem a s uvedením metodiky. Celkový průměr „normy“ různých aut nevytvářet.

Uživatel spravuje vlastní auta. Archivace zachová historii a čtení; zablokuje nové tankování, ale OWNER/ADMIN mohou opravovat historické záznamy. CONTRIBUTOR nemůže archivovaná data měnit. Obnovení auta provádí OWNER/ADMIN. Trvalé mazání auta s historií nebude v MVP veřejnou funkcí.

VIN se při vyplnění normalizuje na velká písmena; běžný formát 17 znaků bez I/O/Q. Historická nestandardní identifikace se zaznamená do poznámky, ne falešným VIN. Jedinečnost vyplněného VIN brání duplicitě stejného auta; případný konflikt vrátí obecné upozornění bez prozrazení jiného vlastníka. RZ není globálně jedinečná, může se měnit. Loga jen s doloženým oprávněním, výchozí zobrazení používá Lucide ikonu a typografii. Dodatek uživatele během fáze 2: při budoucím dohledání VIN (fáze 8) nabídnout ilustrační fotografii modelu z veřejného zdroje s ověřenou licencí, atribucí a označením ilustračního charakteru; obrázek, náhled i původ uložit do PostgreSQL. Přesný návrh je v INTEGRATIONS.md; ve fázi 2 zůstává ruční VIN bez integrace.

## 4. Tankování a validace

Povinné: přístupné aktivní auto, datum, kladné litry a alespoň jedno z polí cena za litr / celkem. Datum předvyplní server podle Europe/Prague; budoucí den se v MVP odmítne. Tachometr je volitelný nezáporný počet celých km. Plná nádrž je explicitní ano/ne, při novém formuláři výchozí ne.

Předvyplněné palivo z auta je opravitelné. Stanice je nepovinná: ORLEN, Shell, MOL, OMV, EuroOil, Tank ONO, Ostatní s vlastním názvem. Volitelná je poznámka (max. 2 000 znaků), plátce a jedna JPEG/PNG účtenka. Autor je vždy nastaven serverem, při úpravách zůstává původní; poslední editor se eviduje zvlášť. Plátce může být aktivní uživatel s přístupem k autu nebo krátký volný text. Jeho uvedení nemění oprávnění ani automaticky nedělí výdaje.

Litry mají nejvýše 3 desetinná místa, zadaná cena za litr nejvýše 4 a částka 2. Backend odmítá vyšší přesnost místo tichého zaokrouhlení vstupu. Při zadání litrů a ceny navrhne celkem zaokrouhlením HALF_UP na haléře. Přesná částka z účtenky má přednost. Při zadání jen částky se jednotková efektivní cena vypočte, nevydává se za cenu uvedenou na stojanu. Nulové placené tankování je povoleno pouze s výslovně zadanou nulovou částkou a potvrzením varování; záporné částky a vratky nejsou tankování.

Varování před uložením: nesoulad paliva, rozdíl částky proti součinu, překročení známého objemu nádrže, chybějící/klesající tachometr, tankování před počátečním stavem, podobný existující záznam a nejasné pořadí v rámci dne. Po potvrzení lze uložit historicky problematický nezáporný tachometr; dotčená spotřeba se nezobrazí jako platná. Backend znovu vyhodnocuje varování a požaduje potvrzení relevantních kódů. Potvrzení varování nikdy neobchází tvrdou validaci nebo oprávnění.

Více záznamů stejného dne má uložené pořadí `day_sequence`. Nový se nabídne na konec; uživatel potvrdí nebo upraví jeho pozici. Autor může změnit datum vlastního záznamu, ale přeuspořádání celého dne je vyhrazeno OWNER/ADMIN. Podrobnosti souběhu a opakovaných mobilních požadavků jsou v [modelu](DATA_MODEL.md) a [API](API.md).

JPEG/PNG maximálně 10 MiB a 24 megapixelů po dekódování. Odmítnout ostatní formáty včetně SVG, PDF, HEIC a animovaných obrázků. Zachovat původní přijatý obrázek soukromě jako binární obsah v DB; metadata včetně případné polohy jsou soukromou součástí originálu. Náhled bude bezpečně znovu zakódován bez EXIF a také uložen v DB. Nahrání neblokuje existenci tankování: po chybě přílohy nabídnout opakování bez vytvoření druhého tankování. Přílohy jsou implementované od fáze 3.

## 5. Historie a export

Historie přístupných vozidel má hledání v názvu auta, stanici a poznámce, filtr vozidla, období včetně obou krajních dnů, paliva a stanice. Řazení podle data/pořadí, částky, litrů nebo tachometru; stabilní sekundární řazení. Výchozí pořadí je od nejnovějších. Na desktopu tabulka, na mobilu čitelný seznam.

Exportuje se celá aktuálně vyfiltrovaná množina, nikoliv pouze stránka; výchozí limit 50 000 řádků, nad něj srozumitelná výzva ke zúžení. Použít stejnou filtrovací a autorizační funkci jako seznam. XLSX obsahuje typované datumy a čísla s českými zobrazovacími formáty, částky a jednotky, autora a plátce. Texty vždy vynutit jako text, včetně hodnot začínajících `=`, `+`, `-`, `@`, tabulátorem nebo novým řádkem. Žádné vzorce ani veřejné URL účtenek.

## 6. Dashboard a měření

Výchozí období je aktuální měsíc v Europe/Prague. Den, týden (pondělí–neděle), měsíc, rok a vlastní od–do. Šipky posouvají kalendářní období; u vlastního rozsahu stejně dlouhý počet dní. Výběr všech přístupných aut nebo jednoho; archivovaná jsou ve „všech“ zahrnuta, aby nezmizely historické výdaje. Volba archivovaných je v seznamu aut oddělená.

Nákupní karty: skutečně zaplaceno, počet tankování, nakoupené litry a realizovaná vážená cena `SUM(total_amount) / SUM(liters)`. Je to částka po slevách, nikoli prostý průměr zadaných jednotkových cen. Všechna dostupná auta se agregují přes jedinečná ID, ne přes násobící JOIN sdílení.

Měřicí karty: spotřeba ze součtu litrů a km platných uzavřených intervalů; nákupní náklady / 100 km ve stejných intervalech; srovnání s normou jednoho vozidla. Zobrazit počet intervalů, pokryté km, mezní datumy, vyloučené intervaly a důvody. Spotřeba v l/100 km napříč auty bude jen pro shodné palivo; při různých palivech samostatně po palivu, bez jednoho zavádějícího čísla.

Grafy: spotřeba (body na koncových datech intervalů), výdaje a vážená cena po dnech/týdnech/měsících podle zvoleného rozsahu. Volitelně podíly nákladů aut. Nedostupná spotřeba je mezera, ne nula. Detail intervalů ukáže použité záznamy i přesah před filtr. Metodika včetně chybějících tachometrů a předem navržených testů je závazně v [CONSUMPTION.md](CONSUMPTION.md).

## 7. Administrace

Sekce Uživatelé, Všechna vozidla, Sdílení, Systém a audit. Účty se deaktivují místo mazání. Nelze deaktivovat nebo zbavit role posledního aktivního ADMIN. Převod vlastnictví je atomický a zaznamenaný; předchozí vlastník standardně ztrácí přístup, pokud mu ADMIN zároveň výslovně neudělí grant. Deaktivace vlastníka ponechá vozidla i historii, ADMIN je může převést. Systémové informace nezobrazují tajné hodnoty nebo kompletní prostředí.

## 8. Kvalita a otevřené slabiny

| Nejednoznačnost / riziko | Navržené řešení |
| --- | --- |
| Datum bez času neřeší více nákupů za den | Výslovná pořadová pozice v rámci dne, opravitelnost s auditem |
| Chybějící tachometr neznamená chybějící palivo | Litry v mezilehlém záznamu započítat mezi známými plnými hranicemi, ukázat neúplnost |
| Nelze rozpoznat úplně vynechané tankování | Uživatel může označit záznam jako přerušení evidence; nepočítat přes tuto hranici |
| Spotřeba z nákupů nezjistí únik, odčerpání nebo jinou jízdu bez evidence | Uvést předpoklady metody a přerušit měření při známé mezeře |
| Nové ceny neoceňují přesně již spálené zásoby | Kartu označit jako nákupní náklady v intervalech; žádné tvrzení o přesné ceně spáleného paliva |
| Jednotky a více nádrží nejsou v původním modelu vyřešeny | Omezení kapalného paliva / jedné nádrže pro spotřebu; rozšíření později |
| Požadavek na mazání CONTRIBUTOR není určen | Navržená pouze editace vlastních záznamů; mazání OWNER/ADMIN |
| Sdílení zpřístupní citlivé účtenky a celou historii | Výslovně vysvětlit ADMIN při přidání přístupu |
| Deklarovaný hot reload nebo HTTPS nezaručí funkčnost | Ověřit Compose, prohlížeč, cookies a skutečné hlavičky samostatně v příslušné fázi |

Akceptace nefunkčních vlastností: použití od 360 px bez vodorovného posuvu celé stránky, klávesnicový průchod, kontrasty ověřené pro oba režimy, nulový přístup k cizím objektům v negativních testech a prokázaná obnova zálohy před produkcí. Konkrétní testy a podmínky předání jsou v [roadmapě](ROADMAP.md).

## 9. Upřesnění implementace fáze 3

Rozdíl částky proti součinu znamená jakoukoli odchylku od výsledku HALF_UP na haléře, nikoli procentní toleranci. Podobný záznam je stejné vozidlo/den/litry/částka. Každý další záznam stejného dne vyžaduje potvrzení pořadí; výchozí vložení je na konec, při editaci se bez změny data zachová pozice. Potvrzení kódů se vždy znovu vyhodnotí pod zámkem. Upozornění se také odvozují při čtení z aktuálních údajů, nejsou výsledkem měření spotřeby.

Aktivní plátce musí mít přístup k autu (vlastník, grant nebo systémový ADMIN); API volby vracejí jen ID/jméno. Historicky uložený plátce zůstává zachován i po ztrátě svého přístupu či deaktivaci, pokud se nemění. Plátcovství nikdy nezakládá oprávnění. Po smazání tankování se odstraní jeho účtenka, audit a záznam ochrany před duplicitou zůstanou. Expirace klíče po 24 h nedovolí automaticky založit druhý nákup; je nutné ověřit historii.

Ve fázi 3 byly připravené syntetické historie C05/C06/C14/C24 bez samotného výpočtu. Fáze 4 nyní implementuje celou matici C01–C34, čistou výpočetní službu, statistické API, intervalový detail a dashboard. Skutečné ověření a omezení uvádí PHASE_4.md.

## 10. Upřesnění implementace fáze 4

Dashboard na `/` a statistiky konkrétního auta zahrnují i archivovaná přístupná vozidla. Výchozí období je aktuální pražský měsíc; týden pondělí–neděle, vlastní rozsah včetně obou hranic. Předchozí/následující vlastní rozsah má stejný počet kalendářních dnů. Filtry jsou v URL, nikoli v cookies nebo klientském trvalém úložišti.

Spotřeba a nákupní Kč/100 km jsou vážené z platných intervalů a oddělené podle paliva; při více palivech je společná hodnota null. Nákupní součty zahrnují všechny nákupy skutečně v období, i neúplné. Pokrytí ukazuje platné/vyřazené intervaly, km, hranice, konkrétní důvody a odkazy na opravu. Plná nádrž bez km není hranice, ale její litry zůstávají v širším intervalu. Pokles km zablokuje dotčenou část historie až do opravy včetně již uzavřeného kandidáta podle C30. Norma se porovnává jen pro explicitně vybrané auto, kladnou normu a platné měření odpovídajícího paliva; vždy s metodikou a zdrojem.

Detail intervalu obsahuje všechny záznamy od kotvy po koncovou plnou, i kotvu před filtrem. Výslovně odlišuje nákup kotvy (nezapočtený) od nákupů v `(A, B]`. Po změně hranic původní dvojice ID vrátí 404. Vše se přepočítává nad aktuální DB historií s konzistentním snapshotem, bez uložených duplicit výsledků. Fáze 5/PWA ani VIN/OCR se tím nezahajují.

## 11. Upřesnění implementace fáze 5

PWA znamená instalovatelný veřejný shell a obecnou offline stránku, nikoli dostupnost osobních údajů bez serveru. V produkčním buildu jsou manifest, vlastní ikony 192/512/maskable/apple-touch a worker s pevnou veřejnou cache. Soukromé API ani dokumenty/účtenky se neukládají. Rozepsaný formulář při chybě spojení zůstane jen v paměti současného okna; reload ho zruší. Retry drží původní idempotency klíč. Novou verzi lze načíst s výslovným upozorněním na neuložené údaje.

Rozhraní reaguje na 360/390/768/1024/1440 px; tablet do 1023 px využívá spodní navigaci. Dotykové akce mají nejméně 44 px, odhlášení už není plovoucí překryv nad obsahem. Navigace přesouvá focus na hlavní obsah, dokument dostává název obrazovky. Field propojuje chyby i nápovědy s inputem/selectem/textarea. Veřejný login respektuje systémový motiv; uložená preference přihlášeného účtu se stále čte z DB. Přístupnost se automaticky kontroluje ve světlém i tmavém režimu, včetně dialogu a chyb.

Ověřené výsledky a neověřené části akceptace jsou v PHASE_5.md. Asistované mobilní měření 7,298 s není uživatelským testem člověka pro cíl 15–30 s. Skutečný nativní zoom 200 % a poslech VoiceOver zůstávají neověřené; automatický reflow a ruční klávesnice/AX byly ověřené. Běh Dockeru zůstává neověřený kvůli chybějícímu daemonu. Nasazení ani GitHub se tím neschvalují.

## Provozní doplněk fáze 6 (3. 11. 2026)

Příprava CI nemění aplikační funkce, API, datový model ani migrace. Verze aplikačního kontraktu zůstává v0.5.0. Workflow pouze kontroluje stávající lock soubory, testy, schema a build. Testovací prostředí používají vlastní syntetické databáze; žádná osobní data ani výsledky E2E se nenahrávají. GitHub private viditelnost a úspěšný běh na čistém Linux runneru zůstávají podmínkou plného dokončení fáze 6. Místní macOS ověření je nenahrazuje.

## Provozní doplněk fáze 7

API, datový model a verze kontraktu v0.5.0 se nemění. Záloha musí zahrnout celou transakčně konzistentní DB včetně originálů/náhledů účtenek a práv. Implementované nástroje šifrují custom dump s manifestem, ověřují kontrolní součty a odmítají obnovu přes existující DB. Nová produkční inicializace odděluje bootstrap a aplikační DB roli. Příprava scheduleru není spuštěná automatická off-host záloha; nativní obnova není Docker/provozní akceptace. Aktuální výsledky jsou v PHASE_7.md, vzdálené kroky jsou podmíněné konkrétním budoucím povolením.
