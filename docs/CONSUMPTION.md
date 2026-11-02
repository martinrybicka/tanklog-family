# Metodika spotřeby a předem připravené testy

Stav: závazný návrh algoritmu a testovacích očekávání pro budoucí implementaci. **Níže uvedené případy nejsou spuštěné jednotkové testy.** Jejich přepis do testů musí předcházet implementaci výpočetní služby ve fázi 4. Tvrdá validace vstupů a práva se testují již ve fázi 3.

## 1. Vstup a předpoklady

Metoda plná–plná předpokládá jednu nádrž, stejný druh kapalného paliva, srovnatelné naplnění, evidenci všech nákupů a žádné nezaznamenané odčerpání. Počáteční tachometr vozidla není počáteční plná nádrž. Servis přijímá celou historii jednoho vozidla seřazenou `(date ASC, day_sequence ASC)`; při nejedinečném pořadí je vstup chybný, nesmí náhodně rozhodnout UUID.

Každý vstup obsahuje ID, datum, pořadí, litry Decimal, skutečnou částku Decimal, palivo, nullable tachometr, plnou nádrž a `break_before`. Výstup má platné intervaly, vyloučené kandidáty s důvody, otevřený konec a upozornění na neúplné záznamy. Veřejné stavy:

- `VALID`: alespoň jeden platný uzavřený interval; případné problémy se uvádějí zvlášť.
- `INSUFFICIENT_DATA`: není žádný platný interval a chybí dvě použitelné hranice; UI „Nedostatek dat“.
- `INVALID_DATA`: známé chyby znemožňují výpočet; UI vysvětlí opravu.
- `UNSUPPORTED`: nevhodný režim vozidla/jednotek; výdaje zůstávají dostupné.

K dispozici jsou důvody `MISSING_ANCHOR`, `OPEN_INTERVAL`, `ZERO_DISTANCE`, `ODOMETER_DECREASE`, `BELOW_INITIAL_ODOMETER`, `HISTORY_GAP`, `MIXED_FUEL`, `MISSING_ODOMETER`, `UNSUPPORTED_MULTI_TANK` a `INVALID_ORDER`. Více důvodů lze vrátit současně. Chybějící hodnota je JSON `null`, nikdy 0, NaN nebo nekonečno.

## 2. Přesné pravidlo intervalů

1. Ověřit typy, jednotky, jednoznačné pořadí a režim vozidla. Nepoužívat float. Prázdná historie vrací nedostatek dat.
2. Projít celou historii a kontrolovat známé tachometry proti počátečnímu stavu a předchozímu známému odečtu. Chybějící odečet poslední známou hodnotu nemaže. Rovnost je přípustná na jednotlivém záznamu, ale měřicí interval potřebuje kladnou vzdálenost.
3. První plná nádrž se známým bezchybným tachometrem je kotva A. Její litry a částka se do následujícího intervalu nezapočtou. Nákupy před A zůstanou pouze ve výdajových statistikách.
4. Sbírat všechny záznamy po A až po další plnou nádrž se známým tachometrem B včetně. Částečný záznam bez tachometru přispívá litry a částkou; sám má upozornění na neúplnost. Plná nádrž bez tachometru nemůže být hranicí, ale její litry se rovněž neztratí.
5. Kandidát A→B musí mít `B.km > A.km`, žádnou chybu známých tachometrů, žádné `break_before` v rozsahu `(A, B]` a stejný druh paliva ve všech záznamech včetně A. Potom vzniká platný interval.
6. Po vyhodnocení se B stává další kotvou. Žádný nákup se nepoužije dvakrát: B uzavírá předchozí interval svými litry, v dalším slouží jen jako reference. Nulová vzdálenost zneplatní právě kandidáta, B může být novou kotvou.
7. Při prvním poklesu známého tachometru najít poslední plnou známou kotvu, která leží **přísně před předchozím známým odečtem**. Zablokovat všechny kandidáty začínající touto kotvou nebo později, až do konce historie. Pokud taková kotva neexistuje, není platné žádné měření. Tím se zneplatní i právě uzavřený interval, pokud zpětný odečet naznačuje chybné pořadí. Starší nedotčené intervaly končící v této kotvě zůstanou platné. Hodnota pod počátečním stavem zneplatní celé měření do opravy. Pozdější růst automaticky neprokazuje opravu nebo výměnu tachometru. Obnovení vyžaduje opravit historii/počáteční stav; podpora výměny tachometru se segmenty je budoucí rozšíření. Tato kontrola se provede před konečným přiznáním platnosti intervalům.
8. Přerušení evidence nebo smíšené palivo zneplatní příslušného kandidáta, nikoli nákupní součty. Nejbližší bezchybná plná známá hranice B může založit nové měření. `break_before` na A se týká minulého úseku, ne úseku po A.
9. Záznamy za poslední známou plnou nádrží jsou otevřený interval. Neodhadovat spotřebu z objemu nádrže, normy nebo posledního nákupu.

Zpětné přidání, editace, smazání, změna pořadí nebo počátečního tachometru vyvolá nový výpočet celé historie vozidla. Není dovoleno pouze přidat „poslední bod“ do uloženého grafu.

## 3. Vzorce a zaokrouhlení

```text
distance_km = B.odometer_km - A.odometer_km
liters = SUM(record.liters for record in (A, B])
amount = SUM(record.total_amount for record in (A, B])
consumption_l_100km = liters / distance_km * 100
purchase_cost_czk_100km = amount / distance_km * 100

weighted_consumption = SUM(valid_interval.liters) / SUM(valid_interval.distance_km) * 100
weighted_purchase_cost = SUM(valid_interval.amount) / SUM(valid_interval.distance_km) * 100
realized_purchase_unit_price = SUM(purchase.total_amount) / SUM(purchase.liters)
```

Interně Decimal s dostatečnou přesností (minimálně 28 platných číslic). Nezaokrouhlovat jednotlivé intervaly před agregací. API vypočtené poměry předá jako desetinný řetězec na 6 míst; UI spotřebu a Kč/100 km na 2 místa, litry až 3, peníze 2, `ROUND_HALF_UP`. Graf může převést již vypočtenou hodnotu na číslo pro polohu bodu; nesmí z floatů vytvářet účetní součty.

`purchase_cost_czk_100km` vyjadřuje **nákupní náklady na 100 km v měřicích intervalech**. Cena paliva nakoupeného na konci intervalu se nemusí shodovat s cenou skutečně spálených zásob. Bez evidence počátečních zásob a ocenění nejde o přesný provozní náklad spáleného paliva. UI to uvádí v popisu karty.

## 4. Časové filtry, vozidla a norma

Interval vzniká před aplikací období. Zařazuje se celý do období podle data B, i když A leží před začátkem období. Rozdělovat litry nebo km poměrem kalendářních dní není dovoleno. Detail odhalí přesah, použité nákupy, km a datumy. Výdaje a litry nakoupené v období se naopak filtrují přímo podle jednotlivých nákupů.

Průměr napříč vozidly se počítá až ze součtů autorizovaných intervalů; jedno vozidlo je v množině jednou. Různá paliva mají samostatné spotřeby, bez jediného celkového čísla. Nákupní výdaje lze sečíst společně v CZK. Vyloučená vozidla, počet intervalů a pokryté km patří do metadat odpovědi.

U konkrétního auta s normou > 0: rozdíl `actual - standard` v l/100 km a procento `(actual / standard - 1) * 100`. Zobrazit metodiku a zdroj; neprezentovat různé jízdní podmínky jako důkaz závady auta.

## 5. Testovací matice s očekáváními

Zápis `F(km; l; Kč)` znamená plnou nádrž, `P` částečnou, `?` chybějící tachometr. Pokud není uvedeno jinak, počáteční tachometr 0, stejné palivo a vzestupné datumy. Částky nepotřebné pro konkrétní případ lze nastavit konzistentně na 40 Kč/l.

| ID | Vstup / změna | Očekávaný výsledek |
| --- | --- | --- |
| C01 | Prázdná historie | INSUFFICIENT_DATA; 0 intervalů, spotřeba null |
| C02 | F(10000; 50) | Jediná kotva, spotřeba null |
| C03 | P(10000; 20), P(10400; 30) | Bez plných hranic, žádný interval |
| C04 | F(10000; 50), F(10600; 45) | 45 l / 600 km = 7,500000; první 50 l vyloučeno |
| C05 | F(10000; 50), P(10300; 20), F(10600; 25) | 45 l / 600 km = 7,500000 |
| C06 | F(10000; 50), P(?; 20), F(10600; 25) | 7,500000; prostřední záznam MISSING_ODOMETER, interval platný |
| C07 | F(10000; 50), F(?; 20), F(10600; 25) | Jeden širší interval 45 l / 600 km = 7,500000; prostřední plná není kotva |
| C08 | F(?; 50), F(10600; 25) | Bez počáteční známé plné hranice, spotřeba null |
| C09 | F(10000; 50), P(10300; 20) | OPEN_INTERVAL; 20 l patří do nákupů, spotřeba null |
| C10 | F(10000; 50), F(10000; 20), F(10500; 40) | První kandidát ZERO_DISTANCE, druhý 40/500×100 = 8,000000 |
| C11 | F(10000; 50), P(10500; 20), F(10400; 25), F(11000; 40) | ODOMETER_DECREASE; blokace od kotvy 10000, žádný platný interval |
| C12 | Počátek 10000, F(9900; 40), F(10500; 40) | BELOW_INITIAL_ODOMETER, žádné platné měření do opravy |
| C13 | F(0; 40), F(500; 50), F(1500; 30) | Intervaly 10 a 3; vážená 80/1500×100 = 5,333333; UI 5,33, nikoli 6,50 |
| C14 | Ve stejný den pořadí F(10000; 50), P(10200; 20), F(10600; 25) | 7,500000; datum samo interval nezneplatní |
| C15 | Stejná data jako C14, ale prohozené pořadí P a koncové F | Pokles 10600→10200 zpochybní i právě uzavřený interval; blokace od kotvy 10000, spotřeba null, UI varuje chybným pořadím |
| C16 | C05: zpětně přidat P(10400; 5) před koncové F | Nově 50/600×100 = 8,333333; žádný starý výsledek v cache |
| C17 | C05: změnit prostřední litry 20→15 | 40/600×100 = 6,666667 |
| C18 | C05: odstranit prostřední P | 25/600×100 = 4,166667; uživatelské potvrzení dopadu, nelze domyslet ztracené litry |
| C19 | F 31. 1. (10000; 50), P 1. 2. (10300; 20), F 5. 2. (10600; 25), filtr únor | Spotřeba 7,500000 v únoru; nákupy února 45 l; A může být mimo filtr |
| C20 | Stejné jako C19, filtr pouze 1. 2. | Nákupy 20 l; žádný uzavřený interval v období, spotřeba null |
| C21 | F(0; 40; 1600), P(300; 20; 780), F(600; 25; 1000) | Spotřeba 7,500000; intervalová částka 1780, nákupní Kč/100 km 296,666667; celkové nákupy 3380 Kč |
| C22 | Dva nákupy 10 l / 400 Kč a 30 l / 1080 Kč | Realizovaná cena 1480/40 = 37,000000; nikoli průměr cen 38 |
| C23 | 12,345 l × 38,90 Kč/l | Návrh částky 480,22 Kč HALF_UP; přesně zadaných 480,00 Kč zůstane 480,00 |
| C24 | C05, prostřední P má break_before=true; pak F(11200; 42) | První kandidát HISTORY_GAP; další 42/600×100 = 7,000000 |
| C25 | Plné PETROL, částečné DIESEL, plné PETROL | MIXED_FUEL; výdaje započteny, kandidát bez platné spotřeby |
| C26 | Vozidlo UNSUPPORTED_MULTI_TANK, jinak C05 | UNSUPPORTED, spotřeba null; nákupy normálně dostupné |
| C27 | Tentýž vůz dostupný přes vlastnictví i vadný redundantní grant ve fixture | Jeden součet historie, žádné násobení; služba grantu běžně takový stav zakáže |
| C28 | Dvě auta PETROL: 45 l/600 km a 35 l/500 km | 80/1100×100 = 7,272727, každý vůz jednou |
| C29 | C28, druhé auto DIESEL | Dvě skupiny 7,500000 a 7,000000, společná spotřeba null |
| C30 | F(0; 40), F(500; 50), F(1000; 40), P(900; 10), F(1500; 30) | Platný pouze první interval 50/500×100 = 10,000000; pokles zablokuje intervaly začínající kotvou 500 a později |
| C31 | Nula/záporné litry, záporný tachometr, nadměrná přesnost, NaN/Infinity | Tvrdá validace odmítne, nevytvoří interval ani DB záznam |
| C32 | Dva záznamy se stejnou pozicí ve dni v přímém vstupu služby | INVALID_ORDER; nevybírat náhodnou posloupnost |
| C33 | Norma 6,000, naměřeno 7,500000 | Rozdíl +1,50 l/100 km a +25,00 %; se zdrojem/metodikou |
| C34 | Chybějící norma nebo žádný platný interval | Srovnání null, žádné dělení nulou |

Testy navíc ověří determinismus po explicitním seřazení a neměnnost vstupních dat, čtení přes hranici roku, přestupný den, pondělní začátek týdne a změnu letního času bez posunu obchodního data. API testy musejí ověřit, že detail intervalu neprozradí záznam nepřístupného auta. Transakční testy pokryjí dvě současné změny pořadí a vytvoření při odebrání grantu.

## 6. Rozhraní služby pro implementaci

Navržené čisté funkce: `build_intervals(vehicle_context, ordered_records)`, `aggregate_intervals(intervals, period, fuel_group)` a `aggregate_purchases(records, period)`. Návratové typy jsou immutable DTO s Decimal hodnotami, ID použitých záznamů, důvody a pokrytím. Doménové chyby se mapují na stabilní API kódy až v HTTP vrstvě. Finální testy nemají kopírovat algoritmus; používají výše uvedené ručně stanovené očekávané výsledky.
