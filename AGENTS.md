# Pravidla práce na TankLog

- Komunikuj česky. Uživatelské texty, komentáře a projektovou dokumentaci piš česky; technické identifikátory mohou být anglicky.
- Aktuálně je uživatelem povolena fáze 1: lokální základ, Docker, databáze, autentizace a uživatelé. Fázi 2 ani další nezačínej bez samostatného pokynu. Schválení výsledku samo není pokynem k další implementaci.
- Přečti README a relevantní dokumenty v `docs/`. Udržuj specifikaci, API, model a rozhodnutí ve shodě. Návrhy neoznačuj za hotové funkce.
- Pracuj postupně podle `docs/ROADMAP.md`. Nepřepisuj funkční části bez potřeby. Preferuj jednoduchý modulární monolit.
- Zachovej React/TypeScript/Vite a Django/DRF/PostgreSQL, jeden origin a `/api/`, serverové sessions a CSRF. Žádné JWT v localStorage, veřejná registrace ani veřejný port databáze.
- Veškerá trvalá aplikační data včetně profilů, motivu, budoucích příloh a jejich náhledů ukládej do PostgreSQL. Cookies slouží jen přihlášení/CSRF; data a nastavení nesmějí záviset na prohlížeči. Používej neutrální modrou, šedou a bílou paletu podle UI_UX. Citlivá provozní konfigurace zůstává v prostředí podle bezpečnostních pravidel.
- Backend v každém požadavku ověřuje aktivní účet, omezení session a práva k objektu. Totéž platí pro seznamy, agregace, exporty a přílohy. Sdílená auta se nekopírují.
- Pro peníze a palivo používej Decimal. Výpočty patří do samostatné servisní vrstvy podle `docs/CONSUMPTION.md`. Nejdříve připrav a spusť příslušné testy s očekávanými výsledky.
- Závislosti při implementaci ověř v oficiálních zdrojích a uzamkni v lock souborech. Tajné hodnoty načítej z prostředí; žádné skutečné účtenky, dumpy nebo přístupové údaje do Gitu ani logů.
- Bez výslovného souhlasu nevytvářej vzdálený repozitář, nepushuj, nenasazuj, nemaž databázi ani volumes, nepřepisuj produkční data a neprováděj nucené Git operace.
- Lokální commity jsou součástí dokončení etap. Přidávej jen zamýšlené soubory. Po etapě aktualizuj dokumentaci, proveď odpovídající kontroly, připrav commit a uveď soubory, skutečné výsledky, ruční ověření i omezení. Potom se zastav.
- Test označ za úspěšný pouze po skutečném provedení. Chybějící Docker nebo jiné nástroje přiznej a uveď ověřitelné příkazy; nenahrazuj je tvrzením o úspěchu.
