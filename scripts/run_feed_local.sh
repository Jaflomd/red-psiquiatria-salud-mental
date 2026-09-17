#!/bin/bash
# Rutina diaria del feed, corriendo en la Mac de Javier (no en GitHub Actions).
# La lanza launchd: ~/Library/LaunchAgents/com.jaflo.redpsm.feed.plist
#
# Pasos: sincroniza con GitHub, consulta Europe PMC + PubMed de los últimos
# días, reconstruye data/summaries.json y, si hay cambios, hace commit y push.
# GitHub Pages republica el sitio solo al recibir el push.
#
# Uso manual:  bash scripts/run_feed_local.sh [días]     (por defecto 2)

set -u
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export LANG="es_ES.UTF-8"

# La raíz es la carpeta que contiene a scripts/, así que el mismo archivo sirve
# en la copia de iCloud y en la copia de trabajo de launchd (~/repos/...).
# launchd NO puede leer iCloud ("Operation not permitted"): el agente diario
# usa la copia de ~/repos.
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DAYS="${1:-2}"
GH_CRED='!gh auth git-credential'

cd "$PROJ" || { echo "no existe el proyecto: $PROJ"; exit 1; }

echo "=== $(date '+%F %H:%M:%S') inicio (ventana: $DAYS días)"

# El repo puede haber cambiado desde otra sesión o desde GitHub.
if ! git -c "credential.helper=$GH_CRED" pull --rebase --autostash -q origin main; then
  echo "ERROR: git pull falló; no se toca nada"
  exit 1
fi

if ! python3 scripts/fetch_daily.py --days "$DAYS"; then
  echo "ERROR: fetch_daily falló; los datos previos quedan intactos"
  exit 1
fi

if ! python3 scripts/build_summaries.py --verify-oa; then
  echo "AVISO: build_summaries reportó errores (revisa arriba); no se publica"
  exit 1
fi

git add data/
if git diff --cached --quiet; then
  echo "sin cambios: nada que publicar"
  echo "=== $(date '+%F %H:%M:%S') fin"
  exit 0
fi

git commit -q -m "feed: $(date +%F)"
if git -c "credential.helper=$GH_CRED" push -q origin main; then
  echo "publicado: $(git log --oneline -1)"
else
  echo "ERROR: push falló; el commit quedó local"
  exit 1
fi

echo "=== $(date '+%F %H:%M:%S') fin"
