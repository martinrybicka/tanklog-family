"""Omezené klienty pevných veřejných zdrojů, bez redirectů a logování payloadů."""

import http.client
import ipaddress
import json
import re
import socket
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit

from django.conf import settings

from apps.core.errors import Problem

HOSTS = {"api.dataovozidlech.cz", "commons.wikimedia.org", "upload.wikimedia.org"}


def fetch(url, headers=None, maximum=1024 * 1024):
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise Problem("unsafe_source", "Zdroj není povolený.", 400) from error
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise Problem("unsafe_source", "Zdroj není povolený.", 400)
    connection = None
    try:
        if any(
            not ipaddress.ip_address(value[4][0]).is_global
            for value in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        ):
            raise Problem("unsafe_source", "Zdroj není veřejný.", 502)
        connection = http.client.HTTPSConnection(parsed.hostname, timeout=5)
        connection.request(
            "GET",
            parsed.path + ("?" + parsed.query if parsed.query else ""),
            headers=headers or {},
        )
        response = connection.getresponse()
        if response.status == 429:
            raise Problem(
                "provider_limited",
                "Zdroj nyní omezuje požadavky. Zkuste to později.",
                429,
            )
        if response.status != 200:
            raise Problem(
                "provider_unavailable",
                "Externí zdroj není dostupný. Ruční zadání zůstává možné.",
                502,
            )
        data = response.read(maximum + 1)
        if len(data) > maximum:
            raise Problem("provider_too_large", "Odpověď zdroje je příliš velká.", 502)
        return data
    except (OSError, ValueError, http.client.HTTPException) as error:
        raise Problem(
            "provider_unavailable",
            "Externí zdroj neodpovídá. Zkuste ruční zadání.",
            502,
        ) from error
    finally:
        if connection:
            connection.close()


def fetch_json(url, headers=None):
    data = fetch(url, headers)
    try:
        return json.loads(data)
    except (ValueError, UnicodeDecodeError) as error:
        message = data.decode("utf-8", errors="replace").lower()
        if "požadav" in message and ("maxim" in message or "limit" in message):
            raise Problem(
                "provider_limited",
                "Zdroj nyní omezuje počet dotazů. Zkuste to později.",
                429,
            ) from error
        raise Problem("provider_invalid", "Zdroj vrátil neplatná data.", 502) from error


def map_rsv(payload, vin):
    if not isinstance(payload, dict):
        raise Problem("provider_invalid", "Zdroj nevrátil platný objekt údajů.", 502)
    message = str(payload.get("Message", payload.get("Error", ""))).lower()
    if "limit" in message or ("maxim" in message and "požadav" in message):
        raise Problem("provider_limited", "Zdroj nyní omezuje počet dotazů.", 429)
    if "klíč" in message or "key" in message:
        raise Problem("provider_unavailable", "Zdroj odmítl přístup. Kontaktujte správce.", 502)
    data = payload.get("Data")
    if payload.get("Status") != 1 or not isinstance(data, dict) or not data:
        raise Problem("vin_not_found", "VIN nebyl nalezen nebo zdroj dotaz odmítl.", 404)
    if str(data.get("VIN", "")).strip().upper() != vin:
        raise Problem("provider_invalid", "Zdroj nevrátil shodný VIN.", 502)
    result = {}
    for raw, field in [("TovarniZnacka", "make"), ("ObchodniOznaceni", "model")]:
        value = str(data.get(raw) or "").strip()
        if value and value != "." and len(value) <= 100:
            result[field] = value
    volume = str(data.get("MotorZdvihObjem") or "")
    if volume.isdecimal() and 0 < int(volume) <= 2147483647:
        result["engine_displacement_cc"] = int(volume)
    power = str(data.get("MotorMaxVykon") or "").replace(",", ".")
    if re.fullmatch(r"\d+(\.\d{1,2})?", power) and 0 < Decimal(power) < 1000000:
        result["power_kw"] = f"{Decimal(power):.2f}"
    fuel = str(data.get("Palivo") or "").upper().strip()
    if "+" in fuel or "/" in fuel:
        fuel = ""
    if fuel.startswith(("BA", "BENZ")):
        result["fuel_type"] = "PETROL"
    elif fuel.startswith(("NM", "NAFTA")):
        result["fuel_type"] = "DIESEL"
    elif fuel == "LPG":
        result["fuel_type"] = "LPG"
    elif fuel == "CNG":
        result["fuel_type"] = "CNG"
    elif fuel in ["ELEKTŘINA", "EL"]:
        result["fuel_type"] = "ELECTRIC"
    # První registrace není rok výroby; složený výkon a spotřeba nejsou jedno číslo.
    return result


def rsv(vin):
    if not settings.RSV_API_KEY:
        raise Problem(
            "provider_not_configured",
            "Dohledání VIN zatím nemá nastavený API klíč. Vyplňte auto ručně.",
            503,
        )
    payload = fetch_json(
        "https://api.dataovozidlech.cz/api/vehicletechnicaldata/v2?" + urlencode({"vin": vin}),
        {"API_KEY": settings.RSV_API_KEY},
    )
    if not isinstance(payload, dict):
        raise Problem("provider_invalid", "Neplatná odpověď registru.", 502)
    return payload, map_rsv(payload, vin)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = []

    def handle_data(self, data):
        self.values.append(data)


def plain(value):
    parser = PlainText()
    parser.feed(str(value or ""))
    return "".join(ch for ch in " ".join("".join(parser.values).split()) if ch.isprintable())[:10000]


LICENSES = {
    "https://creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
    "https://creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
    "https://creativecommons.org/licenses/by-sa/4.0/": "CC BY-SA 4.0",
}


def commons(make, model):
    agent = settings.COMMONS_USER_AGENT
    if not agent:
        raise Problem(
            "provider_not_configured",
            "Fotografie vyžadují nastavený kontakt provozovatele pro Wikimedia API.",
            503,
        )
    query = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f'"{make}" "{model}" filetype:bitmap',
        "gsrnamespace": "6",
        "gsrlimit": "3",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime|timestamp|sha1",
        "iiurlwidth": "1000",
    }
    payload = fetch_json(
        "https://commons.wikimedia.org/w/api.php?" + urlencode(query),
        {"User-Agent": agent},
    )
    result = []
    for page in payload.get("query", {}).get("pages", {}).values():
        info = page.get("imageinfo", [{}])[0]
        meta = info.get("extmetadata", {})
        license_url = plain(meta.get("LicenseUrl", {}).get("value")).replace("http://", "https://")
        if license_url.rstrip("/") + "/" not in LICENSES:
            continue
        license_url = license_url.rstrip("/") + "/"
        author = plain(meta.get("Artist", {}).get("value"))
        credit = plain(meta.get("Credit", {}).get("value"))
        attribution = plain(meta.get("Attribution", {}).get("value"))
        if len(author) > 1000 or len(credit) > 2000 or len(attribution) > 2000:
            continue
        source = info.get("descriptionurl", "")
        image = info.get("thumburl", info.get("url", ""))
        parsed = urlsplit(source)
        if (
            not author
            or parsed.scheme != "https"
            or parsed.hostname != "commons.wikimedia.org"
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/wiki/File:")
        ):
            continue
        if urlsplit(image).hostname != "upload.wikimedia.org":
            continue
        result.append(
            {
                "url": image,
                "source": source,
                "author": author,
                "credit": credit,
                "attribution": attribution,
                "source_timestamp": info.get("timestamp", ""),
                "source_sha1": info.get("sha1", ""),
                "license": LICENSES[license_url],
                "license_url": license_url,
                "title": plain(page.get("title")),
                "modified": "Zmenšení a očištěný náhled; ilustrační fotografie.",
            }
        )
    return result
