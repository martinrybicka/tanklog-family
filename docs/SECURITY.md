# Oprávnění, bezpečnost a provozní integrita

Stav: bezpečnostní požadavky průběžně implementované po etapách. Ve fázi 1 se testují účty, sessions, CSRF, reset, audit a produkční konfigurace. Fáze 2 přidává objektová práva vozidel, granty, převody a negativní/souběžné testy. Fáze 3 přidává autorizační kontroly historie/exportů/účtenek, validaci obrázků a auditovaný DB limit uploadů. Výsledky a výjimky ověření viz PHASE_1.md, PHASE_2.md a PHASE_3.md; nejde o obecnou bezpečnostní certifikaci aplikace.

## 1. Matice práv

Každá akce vyžaduje aktivní účet a plnou session, pokud není výslovně uvedena mezi veřejnými autentizačními cestami. ADMIN přistupuje ke všem autům; ostatní role platí pouze pro konkrétní dostupné auto.

| Akce | VIEWER | CONTRIBUTOR | OWNER | ADMIN |
| --- | --- | --- | --- | --- |
| Auto, historie, statistiky, XLSX a účtenky – čtení | Ano | Ano | Ano | Ano, všechna |
| Vytvořit vlastní auto | Ano jako USER | Ano jako USER | Ano | Ano |
| Měnit údaje / archivovat / obnovit dané auto | Ne | Ne | Ano | Ano |
| Přidat tankování do aktivního auta | Ne | Ano | Ano | Ano |
| Upravit vlastní tankování v aktivním autě | Ne | Ano | Ano | Ano |
| Upravit cizí tankování | Ne | Ne | Ano | Ano |
| Upravit historii archivovaného auta | Ne | Ne | Ano | Ano |
| Smazat tankování | Ne | Ne | Ano | Ano |
| Přidat/nahradit/smazat účtenku | Ne | Ke svému aktivnímu záznamu | Ano | Ano |
| Změnit pozici vlastního záznamu při jeho editaci | Ne | Ano, aktivní auto | Ano | Ano |
| Přeuspořádat celý den | Ne | Ne | Ano | Ano |
| Správa grantů a převod vlastníka | Ne | Ne | Ne | Ano |
| Účty, systém a audit | Ne | Ne | Ne | Ano |

USER bez grantu může vytvářet vlastní auta a spravovat profil, ale nevidí žádné cizí auto. Deaktivovaný účet nemá práva ani když zůstává vlastníkem. Odebrané sdílení okamžitě odebere i přístup k vlastním dříve přidaným záznamům. Autor ani plátce nejsou samostatným přístupovým oprávněním. Přístup k archivované historii nezmizí, ale nová tankování jsou zakázána všem do obnovení auta.

## 2. Vynucování a izolace

Výchozí politika DRF je uzavřená. Každý seznam nejprve omezuje množinu objektů podle vlastníka/grantu; detail pracuje s touto množinou, nikoli s libovolným ID z globální tabulky. Následuje kontrola akce. Stejné pravidlo pro související FK, plátce, soubory, statistiky, export a chybové zprávy. UUID pouze ztěžuje hádání; nedovoluje přeskočit kontrolu.

Zapisovatelné serializer fields jsou explicitní whitelist. Běžný požadavek nemůže změnit roli, vlastníka, autora, storage key, verzi nebo interní stav. Ověřuje se konzistence všech ID v URL/těle. Při pokusu o cizí ID vrátit 404 bez metadat cizího objektu. Roster účtů a audit smí pouze ADMIN; běžný uživatel dostane minimální volby plátce daného auta.

Všechny změny grantů, vlastnictví, archivace a historie zamykají vozidlo a kontrolují práva znovu v transakci. Odpověď/statistika se vytváří z konzistentního snapshotu. Po úspěšném odebrání přístupu každé nově vyhodnocené čtení selže; již doručený export nebo obrázek nelze zpětně odvolat. Query cache po odhlášení se maže. Oprávnění a invalidaci nesmí obcházet ani technický Django admin; zápisy vést přes služby, případně admin ponechat read-only.

## 3. Sessions, hesla a reset

- Django serverové DB sessions, bezpečné hashování hesel a standardní validátory (minimálně 12 znaků, běžná hesla a podobnost s identitou). Hashovací konfiguraci udržovat s frameworkem, bez vlastní kryptografie.
- Session cookie HttpOnly, SameSite=Lax, v produkci Secure; CSRF cookie Secure a SameSite=Lax. Token se předává maskovaný přes bootstrap, nemusí být čitelný z cookie. Ochrana CSRF výslovně i na anonymním loginu; samotná DRF session ochrana pro přihlášené nestačí.
- Rotace session a CSRF při loginu, timeout plné session nejvýše 12 hodin, omezené 15 minut; žádné neomezené „zapamatovat“. Logout ruší session, není GET odkaz.
- `auth_epoch` se kontroluje při každém požadavku. Reset, změna hesla a deaktivace zneplatní předchozí sessions; po vlastní změně hesla lze založit jednu novou aktuální session. Reaktivace neoživí staré sessions.
- Ochrana přihlášení přes udržovaný django-axes s databázovým handlerem, bez nové služby. Ověřit kompatibilitu a konkurentní chování při fázi 1. Návrh limitů: 5 selhání pro kombinaci účet+IP / 15 minut a samostatný IP limit na nginx; ověřit chování za sdílenou NAT a nemožnost obejití podvrženou hlavičkou. [Oficiální django-axes dokumentace](https://django-axes.readthedocs.io/en/latest/).
- Stejný DB limit chrání i potvrzování aktuálního hesla při citlivých akcích, aby se ověření hesla nestalo alternativním neomezeným login endpointem.
- Ověření aktuálního hesla a zápis neúspěšného pokusu proběhnou před transakcí doménové změny. Po získání zámků se znovu kontroluje auth_epoch/aktivace/role/verze. Nezapínat globální ATOMIC_REQUESTS bez úpravy tohoto toku: rollback odmítnuté akce by nesměl vymazat čítač ochrany loginu. Tento scénář má vlastní test.
- Uživatelsky stejné sdělení pro neexistující/deaktivovaný účet nebo chybu hesla. Neomezit ochranu pouze na DRF throttling, který sám není plnohodnotnou obranou proti distribuovanému hádání.

Založení/reset: ADMIN se znovu autentizuje vlastním aktuálním heslem. Server kryptograficky náhodně vygeneruje alespoň 128 bitů entropie dočasného hesla, uloží pouze Django hash, nastaví `must_change_password`, expiraci 24 hodin a nový `auth_epoch`. Vrátí otevřené heslo jen jednou v HTTPS odpovědi no-store; správce je předá soukromě mimo TankLog. Žádné ukládání do auditu, prohlížečového úložiště nebo logu.

Přihlášení dočasným heslem musí pod zámkem účtu atomicky zkontrolovat expiraci a jednorázovost. Po prvním úspěchu dočasný hash zneplatnit a založit omezenou session s aktuálním session hashem. Druhé použití stejného hesla neprojde ani souběžně. Pokud session propadne před nastavením hesla, správce vydá nové. Omezená session nemá přístup k autům, exportu ani administraci, i pokud jde o účet ADMIN. Po nastavení nového hesla se omezení zruší a přístupové údaje znovu rotují. Tuto sekvenci je nutné explicitně otestovat; pouhé `must_change_password` ve frontendu nestačí.

Změna role/deaktivace posledního aktivního ADMIN je zakázána v transakci se zámkem. První a nouzový správce se zakládá řízeným management příkazem, bez skrytého výchozího účtu. Povinné MFA není v zadání MVP, lze navrhnout před širším vystavením internetu jako další samostatný rozsah.

Fáze 1 zpřesňuje bezpečné chování: administrační reset vlastního účtu se odmítá, aby správce neztratil přihlášení dřív, než si přečte nové jednorázové heslo. Vlastní heslo mění přes Nastavení. Názvy účtů jsou ASCII (písmena, čísla a . @ + - _), normalizované na malá písmena a chráněné case-insensitive unikátním DB indexem.

Profil, nastavení motivu, audit i session záznamy jsou v DB. Cookie obsahuje jen session identifikátor a CSRF hodnotu; uložená data nejsou v localStorage/sessionStorage/IndexedDB. Odstranění cookies nebo nové zařízení pouze vyžadují přihlášení. Přístup k datům vždy vychází ze serverového účtu, ne z identifikátoru uloženého jen v prohlížeči.

## 4. Účtenky a vstupy

Limit 10 MiB na obrázek se kontroluje na proxy i backendu; HTTP multipart request má malou dodatečnou režii (např. proxy limit 12 MiB, soubor stále 10 MiB). Požadavky i formuláře mají konečné velikosti. Kontrolovat skutečné dekódování Pillow, rozměry max. 24 MP, nepovolit dekompresní bomby, animace, poškozené obrázky a neočekávaný formát. MIME a přípona od klienta nestačí.

Originál JPEG/PNG je soukromý, náhled se znovu zakóduje bez EXIF. Uživatel před sdílením ví, že originál může obsahovat metadata. Oba obsahy budou podle dodatku uživatele z fáze 1 uložené v PostgreSQL (implementace až ve fázi 3). Interním identifikátorem je UUID; původní jméno je očištěný název stažení a nikdy cesta. Originál podávat s ověřeným MIME, `Content-Disposition: attachment` a `X-Content-Type-Options: nosniff`; náhled lze zobrazit inline po autorizaci.

Přílohy nejsou veřejné přes `/media/`; nginx tyto cesty odmítá. Každé stažení binárního obsahu z DB znovu ověřuje session a právo k autu. Žádná veřejná podepsaná URL s dlouhou platností. Limitovat frekvenci uploadu, velikost DB a jejího svazku, hlídat volné místo a selhání disku. Binární obsah nikdy nevkládat do běžného seznamu/JSON statistik nebo auditu.

Upload se validuje v omezeném pracovním prostoru; případné dočasné soubory nejsou trvalým úložištěm. Výměna nebo DELETE přílohy proběhne atomicky nad binárními poli/metadaty v DB. Rollback zachová původní obsah. OCR nemění originál a nespouští se v MVP.

Pro XLSX vynutit textový typ libovolného uživatelského textu, včetně řetězců po bílých znacích s prefixem `=`, `+`, `-`, `@`. Testovat načtením výsledného sešitu: žádná textová buňka nemá `data_type=f`. Nekonstruovat vzorce ani externí odkazy. Číselné buňky lze zapisovat jako čísla po kontrolovaném převodu pro XLSX, ale nikdy z nich zpětně odvozovat databázovou přesnost.

## 5. Produkční nastavení

Konkrétní požadavky navazují na [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/) a [nastavení důvěry proxy](https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header). Před nasazením provést `check --deploy` s produkčním settings modulem a skutečný test přes NPM.

| Oblast | Podmínka |
| --- | --- |
| Django | DEBUG=False; silný vlastní SECRET_KEY; explicitní ALLOWED_HOSTS; přesné CSRF_TRUSTED_ORIGINS |
| Transport | HTTPS na NPM; přesměrování HTTP ověřené bez smyčky; HSTS zapnout až po ověření domény/HTTPS, subdomény nepřidávat automaticky |
| Proxy | Backend dostupný jen důvěryhodné webové proxy, sanitizované forwarded hlavičky; bezpečně zachované původní https a klientská IP |
| Cookies | SESSION_COOKIE_SECURE/HTTPONLY, CSRF_COOKIE_SECURE, SameSite; bez neodůvodněného globálního cookie domain |
| Síť | PostgreSQL bez publikovaného portu, backend bez přístupu z internetu, jen web na síti NPM |
| Server | Gunicorn místo runserver; pinned obrazy, limity zdrojů, restart policy, healthchecky a řízené migrace |
| Frontend | Lokálně hostované závislosti/fonty; CSP bez nepotřebných externích zdrojů, frame-ancestors a nosniff; vyhnout se raw HTML z poznámek |
| Data | Persistentní DB a účtenky, audit, kontrola volného místa, monitorování healthchecku |

Při změně domény zkontrolovat cookies, originy a proxy hlavičky; nepovolovat `*` jako univerzální opravu CSRF. API klíče pouze backend env; `VITE_*` je veřejný buildový prostor. Závislosti a image průběžně aktualizovat a zkontrolovat licenční podmínky případných log.

## 6. Audit, logy a retence

Audit zapisuje povolené rozdíly současně se změnou, významné administrační akce a reset bez hesla. Je čitelný jen ADMIN, nemá veřejné mutace. Běžné logy mají request ID, stav a bezpečné technické údaje, bez cookie, Authorization, hesel, příloh, poznámek a kompletních payloadů. Případné IP adresy pro ochranu loginu mají omezenou retenci.

Navržené výchozí retence pro schválení před produkcí: provozní logy 30 dní, login pokusy 30 dní, audit 365 dní; obchodní historie do explicitního odstranění. Běžné rozhraní neposkytuje smazání účtu/aut s historií. Případný skutečný výmaz osobních údajů je řízený postup včetně návazností a záloh; nejde o pouhou deaktivaci. Konkrétní provozovatel může potřebovat jinou politiku, tu stanovit před fází 7.

## 7. Zálohy a ověřená obnova – podmínka produkce

Návrh pro malou instalaci: denní šifrovaná záloha mimo hostitele, 7 denních + 4 týdenní + 6 měsíčních bodů. Výchozí cíle RPO do 24 h a RTO do 4 h jsou plán, nikoli změřený výsledek. Klíč k obnově uchovat odděleně od serveru a zálohy. Záloha obsahuje `pg_dump` v custom formátu včetně binárních originálů/náhledů v DB, kontrolní součty, verzi aplikace a migrací; tajnou konfiguraci uložit odděleně šifrovaně. Binární účtenky zvětší dump a délku obnovy; cíle ověřit s realistickou velikostí databáze.

Konzistence: `pg_dump` zachytí jednotný snapshot všech aplikačních řádků i binárních příloh; samostatné kopírování souborového úložiště se nepoužívá. Pro kontrolovaný cutover může být stále potřeba údržbové okno. Nepovažovat kopii běžícího datového adresáře PostgreSQL za validní dump. Zálohovat i přiřazené hash hodnoty příloh pro následnou kontrolu integrity.

Obnovu provést do **nového izolovaného** projektu/svazků: stejná kompatibilní verze PostgreSQL, restore celé DB včetně binárních příloh, kontrolní součty, kontrola migrací, login testovacím účtem a ověření několika účtenek, součtů a oprávnění. Produkční volumes se při cvičení nepřipojují. Zapsat čas, výsledky a odchylku RPO/RTO; opakovat alespoň čtvrtletně a po zásadní změně schématu. Rollback image nesmí předpokládat zpětnou kompatibilitu migrace.

Bez výslovného schválení se nemažou DB ani volumes, nespouští `docker compose down -v`, nucené Git operace ani obnova přes existující produkční data. Nasazení, přepsání dat a úpravy produkční infrastruktury vyžadují vlastní autorizovanou etapu.

## 8. Povinné negativní testy

Nepřihlášený a cizí USER nesmí přes známé UUID číst/měnit auto, tankování, účtenku, export, agregaci nebo interval. VIEWER nesmí nic zapisovat, CONTRIBUTOR nesmí cizí úpravu ani smazat vlastní tankování. Zkusit změnu FK v těle i nesoulad ID v URL. Ověřit odebrání grantu po předchozím úspěšném downloadu, archivované auto, deaktivaci s platnou cookie, expirované a souběžně použité dočasné heslo, omezeného ADMIN, chybějící CSRF na loginu, zneužití forwarded hlaviček, formula injection a přímou URL interního souboru. Podrobné rozdělení do etap je v [ROADMAP.md](ROADMAP.md).

## 9. Ověření a omezení fáze 3

Negativní testy pokrývají cizí URL/FK, VIEWER/CONTRIBUTOR/OWNER/ADMIN, vlastní/cizí/archivované záznamy, odebrání přístupu i k původně vlastnímu záznamu a účtence, CSRF převzaté z výchozí autentizace, ETag a opakované klíče. Upload ověřuje MIME podle dekódovaných dat, poškození, animaci, velikost/rozměry a bezpečný název, znovu kóduje náhled bez EXIF. Obrázky/export nemají veřejnou URL a API odpovědi jsou no-store. Již doručené obrázky/soubory nelze zpětně odvolat.

Pokus o upload se po ověření základních práv/ETag auditně zaznamená před dekódováním, mimo transakci samotné náhrady. Limit 20/min na účet se pod zámkem účtu neztratí rollbackem poškozeného souboru. Nginx doplňuje 30/min/IP a body limit 12 MiB pro receipt; binární limit serveru zůstává 10 MiB. Selhání náhrady ponechá původní obrázek i verzi. Export vynucuje textový typ včetně prefixů whitespace/=/+/-/@ a odstraňuje XML-nepřípustné řídicí znaky pouze ve výstupu.

Docker/produkční nginx runtime ani skutečná obnova zálohy se bez místního daemonu neověřily. Úspěšné nativní testy tyto limity nenahrazují. Před veřejným provozem nadále platí oddělení aplikační DB role a fáze 5/7.

## 10. Analytické čtení fáze 4

Statistické endpointy a intervalové podklady používají plnou session a opakovanou kontrolu aktivního User/auth_epoch uvnitř read-only REPEATABLE READ snapshotu. V témže snapshotu se vyhodnotí selektor vozidel i celá historie. Neaktivní/dočasné session nedostanou doménová data, cizí vehicle_id/start_id/end_id nic neodhalí. Výběr aut je deduplikovaný přes EXISTS; nikoli násobící JOIN na granty. Binární obrázky, plátci a další soukromé údaje nejsou součástí statistického JSON.

Rozpracované čtení může dokončit snapshot získaný před souběžným odebráním grantu; následné nově zahájené čtení již vozidlo nenajde. Klient po chybě nezobrazuje předchozí data, po logoutu maže cache a soukromé API zůstává no-store. Po místní změně historie/metadat/grantů se invaliduje i analytická cache; ostatní okna znovu ověřují při focusu a po 30 s. Již zobrazené údaje nelze zpětně odvolat. Testy pokrývají konzistenci snapshotu během zápisu, souběžné pořadí, tvorbu proti odebrání grantu, IDOR, omezenou session a redundantní granty. Konkrétní výsledky a Docker omezení viz PHASE_4.md.

## 11. Ověření a doplnění fáze 5

PWA smí trvale držet jen pevně vyjmenované veřejné statické soubory. Jejich instalace vynechává cookies, žádná navštívená URL se dynamicky nepřidává do cache. API, downloady, exporty i mutace procházejí do sítě. Navigace při výpadku dostane obecnou offline stránku bez údajů účtu. Testy kontrolují CacheStorage po přihlášení, offline chování a opakování zápisu po obnově sítě. Unit testy workeru výslovně brání obsluze citlivých cest a ukládání navigačních odpovědí.

Paměťová query cache má gcTime=0; při 403/404 se odstraní dřívější úspěšná data vadného dotazu. Logout ruší cache bez dalšího síťového bootstrapu a oznamuje odhlášení ostatním oknům pomocí dočasného BroadcastChannel signálu bez osobních údajů. BFCache návrat vyžádá reload. Již doručené soubory a obsah obrazovky nelze zpětně odvolat, další serverové čtení vždy znovu ověří práva. Veřejné soubory v CacheStorage nejsou osobními daty a logout je nemusí odstranit.

Nginx chyby 413/429/503 mají JSON, private,no-store a stejné bezpečnostní hlavičky jako zbytek webu. Skrytý readiness endpoint vrací JSON 404. Chybný Host a špatný JSON dostávají serverový JSON 400; frontendové cesty zůstávají HTML fallback. Lokální HTTPS nginx/Gunicorn test ověřil Secure/HttpOnly/SameSite cookies, CSRF, podvržené forwarded proto, CSP/nosniff, přímé frontendové cesty, limity a nedostupný backend. Další negativní role/IDOR/varování/upload/XLSX/session/souběhy z fází 1–4 jsou součástí plné pytest regrese.

`check --deploy` nad lokální produkční konfigurací vrací jedinou známou výjimku security.W004 (HSTS=0, podle ADR-027). HSTS se nezapíná pro testovací localhost a bez ověřené produkční domény. Npm audit a pip-audit uzamčených produkčních Python závislostí nenašly známé zranitelnosti k datu ověření; nejde o trvalou garanci nebo bezpečnostní certifikaci. Docker image/provozní síť, úplný screen-reader audit a fyzická instalace na Android/iOS nebyly ověřené. Podrobné výsledky a omezení viz PHASE_5.md.

## CI a historie – lokální část fáze 6

Připravený workflow má jen contents:read, checkout s persist-credentials:false, ověřené úplné SHA akcí, konečné timeouty a pouze hostované ubuntu-24.04 runnery. Nemá pull_request_target, workflow_run, secrets kontext, OIDC, zápis balíčků, deployment ani upload artefaktů. Testovací heslo PostgreSQL služby je výslovně syntetické, použité pouze na loopbacku jednorázového runneru. Nejde o produkční credential. Kontejnerový pomocník generuje vlastní náhodné secrets do ignorovaného souboru s právy 600.

Gitleaks s redakcí kontroluje obsah celé historie; samostatná kontrola zakazuje cesty provozních dat a ověřuje ignore. Regresní testy odmítají zvýšená oprávnění, pohyblivé tagy, vzdálený Docker/DB a publikaci. Tyto kontroly nejsou univerzálním detektorem všech možných úniků. Lokálně byly také porovnány skutečné hodnoty secrets z .env se sledovanými soubory bez jejich výpisu. Žádné .env, soukromé přílohy, databáze ani provozní logy nebyly přidány do Gitu.

Kontrola check --deploy přijímá pouze již zdokumentované security.W004 (HSTS=0 dle ADR-027). Nové chyby/varování zastaví kontrolu, žádné Django kontroly nejsou umlčené. Skutečné nastavení GitHub repozitáře, viditelnost private, branch protection a úspěch runneru nebyly ověřené: uživatel zakázal odesílání. Před případnou pozdější autorizovanou publikací se audit zopakuje. Podrobnosti a výsledky viz [PHASE_6.md](PHASE_6.md).

## Lokální příprava bezpečného provozu – fáze 7

Nový produkční svazek má oddělený bootstrap přístup, backend používá omezenou roli. Inicializace neprovádí automatické přejmenování ani přepis již existujících rolí. Production env template a preflight vyžadují přesný HTTPS origin, host, důvěryhodnou proxy, různá silná tajemství, odpovědnou osobu a zálohovací cesty. Default dev .env není produkční konfigurace. Access logy nginx/Gunicorn neobsahují query string, cookies ani klientskou IP; rotace Docker logů omezuje velikost. NPM a další vrstvy logování se musí zkontrolovat na skutečném serveru.

Zálohovací kontejner používá pouze veřejný age recipient, soukromý klíč musí být oddělený od serveru a off-host archivu. Dočasný nešifrovaný dump je privátní, v kontejneru na tmpfs; hostitel musí chránit swap/core dumps. Age není podpis původu a restore smí přijmout pouze vlastní důvěryhodný archiv, protože dump může obsahovat SQL. Velikost dešifrování je omezená, archiv odmítá odkazy/cesty a kontrolní součet se ověří před vytvořením DB. Restore povolí pouze nový tanklog_restore_* cíl, bez --clean a bez mazání existujících dat/svazků.

Místně byla skutečně obnovena celá syntetická DB s 19 tabulkami do odděleného clusteru; ověřeny otisky, originály/náhledy, role, API přihlášení/CSRF a součty. Chybný klíč, poškozený ciphertext a existující cíl jsou odmítnuté. To není obnova do Docker volumes ani prokázaná off-host záloha. Scheduler je pouze neinstalovaná šablona pro budoucí Linux; retence je plán bez automatického mazání. Chybí skutečná produkční infrastruktura, odpovědná osoba a měření na reálném objemu. Bez nich nelze potvrdit kompletní akceptaci fáze 7. Viz OPERATIONS.md a PHASE_7.md.

## Fáze 8 – integrace a rozšířená evidence

Stejné aktivní účty, omezení session, CSRF a objektové role platí pro události, součty, termíny, kandidáty, binární fotografie, návrhy importu i OCR. Žadatel je navíc součást soukromého přístupu k návrhům. Před potvrzením a po externí práci se práva znovu ověřují; cizí UUID není oprávnění. Event mutace používají zámky, ETag a per-user idempotenci; celé potvrzení importu je transakční a vyžaduje původní revizi historie/auta.

RSV/Commons mají pevné HTTPS hosty, žádné redirecty, jiné porty ani credentials v URL; DNS adresy musejí být veřejné. JSON má limit 1 MiB, obrázek 5 MiB/12 MP, socket timeout 5 s, nejvýše 3 kandidáti. HTML metadata jsou změněna na prostý text; licence CC0/BY4/SA4 s úplným původem. VIN jde pouze oficiálnímu RSV, Commons dostává jen značku/model. Klouzavá DB kvóta je 5/účet a 20/provider za 60 s (OCR 3/účet); žádné automatické externí retry. Secrets z prostředí nevstupují do auditu, odpovědí ani OCR child prostředí.

OCR: ověřený engine 5.5.4 a hashe ces/eng, soukromý očištěný grayscale vstup max. 2000×2000, timeout 15 s, CPU 10 s, na macOS RSS dohled 512 MiB, výstup 2 MiB, 64 deskriptorů, dva DB sloty s expirací. Linux navíc RLIMIT_AS 1 GiB; jeho běhové ověření čeká na Docker. macOS nepodporuje použitelný RLIMIT_AS/DATA a je hlídán z rodiče přes RSS. Temp obsah se uklízí, v Dockeru je `/tmp` tmpfs s limitem. Výsledek je návrh, vždy s výběrem polí a kontrolou původu/verze účtenky; původní dokument se nemění. Resource limity nejsou plnohodnotný OS sandbox.

CSV je UTF-8, max. 128 KiB/200 řádků, whitelist polí a žádné vzdálené přílohy/role/owner/payer ID. Původní text zůstává soukromý v DB. Neaktivní/neaktuální přístup import nepotvrdí. Offline fronta je pouze neuložená paměť okna: výslovný opt-in, upozornění před zavřením, nové ověření účtu před synchronizací, purge při logoutu/změně účtu. Žádná soukromá SW/IndexedDB/localStorage cache ani automatická synchronizace.

Úplný živý RSV/foto průchod, Linux image a skutečné provozní zatížení nejsou ověřené. Viz [PHASE_8.md](PHASE_8.md); tyto limity nelze nahrazovat fixture úspěchem.

## Rodinná cesta

Nahraný DB návrh je soukromý pro autora s přístupem k autu, včetně přímé fotografie. Upload a dokončení vyžadují právo vytvářet kapalné tankování; čtenář návrh nevytvoří. Data se znovu autorizují pod zámky a po OCR, originál má stejné ověření jako dosavadní účtenka. Nový upload podléhá kvótě, OCR sdílí původní globální sloty/limity a nikdy nejde do cloudu. Žádná veřejná registrace, JWT nebo browserová trvalá storage.

ADMIN smí připravit výchozí auto člena, ale musí jít o jeho skutečně dostupné aktivní auto se zápisovým právem. Předvolba nevytváří grant; cílové ID nelze využít k prolomení přístupové matice. ETag brání přepsání souběžné konfigurace. Atomické dokončení a hash/idempotence brání duplicitám i částečnému uložení fotografie. Fotografie/OCR návrh se uchová přes odhlášení a nové zařízení v DB; neuložený ruční formulář se neukládá do browseru.


Nasazení 6. 11. 2026: historický zmrazený Debian snapshot v linuxovém buildu nahradily oficiální podepsané Bookworm a Bookworm-security repozitáře kvůli nedostupnému stahování snapshot balíčků. Základní image zůstává připnutý digestem a zdroj Tesseract/modely mají stejné SHA-256; tranzitivní systémové knihovny získávají aktuální opravy Bookworm. Starší tvrzení o plně zmrazených OS balíčcích se tímto zpřesňuje.
