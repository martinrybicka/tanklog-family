# Oprávnění, bezpečnost a provozní integrita

Stav: požadavky návrhu. Jejich implementace a ověření jsou akceptační podmínky odpovídajících etap, nikoli splněná bezpečnostní garance současného adresáře.

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
- Uživatelsky stejné sdělení pro neexistující/deaktivovaný účet nebo chybu hesla. Neomezit ochranu pouze na DRF throttling, který sám není plnohodnotnou obranou proti distribuovanému hádání.

Založení/reset: ADMIN se znovu autentizuje vlastním aktuálním heslem. Server kryptograficky náhodně vygeneruje alespoň 128 bitů entropie dočasného hesla, uloží pouze Django hash, nastaví `must_change_password`, expiraci 24 hodin a nový `auth_epoch`. Vrátí otevřené heslo jen jednou v HTTPS odpovědi no-store; správce je předá soukromě mimo TankLog. Žádné ukládání do auditu, prohlížečového úložiště nebo logu.

Přihlášení dočasným heslem musí pod zámkem účtu atomicky zkontrolovat expiraci a jednorázovost. Po prvním úspěchu dočasný hash zneplatnit a založit omezenou session s aktuálním session hashem. Druhé použití stejného hesla neprojde ani souběžně. Pokud session propadne před nastavením hesla, správce vydá nové. Omezená session nemá přístup k autům, exportu ani administraci, i pokud jde o účet ADMIN. Po nastavení nového hesla se omezení zruší a přístupové údaje znovu rotují. Tuto sekvenci je nutné explicitně otestovat; pouhé `must_change_password` ve frontendu nestačí.

Změna role/deaktivace posledního aktivního ADMIN je zakázána v transakci se zámkem. První a nouzový správce se zakládá řízeným management příkazem, bez skrytého výchozího účtu. Povinné MFA není v zadání MVP, lze navrhnout před širším vystavením internetu jako další samostatný rozsah.

## 4. Účtenky a vstupy

Limit 10 MiB na obrázek se kontroluje na proxy i backendu; HTTP multipart request má malou dodatečnou režii (např. proxy limit 12 MiB, soubor stále 10 MiB). Požadavky i formuláře mají konečné velikosti. Kontrolovat skutečné dekódování Pillow, rozměry max. 24 MP, nepovolit dekompresní bomby, animace, poškozené obrázky a neočekávaný formát. MIME a přípona od klienta nestačí.

Originál JPEG/PNG je soukromý, náhled se znovu zakóduje bez EXIF. Uživatel před sdílením ví, že originál může obsahovat metadata. Interní názvy jsou náhodné UUID; původní jméno slouží jen jako očištěný název stažení, nikdy jako cesta. Zabránit traversal a symlink úniku, omezit filesystem oprávnění. Originál podávat s ověřeným MIME, `Content-Disposition: attachment` a `X-Content-Type-Options: nosniff`; náhled lze zobrazit inline po autorizaci.

Soubory nejsou veřejné přes `/media/`. nginx `internal` lokace přijímá pouze interní přesměrování po ověření backendem; přímý přístup vrací 404. Každé stažení znovu ověřuje session a právo k autu. Žádná veřejná podepsaná URL s dlouhou platností. Limitovat frekvenci uploadu a kapacitu svazku, hlídat volné místo a selhání disku.

Upload jde do privátního stagingu, po validaci vznikne originál/náhled a teprve pak DB vazba. Při DB rollbacku nový soubor uklidit; při výměně/DELETE odstranit starý až po commitu. Pravidelný idempotentní úklid po ochranné lhůtě řeší zbytky po pádu, nemaže soubory odkazované živou DB. OCR nemění originál a nespouští se v MVP.

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

Návrh pro malou instalaci: denní šifrovaná záloha mimo hostitele, 7 denních + 4 týdenní + 6 měsíčních bodů. Výchozí cíle RPO do 24 h a RTO do 4 h jsou plán, nikoli změřený výsledek. Klíč k obnově uchovat odděleně od serveru a zálohy. Záloha obsahuje `pg_dump` v custom formátu, soukromé originály/náhledy, kontrolní součty, verzi aplikace a migrací; tajnou konfiguraci uložit odděleně šifrovaně.

Konzistence: po dobu pořízení DB dumpu a kopie souborů zablokovat všechny zápisy a úklid souborů (u malé instalace údržbové okno / zastavení webových writerů), zabránit zapisování management příkazy. Čtení může být dostupné podle zvoleného režimu. Prosté nezávislé kopírování živé DB a účtenek bez společného bodu nestačí. Nepovažovat kopii běžícího datového adresáře PostgreSQL za validní dump.

Obnovu provést do **nového izolovaného** projektu/svazků: stejná kompatibilní verze PostgreSQL, restore DB, obnova souborů a oprávnění, kontrolní součty, kontrola migrací, login testovacím účtem a ověření několika účtenek, součtů a oprávnění. Produkční volumes se při cvičení nepřipojují. Zapsat čas, výsledky a odchylku RPO/RTO; opakovat alespoň čtvrtletně a po zásadní změně schématu. Rollback image nesmí předpokládat zpětnou kompatibilitu migrace.

Bez výslovného schválení se nemažou DB ani volumes, nespouští `docker compose down -v`, nucené Git operace ani obnova přes existující produkční data. Nasazení, přepsání dat a úpravy produkční infrastruktury vyžadují vlastní autorizovanou etapu.

## 8. Povinné negativní testy

Nepřihlášený a cizí USER nesmí přes známé UUID číst/měnit auto, tankování, účtenku, export, agregaci nebo interval. VIEWER nesmí nic zapisovat, CONTRIBUTOR nesmí cizí úpravu ani smazat vlastní tankování. Zkusit změnu FK v těle i nesoulad ID v URL. Ověřit odebrání grantu po předchozím úspěšném downloadu, archivované auto, deaktivaci s platnou cookie, expirované a souběžně použité dočasné heslo, omezeného ADMIN, chybějící CSRF na loginu, zneužití forwarded hlaviček, formula injection a přímou URL interního souboru. Podrobné rozdělení do etap je v [ROADMAP.md](ROADMAP.md).
