# Provoz, zálohy a obnova – lokální příprava fáze 7

Stav 3. 11. 2026: implementované nástroje a místní zkouška. **Žádný produkční zásah ani přenos na server nebyl proveden.** Skutečné nasazení vyžaduje samostatné povolení a doplnění inventáře. Výsledky viz [PHASE_7.md](PHASE_7.md). Aplikační data včetně všech binárních účtenek zůstávají v PostgreSQL; zálohy jsou provozní kopie, nikoli nové úložiště aplikace.

## Inventář před případným nasazením

| Údaj | Skutečný stav |
| --- | --- |
| Server, OS, architektura, Docker/Compose verze a kapacita | Nezjištěno; Mac/ARM64 není údaj o produkci |
| Veřejná doména, DNS, issuer/expirace certifikátu | Nezadáno a neověřeno |
| Existující síť a stabilní IP NPM | Neověřeno; název npm_proxy v dev šabloně není zjištěná síť |
| Připojené off-host úložiště, jeho vlastník a kapacita | Nezadáno; místní .runtime není off-host záloha |
| Konkrétní odpovědná osoba a kontakt pro obnovu/alerty | Neurčeno; povinné TANKLOG_OPERATIONS_OWNER |
| Produkční RPO/RTO a retence | Cíl RPO ≤24 h, RTO ≤4 h; plán 7 denních + 4 týdenní + 6 měsíčních bodů, vyžaduje schválení vlastníka |

Access logy webu a Gunicorn záměrně vynechávají query string/cookies/IP a Docker logy mají velikostní rotaci. Efektivní logování NPM a dalších vrstev musí provozovatel prověřit zvlášť.

Tyto údaje nelze odvodit z místní IP nebo ze syntetické .env. Před nasazením ověřit i závislé služby na stejném serveru a plán údržby. Produkce není povolená aktuálním pokynem.

## Produkční konfigurace

`.env.production.example` je záměrně nefunkční šablona. Při budoucím autorizovaném nastavení vytvořte soukromou kopii s právy 600 mimo Git; používejte jednoduché řádky KEY=value bez shellu, quotes a expanze. Tři tajemství (Django, bootstrap DB a aplikační DB) generujte nezávisle přes Python secrets.token_urlsafe, nikoli ručně. Preflight vyžaduje URL-safe hodnoty, přesnou jednu HTTPS doménu, odpovídající host/origin, oddělené DB role, konkrétní revizi, úložiště a vlastníka provozu:

```sh
python3 infra/ops/preflight.py --env-file /cesta/k/production.env
# Navíc skutečný připojený mount a veřejný klíč, bez přenosu dat:
python3 infra/ops/preflight.py --env-file /cesta/k/production.env --require-backup-mount
```

Kontrola nedokazuje platnost DNS/certifikátu, důvěryhodnost síťového zařízení ani fyzické umístění úložiště. Mountpoint může být i místní disk: operátor musí ověřit skutečný zdroj mountu, oddělený host a schopnost obnovy při ztrátě aplikačního hostitele. Není dovoleno při odpojení použít tichý fallback na místní adresář.

`compose.prod.yaml` používá interní DB, oddělenou bootstrap roli a aplikační roli bez SUPERUSER/CREATEDB/CREATEROLE/REPLICATION. `init-role.sh` se spustí pouze při prvním založení **nového** PostgreSQL svazku; stávající role/databáze nepřepisuje. Aplikace vytváří své tabulky/migrace v přiděleném schématu. Zálohovací operace mají samostatný bootstrap přístup, backend zná pouze aplikační heslo. Převod případné starší instalace vyžaduje samostatný kontrolovaný SQL plán; nikdy kvůli inicializaci nemažte existující svazek. Před migracemi ověřte skutečné atributy přihlášené aplikační role a vlastnictví tabulek.

Base DB healthcheck testuje TCP 127.0.0.1, aby dočasný inicializační Unix server nemohl předčasně označit DB za připravenou. Backendový healthcheck posílá nakonfigurovaný Host i při přístupu na loopback, takže kvůli němu není nutné povolit další hosty. Produkční web má kontrolu statického HTTP shellu; backend vlastní neveřejnou DB readiness. To nenahrazuje externí dohled přes veřejný HTTPS origin. Resource limity a volné místo nastavte podle skutečné kapacity a měření, nikoli podle tohoto Macu.

## NPM, HTTPS a proxy

Po budoucím ověření existující sítě připojuje prod konfigurace pouze web, s jednoznačným aliasem **tanklog-web**, port **8080**. Backend a DB se do NPM sítě nepřipojují a žádná služba nemá host port. Síť se sama nevytváří. V NPM použít ověřenou doménu, platný certifikát, Force SSL a upstream http://tanklog-web:8080. Nepoužívat localhost z kontejneru NPM ani náhodně odvozenou IP.

Na skutečné hranici NPM musí být původní klientské forwarded hlavičky nahrazené hodnotami z proxy: Host odpovídá veřejné doméně, X-Forwarded-Proto=https, X-Forwarded-For a X-Real-IP vycházejí ze skutečného klienta. Ověřit efektivní nginx konfiguraci NPM; nevkládat slepě duplicity proxy_set_header do Advanced. Vnitřní web důvěřuje schématu jen od NPM_TRUSTED_CIDR a přepíše IP/proto pro backend. Preferujte stabilní přesnou IP NPM /32 nebo /128; jinak vědomě posuďte všechny členy důvěryhodné podsítě.

Povinné skutečné ověření po autorizovaném nasazení: HTTP→HTTPS bez smyčky, curl bez -k, hostname a řetězec/expirace certifikátu, CSRF odmítnutí cizího originu, Secure/HttpOnly/SameSite cookies, podvržený Host/proto/IP, odmítnutí private_media/media a účtenky bez session, JSON API chyby a SPA fallback. Zkontrolovat skutečné publikované porty a členství sítí. HSTS zůstává 0 dle ADR-027; zapnout opatrně teprve po ověření HTTPS a domény, bez automatických subdomén/preload. Místní samopodepsaný test to nenahrazuje.

## Šifrovaná záloha

`infra/ops/backup.py backup` používá PostgreSQL **18.6**, age **1.3.2** a existující zamčené Python závislosti. `infra/operations.Dockerfile` má připnutý PostgreSQL i uv image digest, uv 0.13.6 a Python 3.14.10. SHA-256 oficiálních age archivů pro Linux amd64/arm64 je v tools.json a kontroluje se před instalací. Linux image zde kvůli chybějícímu Dockeru nebyl sestavený.

Algoritmus:

1. Otevře read-only REPEATABLE READ transakci, exportuje snapshot a předá jej pg_dump --snapshot do custom dumpu.
2. Ze stejného snapshotu vytvoří SHA-256 otisky všech řádků všech public tabulek, včetně bytea originálů/náhledů, oprávnění, sessions a migrací. Zkontroluje uložené SHA-256/velikosti originálů účtenek. Hash zahrnuje i náhledy; jejich zachování kontroluje obnova.
3. Manifest obsahuje čas snapshotu, commit aplikace, verzi formátu/PG, součet dumpu a otisky tabulek. Je **uvnitř šifrovaného archivu**.
4. Dump a manifest zabalí proudem do age. Trvalý výstup je pouze nový .tar.age s právy 600; zápis se synchronizuje a publikuje atomicky bez přepsání existujícího souboru. Neúspěšný .partial není platná záloha.

Dočasný nešifrovaný dump vzniká v privátním adresáři procesu a po skončení se odstraní. V operations kontejneru je /tmp tmpfs, root filesystem je read-only a capabilities odebrané. Hostitel musí řešit šifrování swapu/core dumps a ochranu privilegovaného přístupu. Nejde o záruku bezpečného přepsání bloků na běžném disku při nativním testu. Zajistěte kapacitu tmpfs i DB svazku; výchozí tmpfs 1 GiB a restore limit 512 MiB jsou testovací konzervativní limity, které před produkcí upravte a ověřte na realistických datech. Obnova dočasně potřebuje přibližně dvojnásobek rozbalovaného archivu plus místo pro obnovenou DB.

Soukromý age klíč generovat a držet **odděleně od aplikačního serveru a off-host archivu**. Běžný backup kontejner připojuje pouze veřejný recipient soubor a zálohovací mount; nemá identity klíč. Klíč neztratit: bez něj není obnova možná. Pro off-host adresář musí být nastaven přístup pro UID/GID 10001 kontejneru. Compose bindy mají create_host_path:false a nevytvářejí náhradní adresáře. Předem ověřte POSIX hardlink/fsync podporu cílového mountu.

Budoucí autorizované jednorázové zálohování po ověření prostředí:

```sh
python3 infra/ops/preflight.py --env-file /etc/tanklog/production.env --require-backup-mount
docker compose --env-file /etc/tanklog/production.env -f compose.yaml -f compose.prod.yaml -f compose.ops.yaml build operations
docker compose --env-file /etc/tanklog/production.env -f compose.yaml -f compose.prod.yaml -f compose.ops.yaml run --rm --no-deps operations
```

Tyto příkazy zde proti serveru nebyly spuštěné. Dump zahrnuje jednu aplikační DB a přílohy, ne globální role PostgreSQL, TLS certifikáty nebo .env. Role se v novém prostředí založí řízeným bootstrapem. Skutečnou tajnou konfiguraci a recovery postup uchovat **samostatně šifrovaně**, mimo Git a odděleně od privátního age klíče. Změnu SECRET_KEY plánovat jako odhlášení existujících sessions.

## Automatizace, retence a dohled

Šablony `infra/ops/systemd/` jsou pouze varianta pro budoucí Linux se systemd. Časovač plánuje 02:00 a 14:00 UTC, náhodné zpoždění do 15 minut a dohnání po startu. Služba kontroluje mount a konfiguraci, spustí pouze jednorázovou zálohu. Cesty /opt/tanklog, /etc/tanklog a /mnt/tanklog-backups musí odpovídat skutečnému serveru a env. Není zde instalován ani aktivován žádný časovač. Na jiném OS připravit scheduler podle zjištěné platformy.

Selhání služby vyvolá místní error záznam v journalu; alert service neposílá zprávy. Konkrétní vlastník musí před produkcí zapojit dohled journalu, stáří poslední úspěšné off-host zálohy (nejpozději 24 h), dostupnosti mountu, volného místa, expirace certifikátu a veřejného HTTP smoke testu. Bez takového dohledu není plánované RPO garantované. Proveďte ruční běh, zkontrolujte systemd-analyze verify, list-timers a journalctl na skutečném systému; zde systemd není dostupný.

Retence je 7 denních + 4 týdenní + 6 měsíčních nejnovějších bodů, s deduplikací. Příkaz pouze vypíše keep/review_only a nic nemaže:

```sh
# Pro lokální syntetické archivy, z kořene:
backend/.venv/bin/python infra/ops/backup.py retention-plan --directory /absolutni/cesta/k/zaloham
```

Automatické mazání není aktivní. Vlastník schválí odstraňování až po ověřené obnově a kapacitní/legislativní politice; uchování více kopií vyžaduje hlídání místa. Obnovu opakovat alespoň čtvrtletně a po významné změně schématu. Nikdy neřešit plný disk příkazem docker volume prune.

## Izolovaná obnova

Obnovujte pouze důvěryhodné vlastní archivy. Age chrání šifrovaný obsah před poškozením, ale veřejný recipient není digitální podpis původu; kdokoli s veřejným klíčem může vytvořit jiný archiv. Pg_restore umí spustit SQL ze zálohy, proto ochrana přístupu k archivům a nezávislé ověření původu zůstávají nutné.

Obnovovací nástroj vyžaduje nový název tanklog_restore_* a odmítne existující DB. Před vytvořením cíle dešifruje s velikostním limitem, povolí pouze dva běžné soubory bez cest/odkazů a ověří součet dumpu. Pg_restore --single-transaction --exit-on-error, bez --clean. Po obnově zkontroluje všechny otisky, řádky, přílohy a migrační záznamy. Případný neúspěšný nový cíl zůstane pro kontrolu; žádná existující DB se nemaže. Zdrojový server může mezitím zapisovat; jeho pozdější změny nepatří do obnoveného snapshotu.

S funkčním místním Dockerem:

```sh
python3 infra/ops/restore_compose.py --archive /absolutni/cesta/backup.tar.age --identity /absolutni/cesta/identity.key
# Pouze pro archiv vytvořený níže uvedeným syntetickým drill.py přidejte --synthetic-check.
```

Pomocník povolí pouze lokální Unix Docker socket, vytvoří nové náhodné jméno projektu, samostatný nový restore_data svazek a nové role/secrets. Používá výhradně compose.restore.yaml, bez veřejných portů, webu a NPM sítě. Soukromý klíč připojí jen read-only do jednorázové operations služby pod UID/GID volajícího. Aplikační kontrola používá omezenou roli, bootstrap klíče nejsou v backendu. Provede shodu dumpu/DB, migrate --check a Django check; API/login s reálnými účty musí v obnoveném prostředí ověřit provozovatel. Po skončení zastaví pouze vlastní kontejnery/sítě, svazek i chráněná testovací konfigurace zůstanou zachované. Žádné down -v/prune.

## Skutečně provedené nativní cvičení

Na tomto Macu s PG 18.6 na loopback portu 55432, backend/.venv a age 1.3.2:

```sh
TANKLOG_DRILL=1 POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python ../infra/ops/drill.py
```

Založí pouze novou zdrojovou syntetickou DB. Připraví 3 účty, sdílení, 3 tankování a 3 účtenky/náhledy; ověří zálohu i při souběžné změně po snapshotu. Vytvoří **nový fyzický cluster** ve vlastním .runtime adresáři, vygeneruje nová hesla a obnoví do něj novou DB s omezenou aplikační rolí. Ověří skutečný API login/CSRF/Secure cookie, binární originál i náhled, oprávnění a součty 45 l / 1800 Kč / 7,50 l/100 km. Zkusí chybný klíč, poškozený ciphertext a opakovanou obnovu do existující DB. Po skončení svůj nový cluster zastaví, datový adresář ani DB nesmaže. Původní PostgreSQL a náhled zůstávají běžet.

Soukromý **testovací** klíč a výsledky jsou jen v ignorovaném .runtime, nejsou produkční recovery materiál. Cvičení vytváří nové DB při každém průchodu; bez dalšího pokynu je nemaže. Potřebuje místní oprávnění založit syntetickou DB a pg_dump/pg_restore/initdb/pg_ctl 18.6 na PATH. Není to obnova do Docker volumes ani kopie mimo hostitele. Přesné měření a omezení v PHASE_7.md.

## Migrace, vydání a rollback před budoucím schváleným nasazením

1. Zaznamenat plný commit, digesty obou aplikačních images, verze nástrojů, stav migrací, role/porty/sítě a vlastníka provozu. Vyřešit neprovedenou GitHub/CI akceptaci fáze 6. Ověřit restore stejné verze a připravit údržbové okno.
2. Zkontrolovat plán migrací na kopii; zajistit úspěšnou šifrovanou off-host zálohu a její recovery klíč mimo hostitele. Uložit oddělenou šifrovanou konfiguraci.
3. Teprve po konkrétní autorizaci zastavit zápisy, pořídit cutover snapshot a provést migrace jedním řízeným procesem. Nespouštět migrace automaticky při každém startu Gunicorn workeru.
4. Ověřit check --deploy se skutečnou konfigurací, HTTPS, CSRF, přístupy, účtenky, statistiky a restart bez mazání volumes. Zapsat časy a výsledky. Vnější NPM limit musí propustit receipt request do 12 MiB a běžné API do 1 MiB, aby vnitřní proxy mohla vrátit JSON chybu.
5. Rollback pouze images je přípustný jen při doložené kompatibilitě nového schématu se starým kódem. Jinak obnovit schválený snapshot do **nového izolovaného projektu**, porovnat součty/přílohy/práva a vědomě rozhodnout o ztrátě zápisů od snapshotu. Přepnutí routy/dat až po samostatném schválení; existující produkční svazky uchovat. Neprovádět automatický pg_restore --clean přes produkci.

## Oficiální zdroje a zámky

Ověřeno 3. 11. 2026: [pg_dump 18 a sdílený snapshot](https://www.postgresql.org/docs/18/app-pgdump.html), [pg_restore 18](https://www.postgresql.org/docs/18/app-pgrestore.html), [age v1.3.2](https://github.com/FiloSottile/age/releases/tag/v1.3.2), [uv v Dockeru](https://docs.astral.sh/uv/guides/integration/docker/), [Compose sítě](https://docs.docker.com/compose/how-tos/networking/), [systemd.timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html). Age release metadata poskytla SHA-256 pro oba Linux archivy; manifest GHCR poskytl připnutý uv digest. Aplikační uv.lock a package-lock.json se v této etapě nemění.
