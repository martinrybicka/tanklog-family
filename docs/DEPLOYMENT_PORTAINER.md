# Ověřené nasazení rodinné verze – 6. 11. 2026

Veřejný repozitář: https://github.com/martinrybicka/tanklog-family (větev main).

Portainer stack `tanklog-family` je nasazený na DOCKER01. PostgreSQL, Django backend a nginx frontend byly skutečně ověřené ve stavu healthy. Publikovaný je pouze webový TCP port **8088**; databáze ani backend nemají publikovaný port. Používá se vlastní nově vytvořený svazek PostgreSQL a samostatná aplikační DB role.

Kontrola před předáním: 0 uživatelů, 0 aut, 0 tankování, 0 rozpracovaných účtenek, úvodní nastavení neprovedené. Endpoint úvodního nastavení přes backend i web vrací `available: true`. Tesseract v produkčním kontejneru skutečně hlásí 5.5.4. Nebyl vytvořen testovací ani výchozí administrátor.

Nginx Proxy Manager: doména `tankovani.mrybicka.com`, přeposílání HTTP na DOCKER01:8088, vlastní SSL certifikát a Force SSL. Pro fotografie nastavte v Advanced `client_max_body_size 12m;`. Správu DNS/NPM provádí uživatel; samotný zdravý stack nepotvrzuje funkčnost veřejného HTTPS.

Po otevření veřejné HTTPS adresy se automaticky nabídne První spuštění. Uživatel zvolí vlastní jméno/heslo správce a vloží jednorázový kód z Portainer → stack tanklog-family → Environment → TANKLOG_SETUP_TOKEN. Kód není v Gitu, není předvyplněný v aplikaci a po vytvoření prvního účtu jej už nelze použít. Poté jej lze odstranit z prostředí stacku. Žádné testovací přihlašovací údaje v produkci neplatí.

Image 0.9.0 byly skutečně sestavené na DOCKER01. Vzdálený BuildKit přes Portainer Edge měl protokolovou chybu; proto je build oddělený do compose.build.yaml a Portainer používá image-only compose.portainer.yaml bez sestavování a bez pullu z registru. Pro další sestavení použijte oba soubory podle README, stejné jméno tagu nastavte do prostředí Portaineru. Staré databázové svazky nemažte.

Lokální kontroly před vydáním: 240 backendových testů prošlo (46,32 s), 30 frontendových testů prošlo, lint/typecheck/build/OpenAPI prošly. Úvodní instalace má testy CSRF, jednorázového kódu, prvního ADMIN, uzavření a zamezení opětovného otevření. Tajné hodnoty kontroloval Gitleaks před zveřejněním celé historie. Produkční vytvoření prvního správce se záměrně neprovedlo, aby účet vytvořil vlastník.

Off-host automatické zálohy ani živé VIN propojení nejsou tímto nasazením nastavené. Veškerá uložená aplikační data jsou v PostgreSQL; svazek sám není záloha. Přístupové údaje se do tohoto dokumentu neukládají.
