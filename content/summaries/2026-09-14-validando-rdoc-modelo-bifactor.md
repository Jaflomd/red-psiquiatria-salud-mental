---
title: "Validando RDoC con datos: un modelo bifactor guiado por activación cerebral"
date: 2026-09-14
status: published
example: false
ai_draft: false
adapted_with_ai: true
author: "Javier Flores"
tags: [symptom_networks, neuroscience]
study_design: modelling
summary_type: empirico
sample_size: 6192
paper_title: "A data-driven latent variable approach to validating the research domain criteria framework."
paper_authors: "Quah SKL, Jo B, Geniesse C, Uddin LQ, Mumford JA, Barch DM, Fair DA, Gotlib IH, Poldrack RA, Saggar M."
paper_journal: "Nature Communications"
paper_journal_abbrev: "Nat Commun"
paper_year: 2025
paper_pub_date: 2025-01-18
paper_source: MED
paper_epmc_id: "39827137"
paper_pmid: "39827137"
paper_pmcid: "PMC11743195"
paper_doi: 10.1038/s41467-025-55831-z
paper_license: "cc by-nc-nd"
paper_pub_types: ["research-article", "Journal Article"]
paper_preprint: false
paper_oa_verified: true
paper_oa_source: europepmc
paper_oa_checked: 2026-09-14
---

## En una frase
Un modelo bifactor construido desde 84 mapas de activación cerebral representa mejor las relaciones circuito-función que la organización RDoC convencional y sugiere añadir un factor general y dividir el dominio cognitivo.

## Ficha rápida
- Población: 6192 participantes sanos procedentes de 19 estudios de resonancia magnética funcional
- Intervención o exposición: 84 mapas whole-brain de activación durante tareas, obtenidos de NeuroVault y UK Biobank
- Comparador: cuatro modelos factoriales, RDoC específico, RDoC bifactor, data-driven específico y data-driven bifactor
- Desenlace primario: ajuste de los modelos medido con RMSEA, CFI, TLI, AIC y BIC
- Efecto principal: el modelo data-driven bifactor mostró mejor ajuste global; Tukey p < .001 para RMSEA, CFI y TLI
- Certeza: baja; análisis exploratorio sobre un corpus limitado, con validación interna y externa

## Pregunta
¿La estructura de dominios definida a priori por RDoC representa adecuadamente las relaciones entre circuitos cerebrales y funciones psicológicas, o una estructura latente derivada de los propios mapas de activación ofrece un ajuste y una generalización mejores?

## Métodos
Estudio de modelado con análisis de variables latentes. Los autores reunieron 84 mapas whole-brain de activación por tareas de 19 estudios con 6192 participantes, reservaron 37 mapas equilibrados por dominio RDoC para entrenar los modelos y conservaron 47 para validación interna. Compararon cuatro soluciones factoriales y realizaron una validación externa con 36 mapas de coordenadas reconstruidos desde Neurosynth.

- Los mapas se parcelaron en 333 regiones corticales y 14 subcorticales y sus valores se escalaron antes del análisis.
- Los modelos data-driven combinaron análisis factorial exploratorio y confirmatorio; los modelos RDoC usaron factores predefinidos y análisis confirmatorio.
- El ajuste se evaluó con RMSEA, CFI, TLI, AIC y BIC robustos, con 5000 remuestreos de Yuan y comparaciones ANOVA, Tukey o Mann-Whitney según la distribución.

## Hallazgos clave
- Añadir un factor general al modelo RDoC específico mejoró todos los índices de ajuste, incluido el balance entre ajuste y complejidad, con Tukey p < .001.
- El modelo data-driven bifactor tuvo el mejor ajuste global en los mapas whole-brain, aunque el modelo data-driven específico fue competitivo al penalizar la complejidad con AIC y BIC.
- La solución data-driven separó ocho factores específicos: percepción social, respuesta motora, respuesta de valencia negativa, memoria de trabajo y lenguaje, atención espacial, teoría de la mente y valoración de recompensa, además del factor general.
- El dominio cognitivo de RDoC distribuyó sus cargas entre varios factores, mientras que el dominio sensorimotor mostró una correspondencia más compacta; valencia negativa no cargó significativamente en un factor data-driven único.
- La validación externa con 36 mapas de Neurosynth favoreció al modelo data-driven específico en todos los índices; el factor general no pudo probarse allí por la dispersión de los mapas de coordenadas.

## Limitaciones
- Muestra: los 84 mapas proceden de un conjunto limitado de estudios y tareas, con representación desigual de los dominios RDoC.
- Medición: la mayoría de tareas usa estímulos visuales, por lo que el factor general puede mezclar funcionamiento task-general con activación visual compartida.
- Análisis: incluso el mejor modelo tuvo un ajuste global subóptimo y la ganancia del bifactor implicó mayor complejidad.
- Generalización: solo se evaluó la unidad de análisis de circuitos por resonancia funcional; faltan datos genéticos, moleculares, fisiológicos y conductuales.

## El principio
- Enunciado: Una ontología funcional mejora cuando separa la actividad compartida entre tareas de los patrones específicos de cada función.
- Fundamento: El bifactor permitió distinguir un componente general de ocho factores específicos y superó el ajuste del RDoC convencional en datos retenidos. La ventaja fue menor al penalizar complejidad y no equivale a validar una nueva nosología clínica.
- Evidencia: 84 mapas de 19 estudios y 6192 participantes; 47 mapas de validación interna y 36 mapas de validación externa.
- Fuerza: baja
- Transferencia: investigación, formación
- Límite: corpus de tareas desequilibrado y restringido a activación funcional en participantes sanos.
- Procedencia: autores

## Por qué importa para la clínica
El artículo no valida un instrumento diagnóstico ni propone cambiar la atención de un paciente. Su valor clínico es indirecto: muestra que los dominios transdiagnósticos usados para formular hipótesis neurobiológicas pueden ser demasiado amplios y que parte de la señal atribuida a un dominio puede corresponder a demandas generales de la tarea.

- Al interpretar biomarcadores basados en RDoC, separar la activación general de la tarea de la señal específica del constructo. Límite: el estudio no demuestra utilidad diagnóstica ni pronóstica individual.
- En investigación de procesos cognitivos, evitar tratar atención, memoria de trabajo, lenguaje y teoría de la mente como una sola unidad neurofuncional. Límite: la partición propuesta depende del conjunto de tareas disponible.
- Al diseñar protocolos transdiagnósticos, ampliar las tareas dirigidas a arousal y regulación, ausentes en este corpus. Límite: la ausencia de mapas no demuestra que el dominio carezca de coherencia biológica.

## Glosario
- RDoC: marco del NIMH que organiza funciones relevantes para la psicopatología en dominios y unidades de análisis dimensionales.
- Modelo bifactor: modelo que estima simultáneamente un factor general compartido y factores específicos ortogonales.
- Factor general: patrón de activación común a múltiples tareas; aquí estuvo dominado por regiones visuales y motoras.
- EFA: análisis factorial exploratorio usado para descubrir cuántos factores específicos describen los datos.
- CFA: análisis factorial confirmatorio usado para estimar el ajuste de una estructura factorial definida.
- Validación interna: prueba del modelo en mapas whole-brain retenidos del corpus original.
- Validación externa: prueba con mapas de coordenadas obtenidos de Neurosynth, una modalidad distinta a la usada para entrenar.

## Lecturas recomendadas
- Beam E, Potts C, Poldrack RA, Etkin A (2021). A data-driven framework for mapping domains of human neurobiology. Nat Neurosci · doi:10.1038/s41593-021-00948-9 · Antecedente directo que mostró límites en la correspondencia circuito-función de RDoC y DSM.
- Bolt T, et al. (2020). Ontological dimensions of cognitive-neural mappings. Neuroinformatics · doi:10.1007/s12021-020-09454-y · Presenta el corpus de mapas y el enfoque ontológico sobre el que se apoya este análisis.
- Insel T, et al. (2010). Research Domain Criteria: Toward a New Classification Framework for Research on Mental Disorders. Am J Psychiatry · doi:10.1176/appi.ajp.2010.09091379 · Texto fundacional para entender el propósito original de RDoC y qué intenta refinar el estudio.

## Nota del curador
Resumen de Javier Flores, adaptado al formato del sitio con asistencia de IA. El contenido y las cifras se contrastaron con el texto completo de PubMed Central. La licencia CC BY-NC-ND permite compartir el artículo con atribución, pero no reutilizar material adaptado del original; esta nota es una síntesis independiente y no reproduce tablas ni figuras.

## Nota completa

### Información del estudio
- Título: A data-driven latent variable approach to validating the research domain criteria framework
- Autor principal: Suan Kit Lionel Quah
- Correo de correspondencia: No reportado en el artículo
- Año: 2025
- Revista: Nature Communications
- Palabras clave: Human behaviour; Cognitive neuroscience
- País: Estados Unidos

### Introducción en tres frases
- Problema: RDoC se definió conceptualmente y puede ser demasiado amplio o poco específico respecto de los circuitos cerebrales que pretende organizar.
- Literatura previa: estudios data-driven habían encontrado vínculos circuito-función más reproducibles y solapamiento neural entre varios dominios RDoC.
- Vacío: faltaba comparar directamente modelos RDoC y modelos derivados de mapas whole-brain, separando varianza general y específica y probando su generalización.

### Pregunta de investigación
- Primaria: comparar si una estructura factorial data-driven representa mejor que RDoC las relaciones entre funciones de tarea y patrones de activación cerebral.
- Secundarias: evaluar el aporte de un factor general, describir la correspondencia entre dominios RDoC y factores empíricos y validar la solución en datos no usados para entrenarla.

### Método
Cuantitativo: modelado de variables latentes mediante análisis factorial exploratorio y confirmatorio de mapas de activación cerebral agregados.

### Diseño
- Diseño: estudio de modelado secundario con validación interna y externa de estructuras factoriales.
- Checklist declarado: Nature Portfolio Reporting Summary.

### Unidad de análisis
Mapas grupales no umbralizados de contraste BOLD tarea frente a línea basal, no participantes individuales. Cada mapa resumió la activación de un estudio o contraste funcional en participantes sanos.

### Muestra
Corpus inicial de 84 mapas whole-brain procedentes de 19 estudios con 6192 participantes. El entrenamiento utilizó 37 mapas derivados de 6119 participantes; la validación interna usó 47 mapas retenidos y la externa 36 mapas de coordenadas de Neurosynth.

### Muestreo
Muestreo intencional de mapas públicos en NeuroVault y UK Biobank. Los autores excluyeron mapas del Human Connectome Project para reducir dependencia entre mapas del mismo grupo y equilibraron el conjunto de entrenamiento por dominio RDoC.

### Procedimientos
1. Se reunieron 84 mapas whole-brain y se seleccionaron 37 para un conjunto de entrenamiento más equilibrado, reservando 47 para validación interna.
2. Los mapas se transformaron a espacio MNI-152 de 2 mm, se parcelaron en 333 regiones corticales y 14 subcorticales y se escalaron.
3. Se estimaron cuatro modelos: RDoC específico, RDoC bifactor, data-driven específico y data-driven bifactor.
4. Se comparó el ajuste de los modelos y la correspondencia entre sus factores, controlando la autocorrelación espacial.
5. La solución se probó en los mapas whole-brain retenidos y en 36 mapas de coordenadas de Neurosynth.

### Variables dependientes
- Ajuste del modelo: RMSEA, CFI y TLI robustos, junto con AIC y BIC para balancear ajuste y complejidad.
- Correspondencia circuito-función: cargas y puntuaciones factoriales de cada mapa en los factores generales y específicos.

### Variables independientes
- Arquitectura del modelo: organización RDoC o data-driven, cada una con estructura específica o bifactor.
- Conjunto de validación: mapas whole-brain retenidos o mapas de coordenadas de Neurosynth.
- Covariables evaluadas: balance por sexo, tamaño de muestra e identificador del estudio; no se incluyeron en el modelo final por su bajo aporte y problemas de convergencia.

### Análisis de datos
- Univariado: descripción del número de mapas, estudios, participantes y representación de dominios.
- Bivariado: correlaciones de Pearson entre puntuaciones factoriales de RDoC y del modelo data-driven.
- Multivariado: EFA con principal axis factoring y rotación oblimin, CFA con máxima verosimilitud robusta y modelos bifactor ortogonales; 5000 remuestreos de Yuan para los índices de ajuste.
- Supuestos: manejo robusto de no normalidad y ajuste de p por autocorrelación espacial mediante BrainSMASH.
- Software: R y paquetes de modelado estructural; el artículo remite al código abierto para los detalles reproducibles.

### Hallazgos principales
Aquí se realizó un estudio de modelado factorial de mapas de resonancia funcional para comparar la ontología RDoC con estructuras data-driven y evaluar su generalización. Los hallazgos principales son: 1) añadir un factor general mejoró el ajuste de RDoC; 2) el modelo data-driven bifactor mostró el mejor ajuste global en whole-brain, aunque la penalización por complejidad favoreció parcialmente al modelo específico; 3) los factores empíricos dividieron el dominio cognitivo y mostraron límites difusos para valencia negativa; 4) la solución data-driven generalizó a mapas retenidos y a mapas de coordenadas externos.

### Datos por hallazgo
1. El RDoC bifactor superó al RDoC específico en todos los índices de ajuste, con Tukey p < .001, incluidos AIC y BIC.
2. El data-driven bifactor superó a los otros modelos en RMSEA, CFI y TLI con Tukey p < .001; se estimaron ocho factores específicos más un factor general.
3. Atención, memoria de trabajo y lenguaje, teoría de la mente y otras demandas cognitivas se distribuyeron en factores separados; valencia negativa no mostró cargas significativas en un único factor data-driven.
4. La validación interna empleó 47 mapas whole-brain y la externa 36 mapas de Neurosynth; en esta última, el modelo data-driven específico superó al RDoC específico en todos los índices comparados.

### Discusión
- Qué significa: una estructura derivada de datos puede representar mejor las relaciones circuito-función que los dominios RDoC actuales, sobre todo al separar actividad general y específica.
- Por qué ocurre: los dominios predefinidos agrupan tareas con demandas neurales heterogéneas, mientras el bifactor absorbe activación compartida y deja patrones residuales más específicos.
- Contexto amplio: los autores proponen refinar RDoC de forma iterativa, no reemplazarlo mecánicamente por una sola solución data-driven.

### Limitaciones según los autores
- Selección: conjunto limitado y desequilibrado de mapas, reflejo de las tareas disponibles en la literatura de neuroimagen.
- Medición: las tareas suelen implicar varios dominios a la vez y predominan los estímulos visuales, lo que puede inflar el factor general.
- Confusión: variaron el balance por sexo, el tamaño de muestra y los parámetros de adquisición entre estudios; excluir sus efectos produjo problemas de estimación.
- Otras: el ajuste global siguió siendo subóptimo y el estudio solo evaluó la unidad de análisis de circuitos funcionales.

### Investigación futura
- Incorporar tareas más amplias y equilibradas, en especial para arousal y sistemas regulatorios.
- Evaluar otras unidades de análisis RDoC, incluidas genética, fisiología y conducta.
- Probar contrastes por sustracción y estructuras alternativas que separen mejor las demandas múltiples de una tarea.
- Replicar los factores en corpus independientes con mayor diversidad de paradigmas y participantes.
