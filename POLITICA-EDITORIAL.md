# Política editorial

Este documento explica qué publica este sitio, con qué criterios y qué límites tienen sus herramientas automáticas. Es la referencia que sigue el software (`scripts/`) y también la que sigue Javier Flores al redactar o revisar resúmenes curados.

## 1. Qué es este sitio

El sitio combina dos tipos de contenido:

- **Resúmenes curados** (`content/summaries/`): artículos que Javier Flores elige y resume en español, con sus propias palabras, pensando en su utilidad clínica o de investigación.
- **Feed diario** (`data/daily/`): un listado generado automáticamente todos los días a partir de Europe PMC, sin curaduría manual, con los artículos nuevos de psiquiatría y salud mental que cumplen el criterio de acceso abierto de este documento.

Ninguno de los dos sustituye la lectura del artículo original. Ambos enlazan siempre a la fuente en Europe PMC.

## 2. Criterio de acceso abierto (regla dura)

Un artículo entra al feed diario, o puede convertirse en resumen curado, **solo si cumple los dos puntos siguientes a la vez**:

1. Europe PMC lo marca como acceso abierto: `isOpenAccess = Y`.
2. El registro declara una licencia Creative Commons reconocible (`license` empieza por `cc by` o es `cc0`: por ejemplo CC BY, CC BY-NC, CC BY-NC-ND, CC BY-SA o CC0).

Si falta cualquiera de los dos, el artículo **se rechaza**, sin excepción:

- `add_paper.py` termina con código de salida 2 y explica el motivo (marca de acceso abierto ausente, o licencia no declarada).
- El feed diario descarta el registro en el paso de filtrado local y lo cuenta como descarte, aunque haya aparecido en los resultados de búsqueda de Europe PMC.

**"Gratis para leer" no es lo mismo que acceso abierto.** Muchas revistas marcan artículos como de lectura gratuita ("Free") sin que Europe PMC los reconozca como acceso abierto ni declaren una licencia. Ese caso se rechaza igual: sin una licencia declarada, no hay base legal clara para resumir el contenido en este sitio.

### Preprints

Los preprints (artículos sin revisión por pares, fuente `PPR` en Europe PMC) **sí pueden entrar al feed**, pero únicamente si cumplen el mismo criterio de acceso abierto con licencia de la sección anterior. Cuando entran, se marcan siempre y de forma visible como **"preprint · sin revisión por pares"**, en el feed, en las tarjetas y en cualquier ficha de detalle, para que nunca se confundan con un artículo publicado en una revista con revisión por pares. Los resúmenes curados de este prototipo no incluyen preprints, pero el sitio está preparado para mostrarlos correctamente si Javier decide curar uno en el futuro.

## 3. Qué queda fuera del feed diario

Además del filtro de acceso abierto, el feed excluye tipos de publicación que no son artículos de investigación originales, entre ellos: resúmenes de congreso, editoriales, cartas, comentarios, noticias, reseñas de libros, obituarios, y explícitamente:

- Erratas y correcciones ("erratum", "correction", "corrected and republished article", "published erratum").
- Retractaciones ("retraction", "retracted publication", "retraction of publication").
- Expresiones de preocupación ("expression of concern").
- Adendas y respuestas ("addendum", "reply").

Si un artículo ya incluido en el feed es retractado o recibe una expresión de preocupación **mientras su día sigue dentro de la ventana de consulta** (`--days`, por defecto los últimos 2 días), se retira en la siguiente corrida del feed: cada corrida recalcula el conjunto completo de esos días desde cero contra Europe PMC (ver sección 8).

**Limitación conocida, no solo de plazo:** una vez que un día sale de esa ventana, `fetch_daily.py` ya no vuelve a consultarlo por sí solo. Las retractaciones suelen registrarse meses después de la indexación original, así que un artículo retractado que ya "envejeció" fuera de la ventana **se queda en el feed indefinidamente** hasta que alguien corra manualmente un backfill que vuelva a traer ese día (`python3 scripts/fetch_daily.py --days N` con N suficientemente grande, o `--date AAAA-MM-DD` apuntando a ese día). Este prototipo no incluye todavía una revalidación periódica automática de los días antiguos del feed.

## 4. Qué es y qué no es un "resumen curado"

Un resumen curado:

- Resume un artículo real, verificado en Europe PMC (DOI, PMID o PMCID, licencia y marca de acceso abierto comprobados el día en que se escribe).
- Está redactado con palabras propias, en español claro, pensando en un lector clínico.
- Incluye una sección fija con la pregunta de investigación, el método, los hallazgos principales, las limitaciones y la relevancia clínica.
- Enlaza siempre al artículo original en Europe PMC (y al DOI y al PDF cuando existen).

Un resumen curado **no es**:

- Una traducción del abstract original. El texto se reformula con palabras propias; cuando hace falta una cita textual, es breve (ver sección 5).
- Una opinión clínica de Javier sobre el tema, salvo en la sección "Por qué importa para la clínica", que sí es una lectura interpretativa y se presenta como tal.
- Un resumen generado por inteligencia artificial sin decirlo. Ver sección 6.

### Los cuatro resúmenes de ejemplo de este prototipo

Los cuatro resúmenes que acompañan este prototipo (`content/summaries/2026-09-14-*.md`) fueron redactados por un agente de inteligencia artificial para mostrar el formato del sitio con artículos reales y verificados, **no por Javier Flores**. Por eso llevan `author: "Borrador de ejemplo generado con IA"`, `status: draft`, `example: true` y `ai_draft: true`, y el frontend los muestra con las etiquetas "BORRADOR DE EJEMPLO" y "BORRADOR IA". No deben tratarse como resúmenes curados publicados hasta que Javier los revise, corrija lo que haga falta y cambie su estado a `published` con su propia autoría.

## 5. Regla de citas y derechos de autor

Los resúmenes se escriben con palabras propias. Si es imprescindible citar una frase del artículo original, la cita:

- va entre comillas,
- tiene menos de 15 palabras,
- y nunca sustituye la explicación en palabras propias del hallazgo.

No se reproducen tablas, figuras ni fragmentos largos del artículo. El resumen siempre enlaza al artículo completo en Europe PMC (y al DOI cuando existe) para quien quiera leer el texto original.

## 6. Etiquetado obligatorio de contenido generado con inteligencia artificial

Ningún texto generado o redactado con ayuda de inteligencia artificial se presenta como si lo hubiera escrito Javier Flores sin decirlo:

- En el **feed diario**, un resumen generado con IA (`ai_summary`) muestra siempre el modelo usado y la fecha de generación, y se etiqueta "Resumen generado con IA · no revisado por un humano". Las etiquetas temáticas detectadas automáticamente se marcan como "Etiquetas automáticas".
- En los **resúmenes curados**, un borrador con `ai_draft: true` se etiqueta "BORRADOR IA · pendiente de revisión" mientras está en estado `draft`, y como redactado con asistencia de IA y revisado por su autor una vez que pasa a `published` (la marca de origen por IA no desaparece al publicarse: solo cambia el texto que la describe).
- El diseño de estudio y el tamaño de muestra detectados automáticamente en el feed se marcan siempre como "estimado", porque el método automático (reglas y expresiones regulares sobre el título y el resumen) puede equivocarse. Solo se presentan sin esa marca cuando Javier los indica manualmente en un resumen curado.

## 7. Corrección y retractación

- Si Europe PMC marca un artículo del feed como retractado o con expresión de preocupación **mientras su día sigue dentro de la ventana de consulta**, el artículo se retira automáticamente del feed en la siguiente corrida (ver la limitación de plazo en la sección 3: fuera de esa ventana, la retirada automática no ocurre sin un backfill manual).
- Los **resúmenes curados** sí se revalidan cada vez que se corre `python3 scripts/build_summaries.py --verify-oa` (paso obligatorio antes de publicar cambios, ver README): esa bandera vuelve a consultar Europe PMC en vivo por cada artículo curado y rechaza la compilación si alguno perdió el acceso abierto, la licencia abierta, o aparece como retractado o con expresión de preocupación asociada.
- Si un resumen curado ya publicado resulta estar basado en un artículo posteriormente retractado, corregido de forma sustancial o con expresión de preocupación, Javier lo marca de forma visible en el propio resumen y añade una nota explicando el cambio; el resumen no se elimina en silencio.
- Cualquier error de hecho detectado en un resumen curado ya publicado (una cifra, un dato de autoría, una conclusión mal transcrita) se corrige en el archivo Markdown y el resumen actualiza su campo `updated` con la fecha de la corrección.

## 8. Transparencia sobre las heurísticas automáticas

El feed diario asigna diseño de estudio, tamaño de muestra y etiquetas temáticas con reglas automáticas (expresiones regulares y coincidencia de tipo de publicación), no con lectura humana de cada artículo. Estas heurísticas:

- Pueden fallar: un tamaño de muestra puede confundir el número de personas evaluadas con el número de personas incluidas en el análisis final, y una etiqueta temática puede aplicarse a un artículo que solo menciona el término de pasada.
- Por eso todo tamaño de muestra automático se muestra con la palabra "estimado" y una nota indicando que puede ser impreciso, y toda etiqueta automática se identifica como tal.
- Nunca se usan heurísticas automáticas dentro de un resumen curado salvo que Javier las revise y las confirme manualmente; en ese caso se marcan con `confidence: manual` en vez de `heuristic`.

## 9. Privacidad

- Este sitio no envía datos personales de sus lectores a ninguna API externa. Las únicas llamadas salientes son a la API pública de Europe PMC (para buscar y verificar artículos) y, de forma opcional y solo cuando Javier lo activa con su propia clave, a la API de Anthropic para generar borradores de resumen.
- No se guarda ni se registra ninguna clave de API en el código ni en los datos publicados del sitio.
- El feed y los resúmenes solo contienen información pública de artículos científicos (título, autores, revista, resumen, identificadores); no se procesan datos de pacientes ni información clínica identificable.
