// Veřejný allowlist vzniká z buildu, žádné API, uživatelské URL ani odpovědi s cookies.
import { createHash } from "node:crypto";
import { readFile, readdir, writeFile } from "node:fs/promises";
const dist = new URL("../dist/", import.meta.url);
const assets = (await readdir(new URL("assets/", dist))).map(
  (name) => `/assets/${name}`,
);
const files = [
  ...assets,
  "/offline.html",
  "/offline.css",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/maskable-512.png",
  "/icons/tanklog.svg",
  "/icons/apple-touch-icon.png",
];
const hash = createHash("sha256");
for (const file of files)
  hash.update(await readFile(new URL(file.slice(1), dist)));
const template = await readFile(
  new URL("./worker.js", import.meta.url),
  "utf8",
);
hash.update(template);
await writeFile(
  new URL("sw.js", dist),
  template
    .replace("__VERSION__", hash.digest("hex").slice(0, 16))
    .replace("__PUBLIC_FILES__", JSON.stringify(files)),
);
