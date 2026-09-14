# Red de Investigación de Psiquiatría y Salud Mental

Prototipo de sitio estático (sin build, sin frameworks) para Javier Flores, psiquiatra e investigador peruano. El sitio combina:

1. **Resúmenes curados** en español de papers que Javier considera relevantes.
2. Un **feed diario automático** de papers nuevos de psiquiatría y salud mental que sean **open access** en Europe PMC.

Ver `POLITICA-EDITORIAL.md` para el criterio exacto de acceso abierto y de inclusión, y la spec del proyecto para el detalle técnico completo.

## 1. Requisitos

- Python 3.12 (solo librería estándar; el proyecto no usa `pip install`).
- Node solo se usa para `node --check assets/app.js` como verificación, no hay build con npm.
- Ningún paquete de terceros. Todo el pipeline y el frontend corren tal cual, sin instalar nada.

## 2. Ver el sitio en local

```bash
cd "red-psiquiatria-salud-mental"
python3 -m http.server 8742
```

Abrir `http://localhost:8742/`. Rutas disponibles (routing por hash, no hace falta configurar el servidor):

- `#/` — Inicio
- `#/papers` — redirige al último día del feed
- `#/papers/YYYY-MM-DD` — papers de un día concreto
- `#/resumenes` — lista de resúmenes curados, con búsqueda y filtros
- `#/resumenes/<slug>` — detalle de un resumen
- `#/acerca` — acerca del sitio y criterios de acceso abierto

Si abres `index.html` directamente desde el disco (`file://`) en vez de por el servidor, la carga de datos falla: los navegadores bloquean `fetch` sobre archivos locales. Usa siempre `python3 -m http.server 8742`.

## 3. Estructura de carpetas

```
index.html, favicon.svg, assets/        → frontend
content/                                → resúmenes curados y copy del sitio (site.json)
data/                                   → generado por los scripts; no se edita a mano
scripts/                                → pipeline en Python (sin dependencias)
tests/                                  → pruebas offline del pipeline
dist/snapshot.html                      → instantánea autocontenida (gitignored), generada
.github/workflows/                      → feed diario (cron) y despliegue a GitHub Pages
```

## 4. Scripts del pipeline

Todos se corren desde la raíz del proyecto con `python3 scripts/<nombre>.py`. Códigos de salida en todos los scripts: `0` correcto · `1` fallo de red/API (no toca datos previos) · `2` rechazo o error de validación · `3` falta configuración (por ejemplo, `--summarize` sin `ANTHROPIC_API_KEY`) · `4` el archivo de destino ya existe · `5` error inesperado.

### 4.1 `fetch_daily.py` — trae los papers del día desde Europe PMC

```bash
python3 scripts/fetch_daily.py [--days N] [--date YYYY-MM-DD] [--summarize] [--max-ai N] [--model M] [--dry-run] [--config scripts/feed_config.json] [--data-dir data] [--quiet]
```

- Sin argumentos, trae los últimos 2 días (ayer y hoy, hora de Lima).
- `--days 7` trae una semana hacia atrás (útil para backfill la primera vez).
- `--date 2026-09-10` trae solo ese día.
- `--summarize` genera además resúmenes en español con IA (ver sección 7); requiere `ANTHROPIC_API_KEY`.
- `--dry-run` muestra los conteos sin escribir nada en `data/`.
- Correrlo dos veces seguidas dejando los mismos archivos (salvo las marcas de tiempo) es intencional: el script es idempotente.

### 4.2 `add_paper.py` — crea la plantilla de un resumen curado a partir de un DOI/PMID/PMCID

```bash
python3 scripts/add_paper.py <DOI|PMID|PMCID|PPRID> [--slug S] [--title T] [--tags a,b] [--design ID] [--sample-size N] [--date YYYY-MM-DD] [--out-dir content/summaries] [--force] [--dry-run] [--summarize] [--model M]
```

- Verifica el artículo en Europe PMC. Si no es acceso abierto con licencia declarada (ver `POLITICA-EDITORIAL.md`), **rechaza con código 2** y explica el motivo; no crea el archivo.
- `--slug` recibe solo la parte descriptiva del nombre (sin la fecha): el archivo final es `content/summaries/YYYY-MM-DD-<slug>.md`.
- Sin `--tags`/`--design`, los detecta automáticamente a partir del título y el resumen (heurística; conviene revisarlos).
- `--summarize` (opcional, requiere `ANTHROPIC_API_KEY`) rellena las 6 secciones con un borrador de IA en vez de dejarlas en `[[PENDIENTE]]`, y marca `ai_draft: true`.
- `--dry-run` imprime el archivo completo sin escribirlo.

### 4.3 `build_summaries.py` — valida los `.md` de `content/summaries/` y genera `data/summaries.json`

```bash
python3 scripts/build_summaries.py [--src content/summaries] [--out data/summaries.json] [--check] [--verify-oa] [--skip-invalid] [--include-drafts]
```

- `--check` solo valida el formato, no escribe nada.
- `--verify-oa` además revalida en vivo contra Europe PMC que cada artículo sigue siendo acceso abierto con licencia y que no fue retractado; es la variante que se usa antes de publicar.
- Con errores de formato, no escribe `data/summaries.json` y sale con código 2 (salvo `--skip-invalid`, que escribe los válidos y avisa de los que dejó fuera).
- Por defecto, un borrador (`status: draft`) que no sea `example: true` no se incluye en `data/summaries.json` (para que un borrador real a medio escribir de Javier no se publique por accidente). Los 4 resúmenes de ejemplo de este prototipo llevan `example: true`, así que sí se incluyen aunque sigan en `draft`. `--include-drafts` fuerza incluir también los borradores no marcados como ejemplo (uso local, para previsualizar).

### 4.4 `summarize_ai.py` — genera un resumen en español con IA para un día del feed

```bash
python3 scripts/summarize_ai.py --input data/daily/2026-09-13.json [--limit 20] [--model M] [--dry-run]
```

Normalmente no se corre suelto: `fetch_daily.py --summarize` ya lo invoca. Sirve para reprocesar un día puntual. `--dry-run` imprime el prompt del primer artículo sin llamar a la API.

### 4.5 `build_snapshot.py` — genera `dist/snapshot.html`, una instantánea autocontenida

```bash
python3 scripts/build_snapshot.py [--days 3] [--max-items 40] [--abstract-chars 700] [--out dist/snapshot.html] [--root .]
```

Empaqueta el HTML, el CSS, el JS y los datos más recientes (resúmenes + los últimos `--days` días del feed, recortados a `--max-items` artículos por día) en un solo archivo HTML sin ningún `fetch` externo salvo las fuentes de Google Fonts. Útil para compartir el prototipo como un único archivo (por ejemplo, como Artifact). `dist/` está en `.gitignore`: se regenera, no se versiona.

## 5. Cómo agregar un resumen curado, paso a paso

1. Busca el artículo y confirma que es acceso abierto con licencia (ver criterio en `POLITICA-EDITORIAL.md`). Necesitas su DOI, PMID o PMCID.
2. Genera la plantilla:
   ```bash
   python3 scripts/add_paper.py 10.1234/ejemplo.2026 --tags adhd,digital --design rct
   ```
   Si el artículo no es acceso abierto o no declara licencia, el comando termina con código 2 y no crea nada.
3. Abre el archivo creado en `content/summaries/` y reemplaza cada `[[PENDIENTE]]`:
   - `En una frase` (una sola oración, máximo 300 caracteres).
   - `Pregunta`, `Métodos`, `Hallazgos clave`, `Limitaciones`, `Por qué importa para la clínica` (obligatorias).
   - `Nota del curador` (opcional).
   - Revisa `title` (el título en español que verá el lector) y ajusta `tags`/`study_design` si la detección automática no fue precisa.
   - Ninguna cifra que no esté en el abstract del artículo; nunca una cita textual de 15 palabras o más.
4. Cuando `status: draft` esté listo para publicarse, cámbialo a `status: published` y pon `author: "Javier Flores"` (o el nombre que corresponda).
5. Valida y genera los datos:
   ```bash
   python3 scripts/build_summaries.py --verify-oa
   ```
6. Revisa el resultado en local (`python3 -m http.server 8742`, ruta `#/resumenes/<slug>`).

## 6. Feed diario y backfill

El feed se genera automáticamente todos los días por GitHub Actions (`.github/workflows/daily-feed.yml`, cron `0 11 * * *` = 06:00 hora de Lima), una vez que el repositorio esté en GitHub con Actions activado. En local:

```bash
python3 scripts/fetch_daily.py --days 2      # uso diario normal
python3 scripts/fetch_daily.py --days 7      # backfill de una semana
python3 scripts/fetch_daily.py --date 2026-09-10   # un solo día puntual
```

`fetch_daily.py` nunca borra días previos ante un fallo de red: si un día falla, los demás se guardan igual y el script termina con código 1 para que quede claro que algo faltó.

## 7. Resumen con IA (opcional)

El feed diario y los borradores de `add_paper.py` pueden incluir, de forma opcional, un resumen en español generado con IA (modelo Claude) a partir del abstract original en inglés. Esto **nunca se activa por defecto**: requiere que definas la variable de entorno `ANTHROPIC_API_KEY` con tu propia clave.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python3 scripts/fetch_daily.py --days 2 --summarize --max-ai 20
```

- Sin `ANTHROPIC_API_KEY`, cualquier comando con `--summarize` termina con código 3 antes de intentar ninguna llamada de red.
- El modelo por defecto es `claude-haiku-4-5`; se puede cambiar con `--model` o con la variable `ANTHROPIC_MODEL`.
- **Costo aproximado**: cada resumen usa un abstract corto como entrada y genera 3-4 oraciones (menos de 90 palabras) de salida, así que el costo por artículo es bajo (del orden de fracciones de centavo de dólar con modelos como Haiku). Procesar un día completo (decenas de artículos, `--max-ai 20` por defecto) cuesta unos pocos centavos de dólar. Los precios cambian con el tiempo: conviene revisar la tabla de precios vigente en la documentación de Anthropic antes de activar `--summarize` en el cron diario.
- **Etiquetado**: todo resumen generado con IA se guarda con el modelo usado (`model`) y la fecha de generación (`generated_at`), y el frontend lo muestra siempre con la etiqueta "Resumen generado con IA · no revisado por un humano". Nunca se presenta como si lo hubiera escrito Javier.

## 8. Tests

```bash
python3 -m unittest discover -s tests -v
```

No requieren red ni `ANTHROPIC_API_KEY`: usan datos de prueba (`tests/fixtures/`) e inyectan la función de red (`fetch_fn`/`post_fn`) en vez de llamar a internet.

## 9. Variables de entorno

| variable | para qué sirve | obligatoria |
|---|---|---|
| `ANTHROPIC_API_KEY` | habilita `--summarize` (resumen con IA) | no; sin ella, `--summarize` falla con código 3 |
| `ANTHROPIC_MODEL` | cambia el modelo de IA por defecto | no |
| `EPMC_CA_FILE` | ruta a un archivo de certificados CA alternativo, si el de macOS no sirve | no |

## 10. Nota sobre certificados SSL en macOS

En algunas instalaciones de macOS, el contexto SSL por defecto de Python no encuentra la cadena de certificados y las llamadas a Europe PMC fallan con `CERTIFICATE_VERIFY_FAILED`. El cliente del pipeline (`scripts/epmc_client.py`) reintenta automáticamente con `/etc/ssl/cert.pem` (o con la ruta de `EPMC_CA_FILE` si la defines) y, como último recurso, con `curl` si está instalado. Si ves un error de red mencionando certificados, no hace falta ninguna acción manual salvo, en casos raros, instalar los certificados de Python (`Install Certificates.command`, incluido con el instalador oficial de python.org) o definir `EPMC_CA_FILE` a mano.

## 11. Despliegue futuro: GitHub Pages + Actions

El repositorio incluye dos workflows ya escritos pero **inactivos** hasta que decidas publicarlo:

- `.github/workflows/daily-feed.yml`: corre los tests, trae el feed del día, reconstruye `data/summaries.json` y, si hay cambios, los commitea.
- `.github/workflows/pages.yml`: publica el sitio en GitHub Pages cuando cambia algo en `index.html`, `assets/`, `data/` o `content/` (o manualmente).

Para activarlos:

1. Sube este proyecto a un repositorio de GitHub (no lo es todavía; hoy es solo una carpeta local en iCloud).
2. En **Settings → Pages → Source**, elige **GitHub Actions**.
3. Si quieres que el feed genere resúmenes con IA automáticamente, crea el secret `ANTHROPIC_API_KEY` en **Settings → Secrets and variables → Actions**. Es opcional: el feed diario funciona igual sin él, solo que sin `ai_summary`.
4. El cron `0 11 * * *` (06:00 hora de Lima) empezará a correr solo. También puedes lanzarlo a mano desde la pestaña **Actions → Feed diario Europe PMC → Run workflow**.

## 12. Limitaciones conocidas

- El tamaño de muestra (`sample_size`) que aparece en el feed diario es una estimación automática por expresiones regulares sobre el abstract; puede ser impreciso y siempre se marca como "estimado".
- Los resúmenes de autor (`summary`) que trae el feed diario vienen en inglés, tal como los escribieron los propios autores del artículo; no están traducidos.
- La ventana por defecto del feed es de 2 días (`--days 2`); un backfill más largo (`--days 7` o más) hay que correrlo manualmente al menos una vez.
- El resumen con IA es opcional y no está activado en este prototipo (no hay `ANTHROPIC_API_KEY` configurada).
- Los 4 resúmenes curados de ejemplo son borradores generados con IA para mostrar el formato del sitio (ver `POLITICA-EDITORIAL.md`, sección 4); no son resúmenes curados publicados por Javier.
- La retirada automática de artículos retractados solo ocurre mientras el día sigue dentro de la ventana de consulta del feed (`--days`); pasada esa ventana hace falta un backfill manual para detectar una retractación. Los resúmenes curados sí se revalidan en cada corrida de `build_summaries.py --verify-oa` (ver `POLITICA-EDITORIAL.md`, secciones 3 y 7).
