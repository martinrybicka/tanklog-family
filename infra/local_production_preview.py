"""Lokální HTTPS náhled buildu. Backend na 8001 spouštějte jen nad syntetickou *_e2e DB."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
runtime = root / ".runtime" / "production-preview"
runtime.mkdir(parents=True, exist_ok=True)
nginx = shutil.which("nginx")
if not nginx:
    raise SystemExit(
        "Chybí nginx. Použijte Docker nebo nainstalujte místní nginx pro tento test."
    )
if not (root / "frontend/dist/sw.js").exists():
    raise SystemExit("Nejdříve sestavte frontend: npm run build --prefix frontend.")
cert, key = runtime / "certificate.pem", runtime / "private.key"
if not cert.exists():
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "3",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    key.chmod(0o600)
source = root / "infra/nginx"
proxy = (
    (source / "proxy-api.conf")
    .read_text()
    .replace("http://backend:8000", "http://127.0.0.1:8001")
)
headers = source / "security-headers.conf"
proxy = proxy.replace("/etc/nginx/tanklog/security-headers.conf", str(headers))
(runtime / "proxy-api.conf").write_text(proxy)
app = (
    (source / "production.conf.template")
    .read_text()
    .replace("${NPM_TRUSTED_CIDR}", "127.0.0.1/32")
    .replace("listen 8080;", "listen 127.0.0.1:8082;")
    .replace("/usr/share/nginx/html", str(root / "frontend/dist"))
    .replace("/etc/nginx/tanklog/security-headers.conf", str(headers))
    .replace("/etc/nginx/tanklog/proxy-api.conf", str(runtime / "proxy-api.conf"))
)
mime_candidates = [
    Path(value)
    for value in [
        os.environ.get("NGINX_MIME_TYPES", ""),
        "/opt/homebrew/etc/nginx/mime.types",
        "/etc/nginx/mime.types",
    ]
    if value
]
mime_file = next((path for path in mime_candidates if path.is_file()), None)
if mime_file is None:
    raise SystemExit("Nastavte NGINX_MIME_TYPES na místní soubor mime.types.")
config = f"""pid {runtime / "nginx.pid"};
error_log {runtime / "nginx-error.log"};
events {{ worker_connections 256; }}
http {{
    include {mime_file};
    default_type application/octet-stream;
    access_log off;
    include {source / "common-http.conf"};
    {app}
    server {{
        listen 127.0.0.1:8443 ssl;
        server_name localhost;
        ssl_certificate {cert};
        ssl_certificate_key {key};
        ssl_protocols TLSv1.2 TLSv1.3;
        client_max_body_size 16m;
        location / {{
            proxy_pass http://127.0.0.1:8082;
            proxy_set_header Host $http_host;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Real-IP $remote_addr;
        }}
    }}
    server {{ listen 127.0.0.1:8083; return 308 https://localhost:8443$request_uri; }}
}}
"""
config_path = runtime / "nginx.conf"
config_path.write_text(config)
subprocess.run([nginx, "-t", "-c", str(config_path)], check=True)
if "--check" in sys.argv:
    raise SystemExit(0)
print(
    "Produkční náhled: https://localhost:8443 (místní testovací certifikát).",
    flush=True,
)
os.execv(nginx, [nginx, "-c", str(config_path), "-g", "daemon off;"])
