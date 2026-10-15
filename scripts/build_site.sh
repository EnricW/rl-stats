#!/usr/bin/env bash
# Construye la web estática en _site/ (site/ + data/), con cache-busting:
# los assets propios se versionan con el SHA del commit para que el navegador
# no sirva CSS/JS viejos tras un deploy. Lo usan ingest.yml y deploy.yml
# (antes cada uno llevaba su copia del bloque y se desviaban).
set -euo pipefail

sha="${GITHUB_SHA:-local-$(date +%s)}"
v="${sha:0:8}"

rm -rf _site
mkdir -p _site
cp -r site/* _site/
cp -r data _site/data

# Versiona las referencias a assets propios en HTML y también los imports
# relativos dentro de los módulos JS (pages/*.js importa ../app.js).
# El lookahead evita re-versionar algo que ya lleva ?v=.
find _site -maxdepth 2 \( -name "*.html" -o -name "*.js" \) \
  -exec perl -pi -e "s/(styles\.css|app\.js|viewer\.js|pages\/[a-z]+\.js)(?![?\w])/\$1?v=$v/g" {} +

echo "build_site: _site listo (v=$v)"
