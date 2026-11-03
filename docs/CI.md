# CI – lokální příprava fáze 6

Stav 3. 11. 2026: workflow je připravený a lokálně kontrolovaný. Nic nebylo odesláno na GitHub; soukromý repozitář ani úspěšný vzdálený běh zatím neexistují. Výsledky jsou v [PHASE_6.md](PHASE_6.md). Následující příkazy nic nepublikují.

## Připravené úlohy

| Úloha | Kontroly |
| --- | --- |
| repository | Celá historie, zakázané datové cesty/ignore, Gitleaks, actionlint, politika oprávnění a její regrese |
| backend | PostgreSQL 18.6, frozen uv lock, Ruff, pytest, migrace, Django check, shoda OpenAPI, check --deploy |
| frontend | npm ci, Oxlint, Vitest, TypeScript/Vite/PWA build, Prettier |
| containers | Dev/prod/CI Compose config, produkční Docker build, migrace a 22 HTTP E2E scénářů ve vlastním projektu |

Backend/frontend následují po auditu, kontejnery až po obou. Workflow reaguje na PR, push do main a ruční spuštění; má contents:read a neponechává checkout credentials. Akce jsou uzamčené úplnými SHA. Nenahrává ani chybové trace/screenshoty, nemá secrets kontext, deploy nebo produkční prostředí. Případná chyba proto vyžaduje opakování lokálně. Zrušený runner uvolní GitHub; lokální kontejnerový pomocník uklízí pouze vlastní kontejnery/sítě, svazek zachová. Není to nástroj pro produkční provoz.

## Lokální kontroly

Z kořene projektu; vyžaduje uv 0.13.6, Python 3.14.10 a Node 26.13.0 na PATH. Závislosti instalujte z existujících locků:

```sh
uv sync --frozen --project backend
(cd frontend && npm ci)
python3 infra/setup_env.py
backend/.venv/bin/python infra/ci/verify_workflow.py
backend/.venv/bin/python infra/ci/check_repository.py
backend/.venv/bin/python -m unittest discover -s infra/ci/tests -v
python3 infra/ci/run_checks.py frontend
python3 infra/verify_compose.py
```

`setup_env.py` nepřepisuje existující .env. `verify_compose.py` vyžaduje Docker Compose plugin, ale nepotřebuje daemon. Na tomto Macu lze použít `COMPOSE_COMMAND=.tools/docker-compose python3 infra/verify_compose.py`.

Instalace kontrolních CLI na CI Linux x64: `python3 infra/ci/install_tools.py` ověří SHA-256 archivů před použitím a připraví `.tools/ci/actionlint` a `.tools/ci/gitleaks`. Na macOS byly použity stejné verze z Homebrew (actionlint 1.7.12, gitleaks 8.30.1). Pak:

```sh
actionlint
gitleaks git --redact --no-banner .
```

### Oddělená nativní backendová DB

Vyžaduje běžící místní PostgreSQL 18 a .env s oprávněním založit testovací DB. Nikdy nepoužívejte produkční údaje. Pomocník odmítne vzdálený host i již existující cílovou DB. Jednou založte novou `tanklog_phase6_ci` (při dalším nezávislém ověření zvolte jiné jméno končící `_ci`):

```sh
TANKLOG_CI=1 POSTGRES_DB=tanklog_phase6_ci POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/backend_command.py .venv/bin/python ../infra/ci/database.py
TANKLOG_CI=1 POSTGRES_DB=tanklog_phase6_ci POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 python3 infra/ci/run_checks.py backend
```

Druhý příkaz lze opakovat nad toutéž vyhrazenou CI DB. Běžná DB se nemění. Runner migruje tuto syntetickou DB; pytest používá vlastní testovací DB a běžně ji spravuje. Port 55432 je místní instance tohoto Macu; jinde změňte na skutečný loopback port. Pokud uv není na PATH, nastavte `UV_COMMAND="$PWD/.tools/python/bin/uv"`. Check --deploy záměrně přijme jen existující security.W004 (HSTS=0 dle ADR-027); ostatní varování/chyby musí selhat.

### Izolované kontejnery a E2E

Vyžaduje funkční **místní** Docker Engine/Compose a Node závislosti. Pomocník odmítne vzdálené Docker endpointy. Port 18080 musí být volný:

```sh
(cd frontend && npx playwright install --with-deps chromium)
python3 infra/ci/containers.py
```

Pomocník vytvoří náhodný projekt tanklog-ci-*, vlastní .runtime/*/config.env s právy 600 a náhodnými secrets; base+CI konfigurace používá nový databázový svazek. Spustí migrace a výslovně chráněný syntetický E2E účet. Nikdy nepřipojuje produkční NPM síť, nedělá down -v/prune a nemaže existující svazky. Po skončení zastaví vlastní kontejnery/sítě. Zachovaný CI svazek může zabírat místo; jeho odstranění není součást automatizace ani této autorizace. Testy používají odpovídající Playwright Chromium, žádný systémový Chrome není nutný. HTTPS/PWA produkční scénáře jsou v tomto HTTP jobu výslovně vynechané; samostatný lokální postup zůstává v PHASE_5.md.

### Čistý export bez lokálních závislostí

`python3 infra/ci/clean_export.py` exportuje pouze HEAD do nového dočasného adresáře mimo pracovní strom; `--index` exportuje připravené změny. Neobsahuje .git ani ignorované .env/.venv/node_modules, a proto se v něm nespouští audit historie. Cestu vypíše na stdout. V exportu proveďte frozen instalace a stejné kontroly podle této stránky, vygenerujte nové .env a nastavte vlastní syntetickou DB. Nepřenášejte běžná aplikační data. Export zde byl skutečně ověřený na macOS/ARM64; není totožný s Ubuntu/x64 runnerem.

## Neprovedená vzdálená akceptace

Teprve po samostatném výslovném povolení GitHubu lze znovu provést audit, založit skutečně private repozitář, ověřit viditelnost, provést autorizovaný push a doložit odkazy/stav všech čtyř úloh na čistém runneru. Následně zkontrolovat nastavení oprávnění a případných secrets; produkční credentials nejsou potřebné. Žádný z těchto kroků zatím nebyl proveden. Fáze 7 vyžaduje další samostatný pokyn.

## Ověřené oficiální zdroje verzí

Ověřeno 3. 11. 2026 proti oficiálním tagům/commitům a release metadatům. Při změně verze znovu ověřte zdroj, SHA a checksum, nespouštějte automaticky pohyblivý tag:

- [GitHub Actions – bezpečné použití](https://docs.github.com/en/actions/reference/security/secure-use)
- [checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1), [setup-node v7.1.0](https://github.com/actions/setup-node/releases/tag/v7.1.0), [setup-uv v10.3.3](https://github.com/astral-sh/setup-uv/releases/tag/v10.3.3)
- [Gitleaks v8.30.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1), [actionlint v1.7.12](https://github.com/rhysd/actionlint/releases/tag/v1.7.12)
- [Playwright – odpovídající prohlížeče](https://playwright.dev/docs/browsers)

## Doplnění lokální části fáze 7

Backend kontrola nyní zahrnuje infra/ops a 10 provozních regresí. Kontejnerová úloha připravuje také build operations image; statická kontrola pokrývá dev/prod/CI/operations/restore Compose. Nové produkční bootstrap proměnné pro config kontrolu jsou výhradně syntetické a nevypisují se. Reálný Linux image, Docker restore a GitHub běh se zatím neprovedly. Nativní měření a provozní předpoklady viz PHASE_7.md a OPERATIONS.md.
