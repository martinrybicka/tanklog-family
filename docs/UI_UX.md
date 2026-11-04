# Návrh UI a UX

Návrh obrazovek a designového systému. Implementovány jsou přihlášení, profil, zabezpečení, administrace účtů a od fáze 2 vozidla/sdílení a od fáze 3 také tankování/historie/účtenky/XLSX; od fáze 4 také analytický dashboard a intervalové podklady. Dodatek uživatele z 2. 11. 2026 mění vizuální směr na **neutrální modrou, šedou a bílou**, s klidnou typografií a střídmým modrým akcentem. Žádné ilustrační grafy s vymyšlenými statistikami ve skutečném dashboardu.

## 1. Navigace a rozvržení

Desktop od 1024 px: levá navigace přibližně 232 px, logo TankLog, Přehled, Moje auta, Tankování, Nastavení; Administrace jen pro ADMIN, uživatelský panel dole. Obsah má max-width přibližně 1440 px a mění se podle prostoru. Nadpis stránky, filtr a hlavní akce jsou vždy čitelné bez plýtvání místem.

Mobil: horní titul/volba auta a dobře dosažitelná akce „Zadat tankování“, dolní navigace Přehled / Auta / Tankování / Více. Více obsahuje Nastavení, Profil a podle role Administraci. Primární tlačítko může být fixované nad spodní navigací s rezervou pro safe-area; nikdy nezakrývá poslední položky, klávesnici ani potvrzení formuláře. Tablet používá stejný obsah s vhodnou mřížkou, nikoli samostatný produkt.

Plánované frontendové cesty:

| Cesta | Obrazovka |
| --- | --- |
| `/prihlaseni` | Login, bez registrace |
| `/zmena-hesla` | Povinná změna po prvním dočasném přihlášení |
| `/` | Přehled |
| `/auta`, `/auta/nove`, `/auta/:id`, `/auta/:id/upravit` | Karty, založení a detail vozidla |
| `/tankovani`, `/tankovani/nove`, `/tankovani/:id` | Historie, rychlý formulář a detail/editace |
| `/nastaveni` | Profil, změna hesla, režim vzhledu |
| `/administrace/*` | Uživatelé, vozidla, sdílení, systém a audit |

Filtry historie/dashboardu v URL umožní návrat z detailu se zachováním období a auta. URL neobsahuje poznámky, hesla ani soukromé obrázky. Route guard zlepšuje UX; skutečná ochrana je vždy na API.

## 2. Tokeny a komponenty

| Token | Světlý režim | Tmavý režim |
| --- | --- | --- |
| Pozadí | `#F4F6F9` | `#101722` |
| Plocha karty | `#FFFFFF` | `#192333` |
| Základní text | `#243249` | `#EDF1F7` |
| Vedlejší text | `#58677B` | `#A7B2C3` |
| Primární akce | `#315FA3` s bílým textem | `#96B7ED` s textem `#18263A` |
| Oddělení ploch | `#DDE3EC` | `#35445B` |

Oddělovací linka není jediným indikátorem hranice ovládacího prvku; inputy a focus potřebují samostatný dostatečně kontrastní obrys. Varování má ikonu i text, ne jen barvu. Pro dokončený vizuál ověřit běžný text nejméně 4,5:1, velký text a důležité grafické prvky 3:1; testované kombinace tokenů nezaručují automaticky všechny stavy finálních komponent.

Typografie: lokálně servírované písmo s doloženou licencí nebo systémová sada, základ 16 px, line-height přibližně 1,5; tabulární číslice pro částky a tachometr. Stupnice mezer 4/8/12/16/24/32 px, karty s poloměrem 12–16 px a střídmým stínem. Texty nejsou verzálková drobná šedá dekorace.

Komponenty: AppShell, PageHeader, VehicleCard, MetricCard s vysvětlením podkladů, PeriodPicker, VehicleFilter, RefuelingForm, DecimalInput, MoneyInput, odlišný FullTankToggle, PermissionBadge, DataQualityBadge, ChartCard, ReceiptUploader, EmptyState, ErrorState a ConfirmDialog. Základ ze shadcn/ui, ikony výhradně konzistentně Lucide. Značky automobilů výchozí typografické + obecná ikona, bez načítání neoficiálních log.

## 3. Přehled

Orientační desktopový wireframe:

```text
┌──────────────┬──────────────────────────────────────────────────┐
│ TankLog      │ Přehled                     [+ Zadat tankování] │
│ Přehled      │ [Všechna auta ▾]  [‹] [Listopad 2026 ▾] [›]      │
│ Moje auta    │ [Zaplaceno] [Tankování] [Nakoupené l] [Kč/l]     │
│ Tankování    │ [Spotřeba + podklady] [Nákupní Kč/100 km + info] │
│ Nastavení    │ [Spotřeba v čase]       [Výdaje v čase]          │
│ Administrace │ [Cena paliva v čase]    [Poslední tankování]     │
└──────────────┴──────────────────────────────────────────────────┘
```

Na mobilu dvě nákupní karty v řádku, měřicí karty a grafy pod sebou. Výchozí měsíc a všechna přístupná auta včetně archivované historie. Ovladač období nabízí den, týden, měsíc, rok a vlastní rozsah; aktuální období má textový popis i datumy. Filtry se neztrácejí při návratu z detailu.

Nákupní a měřicí karty mají viditelně odlišné popisky podkladů. U spotřeby například „2 uzavřené intervaly · 1 100 km“ a odkaz „Jak se počítá“. Vysvětlení: „Spotřebu řadíme podle dne koncového tankování. Interval může začínat před vybraným obdobím.“ U Kč/100 km popis nákupního významu podle metodiky. Různá paliva mají samostatné hodnoty, nikoli jeden celkový průměr.

Grafy Recharts s tooltipem, popsanými osami/jednotkami a dostupnou tabulkovou alternativou. Chybějící měření zůstane mezerou, loading neukazuje smyšlená čísla. U souhrnu bez nákupů může být zaplaceno 0 Kč, ale spotřeba je „Nedostatek dat“. Normu zobrazit až po výběru konkrétního auta.

## 4. Rychlé zadání tankování

Nejkratší průchod: globální tlačítko → auto předvyplněné z právě zobrazeného auta, jinak z poslední lokální preference (jen ID po ověření aktuálního přístupu) → dnešní datum → litry → cena nebo celkem → plná nádrž a doporučený tachometr → uložit. Pokud existuje jen jedno aktivní auto, výběr je automatický. Při příchodu z globálního přehledu s více auty musí být vybrané auto výrazně vidět.

```text
Nové tankování                                [Zavřít]
[Škoda Octavia ▾]               [Dnes · 2. 11. 2026]
Litry *                 Cena za litr        Celkem
[42,350     l]          [38,90 Kč]           [1 647,00 Kč]
Tachometr (doporučeno)                      Plná nádrž?
[10 600    km]                              [Ne] [Ano]
[Další údaje ▾] Palivo, stanice, plátce, poznámka, mezera
[Přiložit účtenku – nepovinné]
[Uložit tankování]
```

Částka se při zadání litrů/ceny navrhne, lze ji přepsat; štítek „Přesná částka z účtenky“ objasní prioritu. Plná nádrž se nepamatuje jako automatické ano. Tachometr může zůstat prázdný: krátké sdělení „Tankování uložíme. Tento údaj může chybět pro výpočet spotřeby.“ Nezobrazovat technické názvy Decimal nebo API.

Pokud ve dni existují další záznamy, ukázat „Toto je 2. tankování daného dne“ a možnost upravit vlastní pozici. Pokud hodnota km koliduje, neodhadovat správné pořadí potichu. Varování seskupit do jednoho srozumitelného potvrzení, které nezastíní skutečnou chybu vstupu. Přerušení evidence v dalších údajích vysvětlit „Od minulého záznamu chybí tankování nebo došlo k odčerpání paliva“.

Číselná klávesnice na mobilu (`inputmode=decimal/numeric`), podpora čárky, správný focus a Enter. Během odesílání zabránit dvojímu kliknutí; retry stejného nákupu drží idempotency klíč. Po úspěchu potvrzení a odkaz na detail. Nejdříve uložit záznam, poté nahrát účtenku; selhání obrázku nabídne opakování u stejného záznamu. Při síťové chybě zachovat rozepsaný formulář v paměti aktuální stránky; offline úložiště a automatická synchronizace patří až do fáze 8.

Cíl 15–30 sekund ověřit s uloženým autem, bez focení účtenky a bez neobvyklých varování. Zapsat skutečně naměřené časy při uživatelském průchodu ve fázi 5; jde o cíl, ne nyní ověřenou vlastnost.

## 5. Vozidla a historie

Karta auta: typografická značka/ikona, název, značka/model, RZ pokud vyplněná, palivo, stav, vlastní/sdílené a role. Akce „Detail“ a podle práva „Zadat tankování“. Archivované na samostatném přepínači, zachované v historických statistikách.

Formulář auta nejprve základní pole, technické parametry a norma v rozbalitelné části. VIN je volitelný ruční vstup; tlačítko pro jeho automatické načítání se v MVP nezobrazuje jako funkční. Zdroj a metodika normy mají viditelné vysvětlení. Více nádrží má upozornění, že je dostupná evidence výdajů bez výpočtu spotřeby.

Detail auta: hlavička s rolí, základní údaje, statistiky a historie. Záložky Přehled / Tankování / Údaje; správce navíc odkaz na sdílení. Historie má desktopovou tabulku a mobilní položky datum–částka–litry–tachometr se štítkem plná/částečná a neúplnost. Filtry na mobilu v panelu s počtem aktivních filtrů a akcí vymazat. Export má popis „Exportovat vyfiltrovaná data“.

Detail tankování zobrazuje autora, plátce, poslední úpravu, obrázek s autorizovaným náhledem a čitelné důvody kvality dat. Mazání jen podle práv, v dialogu s datem/autem/částkou a sdělením, že se změní statistiky; po smazání návrat do zachovaného filtru. Contributor nevidí akci smazat.

## 6. Administrace a nastavení

Správa uživatelů: seznam, vytvoření, aktivace/deaktivace, změna role a reset. Dočasné heslo se zobrazí jednou v konkrétním potvrzeném výsledku, bez ukládání v historii prohlížeče. UI říká, že ho správce musí bezpečně předat. Povinná změna hesla přesměruje na samostatný formulář a nesmí zpřístupnit jiný obsah přes přímou URL.

Sdílení: vybrat jediné existující auto → vlastníka → seznam grantů → přidat aktivního uživatele a roli. Stručné vysvětlení VIEWER/CONTRIBUTOR a zpřístupnění celé historie včetně účtenek. Převod vlastníka má výraznou informaci, zda předchozí vlastník ztratí přístup nebo dostane nový grant. Poslední ADMIN má ochranu s konkrétním vysvětlením.

Nastavení: vlastní zobrazované jméno, kontakt, změna hesla a systémový/světlý/tmavý vzhled. Preferenci vzhledu ukládat pouze do profilu v DB, společně pro všechna zařízení. Před přihlášením se nepoužívá uložená lokální preference. Cookies nesou jen identifikátor přihlášení/CSRF, žádná osobní data nebo nastavení. Smazání cookies vyžádá nové přihlášení, uložený profil, motiv a budoucí historie se zachovají.

## 7. Stavy a přístupnost

| Stav | Chování |
| --- | --- |
| Žádné auto | „Přidejte své první auto“ a příslušná akce |
| Žádné tankování | „Zatím tu není žádné tankování“; akce dle role |
| Filtr bez výsledků | Uvést aktivní filtry a nabídnout vymazání |
| Chybějící spotřeba | Konkrétní důvod a odkaz na plné nádrže / opravu historie |
| Načítání | Skeleton respektující reduced motion, bez skákání layoutu |
| Síťová chyba | Český text, zachovaný formulář a znovu zkusit; ověřit výsledek odeslání před novým nákupem |
| Stará verze při editaci | Vysvětlit souběžnou změnu a nabídnout načtení aktuálního záznamu, nepřepsat potichu |
| Zaniklá session | Přihlášení a vyčištění soukromé cache; neukládat heslo ani formulář do URL |
| Odebraný přístup | „K tomuto záznamu už nemáte přístup“, bezpečný návrat |

Každý input má label a čitelnou chybu napojenou přes `aria-describedby`; jednotka není náhradou názvu. Min. dotykové cíle 44×44 px, výrazný focus, logické tab pořadí, skip-link a landmarky. Dialogy mají focus trap, Escape a návrat focusu na spouštěč. Akce nesmějí být dostupné jen přes hover, stav se nevyjadřuje pouze barvou. Ověřit zoom 200 %, šířky 360/390/768/1024/1440 px, VoiceOver nebo NVDA, kontrasty a klávesnici v obou motivech.

## 8. Dostupné obrazovky fáze 2

Moje auta nabízí stránkované karty a stav active/archived/all v URL. ADMIN má navíc Všechna vozidla a sdílení (`/administrace/vozidla`). Detail obsahuje technické údaje a skutečnou roli, podle práv editaci a potvrzenou archivaci/obnovení. Ve fázi 2 byly historie a spotřeba označené jako budoucí funkce, bez falešných statistik; skutečné obrazovky vznikly ve fázích 3–4. Administrační sdílení je na detailu vozidla; nabízí hledání/stránkování aktivních účtů, granty, změnu rolí, potvrzené odebrání a převod s aktuálním heslem. Konflikt ETag zachová formulář a nabídne načtení aktuálních údajů; nezapisuje automaticky novou verzí přes cizí změny.

Karta sdíleného auta rozlišuje Čtenář/Přispěvatel, vlastní auto a administrátorský přístup. Technické údaje a norma jsou v rozbalitelné oblasti formuláře. Podporuje se desetinná čárka; API dostává přesné řetězce s tečkou. Neznámá norma je prázdná/null. Postranní panel se na nižším desktopu posouvá, aby rozšířená navigace nezablokovala odhlášení. Motivy a paleta z fáze 1 zůstávají. Ilustrační fotografie budou až součástí VIN integrace podle INTEGRATIONS.md.

## 9. Dostupné obrazovky fáze 3

/tankovani, /tankovani/nove, /tankovani/:id a /tankovani/:id/upravit jsou funkční. Karty i detail auta mají akci podle práva, globální navigace nabízí zadání. Formulář předvyplní serverový pražský den a palivo z vybraného auta; plná nádrž je výchozí ne. Částka z účtenky má přednost, návrh je přesně vypočtený z litrů a ceny. Volitelný tachometr se nepřepisuje odhadem. Další údaje obsahují plátce, stanici, poznámku, pořadí a mezeru v evidenci. Varování mají jeden potvrzovací dialog se skutečnými kódy serveru; nevalidní data nelze potvrdit.

Po uložení vede detail na samostatný upload. Chyba přílohy jasně říká, že tankování už existuje; opakování jde k témuž záznamu. Detail ukazuje soukromý náhled, stažení originálu a podle práva náhradu/smazání. Historie má desktopovou tabulku a mobilní seznam; filtry a řazení zůstávají v URL při detailu/editaci/mazání. Export používá celý filtr, ne jen stránku. Celodenní pořadí může měnit OWNER/ADMIN, vlastní pozici přispěvatel v editaci. Dialogy vracejí focus na původní ovladač nebo hlavní obsah, pokud byl ovladač odstraněn.

Ve fázi 3 byly statistiky ještě budoucí. Fáze 4 nyní přidává na detail auta odkaz Statistiky a spotřeba. Plný audit přístupnosti a měření rychlosti podle fáze 5 se nepředstírá jako dokončený.

## 10. Dostupné obrazovky fáze 4

Přehled `/` zachovává osobní uvítání a nahrazuje původní úvodní karty skutečným dashboardem. Výběr auta (včetně archivovaných) a období je v URL. `/auta/:id/statistiky` má shodné statistiky konkrétního auta, `/auta/:id/intervaly` stránkovanou tabulku a `/auta/:id/intervaly/detail?start_id=…&end_id=…` aktuální podklady. Všechny odkazy zachovávají analytické období; návrat k opravě otevře existující detail tankování.

Výchozí je měsíc podle pražského data serveru. Ovladače mají den/týden/měsíc/rok/vlastní, od–do, explicitní Použít období a šipky předchozí/následující; vlastní rozsah se posouvá stejně dlouhý. Nákupní součty, vážená realizovaná cena a měření jsou oddělené. Chybějící hodnota je text Nedostatek dat, skutečná nulová částka je 0,00. Spotřeba je oddělená podle paliva, srovnání normy má metodiku/zdroj a je jen pro explicitní auto.

Pokrytí ukazuje km, platné/vyřazené intervaly, datumové hranice a rozbalitelné důvody/opravu pro každé auto. Grafy výdajů a vážené ceny mají seskupení den/týden/měsíc a jednotky Kč/Kč/l; spotřební graf je pro každé auto/palivo zvlášť v l/100 km s mezerami místo neplatných bodů. Každý graf má rozbalitelnou tabulku. Tabulka podkladů označuje počáteční kotvu mimo filtr i její nezapočtený nákup. Na mobilu jsou karty pod sebou a široké podklady mají vlastní vodorovný posuv, nikoli přesah stránky. Modrošedá/bílá paleta i DB nastavení motivu zůstávají; fáze 5 přidává automatické a dílčí ruční ověření přístupnosti podle PHASE_5.md.

## 11. Dostupné úpravy fáze 5

Tablet do 1023 px má spodní navigaci a obsah přes celou šířku. Akce mají alespoň 44 px a bezpečné spodní okraje. Odhlášení se přesunulo do běžného toku pod obsah místo plovoucího tlačítka překrývajícího řádky. Nadpisy a akce se mohou zalamovat; široké tabulky mají vlastní posuv. Globální Zadat tankování předvyplní právě vybrané auto z cesty/filtru, bez prohlížečové preference.

Změna cesty aktualizuje document.title a přesune focus na hlavní obsah; dialog nadále drží focus a vrací ho. Chyby i nápovědy Field mají explicitní vazbu aria-describedby a vadná pole aria-invalid. Login má vlastní h1 a dekorativní příběh h2; popisek loga je odvozen z viditelného textu. Motiv před přihlášením respektuje zařízení, po přihlášení uložený DB profil. Reduced motion vypíná animace a přechody. Grafy zachovávají tabulkové alternativy.

Nastavení má informace o instalaci aplikace a případné podporované tlačítko prohlížeče. Offline status vysvětluje nutnost serveru a dočasnost rozepsaných údajů. Při offline navigaci se zobrazí obecná veřejná stránka s odkazem Zkusit připojení znovu. Aktualizace rozhraní nenutí reload neuloženého formuláře bez potvrzení. ErrorBoundary nabízí obnovu a vysvětlení, že uložená data zůstávají na serveru.

Ověřeno axe pro WCAG 2 A/AA a 2.1 A/AA na loginu, chybách, dashboardu, autech, formuláři auta, historii, tankování, nastavení, účtech a dialogu v obou motivech a desktop/mobil. Šířky 360/390/768/1024/1440 a reflow při 720 CSS px odpovídajících 1440/200 % prošly. Ručně přes klávesnici prošlo prázdné přihlášení s návratem focusu a AX zobrazením chyb. Skutečný zoom a poslech VoiceOver nebyly dokončené kvůli zablokování nativního browser ovládání; neoznačují se za ověřené.

Mobilní asistovaný průchod: uložené auto a serverové datum, 42,350 l, 38,90 Kč/l, 10 000 km, částečná nádrž, uložit → detail 1 647,42 Kč; 7,298 s od prvního vstupu po zobrazení detailu. Nezahrnuje volbu auta, přihlášení ani účtenku. Je rychlejší díky asistovanému vyplňování; není to měření člověka pro cíl 15–30 s. Předvyplnění auta a odstranění překryvu jsou provedené UX opravy, reprezentativní uživatelský test zůstává otevřený. Celkové omezení akceptace je v PHASE_5.md.

## Fáze 8 – nové obrazovky a potvrzení

Neutrální modrá/šedá/bílá paleta a oba motivy zůstávají. Detail auta přidává ilustrační foto s textovou atribucí, odkazy na servis/energii a import. VIN/OCR návrhy mají checkbox pro každé pole a explicitní použití; ruční formulář zůstává dostupný. Údaje z nejistého zdroje se netváří jako jistota.

Události mají jasný druh, datum/km, částku, případný další termín/předstih a uzavření; přehled připomínek vysvětluje známý odečet. Energie uvádí kg/kWh odděleně. CSV náhled zobrazuje každý řádek, chyby a potvrzovaná varování před zápisem, posuvnou tabulku lze ovládat klávesnicí. Offline obrazovka zřetelně říká „neuloženo“, upozorňuje na ztrátu při zavření/reloadu, nabízí opravu, zahození a ruční synchronizaci. Nové funkce jsou dostupné i v mobilní navigaci.

## Rodinné rozhraní – nové zadání 4. 11. 2026

Pozdější pokyn výslovně povoluje modernější grafiku, jemné modrofialové přechody a pastelové barevné akcenty. Bílé karty, klidné pozadí, velké akční tlačítko, konzistentní Lucide ikony a vlastní jednoduchá SVG ilustrace. Bez externích grafických/fontových služeb. Souhrny jsou skutečná data; dekorativní auto neslouží jako identifikace konkrétního vozidla.

Domů / Přidat účtenku / Historie, na mobilu tři stálé spodní položky. Účet a odhlášení v horním uživatelském panelu; Správa rodiny jen ADMIN. Podrobná analytika, sdílení, VIN/servis a import jsou v samostatné plné části a správce k nim má odkazy. Zařízení ani cookies nenesou preference auta.

Účtenkový průvodce: zřetelné tři kroky, fotoaparát i samostatná volba existujícího souboru, ověřený soukromý náhled, předvyplněné auto/datum a rozpoznané návrhy. Před potvrzením se ukazují datum, litry a částka; km jsou nepovinné, plná nádrž není automatická. Volitelné další údaje se rozbalují. Ruční fallback je dostupný i bez fotografie/enginu. Úspěch zobrazí uloženou částku a historii; varování se nepotlačují. Foto a OCR podklady lze dokončit později, ruční neuložené úpravy se zatím nepřenášejí. Světlý/tmavý motiv a přístupnost se kontrolují skutečnými testy.
