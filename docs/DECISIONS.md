# Architektonická rozhodnutí

Datum návrhu: 2. 11. 2026. Uživatel následně výslovně zadal implementaci fáze 1 podle tohoto návrhu; zbývající etapy nadále vyžadují vlastní pokyn. Uživatel následně samostatně potvrdil fázi 2. Stav konkrétní implementace a ověření viz PHASE_1.md a PHASE_2.md. Dodatkem během fáze 1 uživatel výslovně změnil ukládání všech trvalých dat na DB a paletu na modrou/šedou/bílou; tyto změny jsou zachyceny níže.

| ID | Rozhodnutí | Důvod / důsledek |
| --- | --- | --- |
| ADR-001 | Modulární Django monolit a React SPA v jednom repozitáři | Jednoduchý self-hosted provoz, sdílené transakce, žádné služby bez potřeby |
| ADR-002 | Jeden origin, `/api/v1/`, Django DB sessions a CSRF | Relativní URL přežijí změnu domény; žádné tokeny v localStorage |
| ADR-003 | Django 5.2 LTS + Python 3.14; ostatní podporované řady podle architektury | Dlouhá podpora před nejnovější krátkodobou Django řadou; před implementací ověřit patche a zamknout závislosti |
| ADR-004 | Vlastník ve `Vehicle.owner`, granty jen VIEWER/CONTRIBUTOR | Právě jeden OWNER bez dvou zdrojů pravdy; ADMIN je systémová role |
| ADR-005 | Sdílení a převod vlastníka provádí pouze ADMIN | Odpovídá zadání a brání neřízenému šíření přístupu; grant zpřístupní celou historii i účtenky |
| ADR-006 | CONTRIBUTOR může upravit své záznamy, mazání jen OWNER/ADMIN | Zadání určuje editaci, nikoli mazání přispěvatelem; konzervativní konkrétní doplnění |
| ADR-007 | Decimal, CZK, litry a km; skutečná částka má přednost | Sleva ani haléřové odchylky neznehodnotí účetní součet; zadaná a efektivní cena se odlišují |
| ADR-008 | Datum + uložené pořadí v rámci dne | Samotný den ani čas vytvoření neurčují pořadí historických tankování; nutné pro reprodukovatelné intervaly |
| ADR-009 | Výpočet plná–plná v čisté servisní vrstvě nad celou historií | Správné částečné nákupy, zpětné změny a filtry; žádné kopie výpočtů podle uživatele |
| ADR-010 | Chybějící mezilehlý tachometr zachová litry v intervalu | Známé obě plné hranice postačují pro vzdálenost; neúplnost jednotlivého záznamu zůstává viditelná |
| ADR-011 | Klesající tachometr zablokuje měření od poslední dotčené plné kotvy do opravy | Zpochybňuje i právě uzavřený interval při chybném pořadí; starší nedotčené intervaly zůstávají, přesné pravidlo v metodice |
| ADR-012 | Přerušení evidence má výslovný příznak a zneplatní přesahující interval | Úplně vynechaný nákup nelze zjistit z čísel; UI musí dát možnost mezeru označit |
| ADR-013 | Spotřeba podle koncového dne, nákupy podle dne nákupu | Jednotná reprodukovatelná metodika; v UI vysvětlit rozdílné podklady |
| ADR-014 | Náklady / 100 km jsou nákupní náklady v měřicích intervalech | Nejde o přesné ocenění spálených zásob; bez zavádění skladové metody FIFO |
| ADR-015 | Spotřeba pouze pro jednu kapalnou nádrž; různé druhy paliva agregovat zvlášť | CNG/kg, elektřina a více nádrží vyžadují jinou metodiku; evidovat výdaje lze i při vypnuté spotřebě |
| ADR-016 | Jedna soukromá JPEG/PNG příloha, 10 MiB / 24 MP, originál + očištěný náhled | Omezení paměti a rizik, zachování originálu pro budoucí OCR; žádné neověřené vzdálené obrázky |
| ADR-017 | Jednorázové dočasné heslo 24 h a omezená session 15 min | Bez SMTP a veřejného resetu; povinná změna, hashování, odvolání starých sessions |
| ADR-018 | Archivace aut a deaktivace účtů; bez trvalého mazání auta s historií | Zachování vztahů, auditu a podkladů statistik; mazání tankování je explicitní autorizovaná operace |
| ADR-019 | Výpočet na požádání, zámek vozidla a optimistická revize | Konzistence při souběhu bez job fronty a invalidace uložených výsledků |
| ADR-020 | Idempotentní vytvoření tankování přes klientské UUID | Mobilní retry po timeoutu nesmí vytvořit dvě tankování; není to offline synchronizace |
| ADR-021 | Záloha celé DB včetně účtenek ve společném konzistentním bodě | Aktualizováno podle ADR-023; před produkcí zkušební restore včetně integrity binárních dat |
| ADR-022 | VIN/OCR pouze pozdější adaptéry na backendu | API klíč zůstane soukromý, import/OCR jen navrhuje údaje k potvrzení |
| ADR-023 | Všechna trvalá aplikační data v PostgreSQL, přílohy jako bytea | Výslovný dodatek uživatele ve fázi 1; nahrazuje návrh privátního filesystemu. Profil a motiv jsou společné pro zařízení, cookie pouze identifikuje session. Účtenky se implementují až ve fázi 3, s limity a většími DB zálohami. |
| ADR-024 | Neutrální modrá/šedá/bílá paleta v obou motivech | Výslovný vizuální pokyn uživatele během fáze 1, nahrazuje původní zelený akcent |
| ADR-025 | PostgreSQL transakční advisory lock pro administrační změny | Krátký společný zámek brání souběžné deaktivaci posledních dvou ADMIN; uživatelské zápisy mají také row lock a ETag |
| ADR-026 | Vlastní administrační reset odmítnout; změna vlastního hesla přes Nastavení | Správce nemůže přijít o session před zobrazením jednorázového hesla; reset jiných účtů odvolá jejich staré sessions |
| ADR-027 | Před produkcí HSTS=0, cookies Secure a HTTPS redirect již zapnuté | HSTS vyžaduje ověřenou skutečnou doménu v etapě 7; check --deploy proto ve fázi 1 vrací zdokumentované security.W004, neskrýváme ho |
| ADR-028 | Potvrzení hesla a jeho limity před transakcí doménového zápisu | Selhání nesmí rollbackem vymazat čítač neúspěšných pokusů. Po úspěchu se v transakci znovu ověří auth_epoch, role, verze a zámky; neobchází se aktuální oprávnění. |

| ADR-029 | Změna grantů zvýší také verzi vozidla | Převod s rozpracovaným ETag nesmí přepsat mezitím změněné sdílení; společný row lock vozidla drží převod a granty atomické. Účty se zamykají před vozidlem, ve stabilním pořadí UUID. |
| ADR-030 | Ve fázi 2 bez veřejného DELETE vozidla | Jedinou cestou odebrání z aktivního seznamu je archivace; žádné nevratné odstranění dat nebo předčasný model tankování. |
| ADR-031 | Budoucí VIN doplní potvrzovanou ilustrační fotografii v DB | Dodatek uživatele během fáze 2. Fotografie modelu vyžaduje ověřenou shodu a licenci/atribuci; originál, náhled i původ patří do PostgreSQL. Bez spolehlivé shody zůstane ikona. Integrace je součástí fáze 8, viz INTEGRATIONS.md. |

## Původní zásadní body fáze 0

1. **Rozsah měření:** CZK/litry/km, jedna nádrž pro spotřebu, různá paliva v dashboardu odděleně; bez spotřeby CNG/EV a více nádrží v MVP (ADR-007, 015).
2. **Práva:** vlastník nesdílí auto sám; CONTRIBUTOR upravuje vlastní tankování, ale nemaže je. Sdílení zpřístupní celou historii a přílohy (ADR-004–006).
3. **Pořadí a neúplná historie:** pořadí ve dni se potvrzuje; chybějící mezilehlý tachometr může mít platný nadřazený interval; pokles km blokuje další měření do opravy; mezera se označuje příznakem (ADR-008–012).
4. **Peníze a časové statistiky:** částka účtenky je rozhodující, cena je realizovaná; spotřeba patří ke koncovému dni a náklady / 100 km mají popsaný nákupní význam (ADR-007, 013–014).
5. **Správa účtů a dat:** reset přes jednorázové heslo bez e-mailové služby; archivace místo trvalého mazání aut; originály účtenek zůstávají soukromé včetně metadat (ADR-016–018).

Fáze 1 byla poté výslovně zahájena uživatelem. Další fáze se nezahajují automaticky; připomínky lze uvést podle ADR ID. Přesná verze knihovny nebo rozteč komponenty nejsou samostatným schvalovacím bodem; řeší se v rámci schváleného rozsahu.
