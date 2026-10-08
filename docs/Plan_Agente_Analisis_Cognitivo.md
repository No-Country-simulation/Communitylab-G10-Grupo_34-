# Plan de Diseño y Construcción del Agente de Análisis Cognitivo — CommunityLab

### Tarea S1-1 · Requisito R2

| | |
|---|---|
| **Proyecto** | CommunityLab — Hackathon ONE G10 (Oracle Next Education & Alura) · Equipo 34 · Simulación Laboral NoCountry [[1]](#referencias) |
| **Preparado por** | Michael Antonio Chacón Rossell — AI Engineer (análisis) |
| **Componente** | Agente de Análisis Cognitivo (Contrato 2 del pipeline de datos) |
| **Fecha** | 20 de septiembre de 2026 · revisión de alineación técnica |

---

> **Nota de revisión — versión alineada con `esquemas.py`:** esta versión corrige el borrador inicial (generado en Gemini) para reflejar el Contrato 2 (`AnalisisCognitivo` / `MensajeAnalizado`) ya vigente, acordado con Sergio y Andrea [[3]](#referencias). Cambios principales frente al borrador original:
> 1. El sentimiento pasa de una polaridad continua `[-1.0, 1.0]` a las cuatro categorías `Literal` ya definidas ("Altamente Positivo", "Positivo", "Neutro", "Dificultad/Negativo").
> 2. El *score* de relevancia pasa de una fórmula ponderada continua a la suma entera de tres dimensiones, 0 a 2 puntos cada una (total 0–6).
> 3. El enrutamiento por umbral a cuatro canales (`LINKEDIN`/`NEWSLETTER`/`FAQ`/`ARCHIVE`) se reemplaza por `categoria_enrutamiento` (Logro/Duda/Dificultad) más los indicadores `requiere_soporte` y `apto_para_publicacion`.
> 4. Las entidades pasan de objetos NER tipados con `confidence` a una lista simple de cadenas (`entidades_relevantes`).
> 5. Se elimina el modelo temático de dos niveles (taxonomía fija + sub-temas) en favor de una lista plana `temas`.
> 6. `batch_id` y `processed_at` se eliminan del nivel de mensaje: la identificación de lote (`run_id`, `request_id`) ya vive en el sobre `AnalisisCognitivo`, no en cada registro.
> 7. Los nombres de archivo de las fases se alinean con la estructura de repositorio ya acordada por el equipo.

---

## 1. Contextualización Arquitectónica y Especificaciones del Sistema

CommunityLab surge como una plataforma orientada a transformar los intercambios orgánicos y no estructurados de comunidades digitales —en canales como Discord o foros colaborativos— en activos de comunicación y conocimiento institucional [[1]](#referencias). En el marco del crecimiento guiado por comunidades (*Community-Led Growth*) y la automatización MarTech, la proliferación diaria de testimonios, hitos formativos y resoluciones técnicas suele quedar confinada en hilos dispersos, impidiendo su aprovechamiento sistemático. La arquitectura de CommunityLab aborda esta problemática mediante una secuencia desacoplada de procesamiento por lotes que captura la actividad cruda, extrae indicadores de valor cognitivo y sintetiza publicaciones para redes profesionales, boletines informativos periódicos y repositorios dinámicos de preguntas frecuentes.

Dentro de esta cadena de valor, la **Tarea S1-1** responde directamente a la implementación técnica del **Requisito R2** [[2]](#referencias), materializando el Agente de Análisis Cognitivo. Este componente se ubica de manera estratégica entre el subsistema de ingesta validada (`InteraccionValidada`) y los agentes de generación textual *downstream* (LinkedIn / Newsletter). Su propósito no es redactar los contenidos finales, sino operar como un filtro inferencial de alta precisión que examina lotes de mensajes validados, extrae dimensiones semánticas clave y pondera objetivamente la relevancia de cada intervención comunitaria.

### Parámetros del pipeline

| Parámetro de pipeline | Especificación técnica en CommunityLab | Justificación de arquitectura |
|---|---|---|
| **Punto de entrada (Input)** | Lista de `InteraccionValidada` (texto no vacío, metadatos de origen canónicos) producida por la capa de validación local [[3]](#referencias). | Asegura homogeneidad sintáctica antes de incurrir en costes de inferencia computacional. |
| **Procesamiento nuclear (S1-1 / R2)** | Clasificación de sentimiento (4 categorías), extracción de temas y entidades, y cómputo del *score* de relevancia 0–6. | Transforma texto plano en atributos categóricos y cuantitativos interpretables, con salida validada por Pydantic. |
| **Punto de salida (Output)** | `MensajeAnalizado` por cada interacción válida, con `source_id`, categorización, `puntuacion_relevancia` y `motivo_seleccion`; agregado en `AnalisisCognitivo` junto al `resumen_comunidad`. | Alimenta de manera determinista los motores generativos de LinkedIn y resumen semanal. |
| **Infraestructura y custodia** | Entorno Python (PydanticAI + LangGraph) orquestado con posible integración n8n, persistiendo artefactos en OCI Object Storage. | Cumple los requerimientos de eficiencia de costes y almacenamiento duradero de nivel empresarial [[1]](#referencias). |

La importancia de este diseño radica en el **desacoplamiento analítico**: al computar previamente el valor semántico y la relevancia de cada registro, se evita sobrecargar a los modelos generativos posteriores con volúmenes masivos de datos irrelevantes, mitigando alucinaciones conceptuales y optimizando los costos operativos por uso de tokens.

## 2. Motores de Extracción Cognitiva y Procesamiento Lingüístico

El análisis del discurso comunitario en entornos técnicos y de aprendizaje presenta desafíos interpretativos particulares: coexistencia de jerga especializada, fragmentos de código intercalados, consultas abreviadas y variabilidad en la carga emotiva. La Tarea S1-1 aborda estos desafíos mediante salida estructurada obligatoria del LLM (PydanticAI), validada de forma estricta contra `MensajeAnalizado` [[3]](#referencias) — sin cómputos numéricos intermedios fuera del esquema acordado.

### 2.1 Análisis de sentimiento

En lugar de una polaridad continua, el agente asigna directamente una de cuatro categorías discretas mediante el campo `sentimiento` (`Literal`), forzadas por el esquema:

- **`"Altamente Positivo"`** — hitos de superación, agradecimientos y testimonios de éxito; materia prima para publicaciones de impacto en LinkedIn.
- **`"Positivo"`** — valoraciones favorables sin llegar a un hito destacado.
- **`"Neutro"`** — consultas de soporte técnico y debates arquitectónicos, candidatos naturales al resumen semanal o a una futura base de FAQ.
- **`"Dificultad/Negativo"`** — fricción con herramientas, dudas recurrentes o bloqueos pedagógicos; candidatos a `requiere_soporte = true`.

Al ser una clasificación categórica y no una regresión numérica, la calibración del modelo se ajusta con ejemplos *few-shot* en el prompt, no con un coeficiente de calibración (`γ`) como proponía el borrador original.

### 2.2 Modelado temático

El esquema vigente usa una lista plana y abierta: `temas: List[str]` (mínimo 1 elemento), extraída libremente por el LLM a partir del contenido de cada mensaje — sin una taxonomía maestra fija separada de micro-temas dinámicos. Esto simplifica la extracción a un único paso, a costa de exigir mayor disciplina en el prompt para mantener nombres de tema consistentes entre lotes (ej. evitar que un mismo concepto aparezca como "LangGraph" en un mensaje y "orquestación de agentes" en otro sin normalización).

### 2.3 Reconocimiento de entidades

`entidades_relevantes: List[str]` (lista simple, por defecto vacía) recoge nombres de tecnologías, herramientas o conceptos mencionados en el mensaje. El esquema no tipifica cada entidad con una etiqueta (`TECH_STACK`, `TOOL_PLATFORM`, etc.) ni con un puntaje de confianza — esa taxonomía puede seguir usándose como **guía interna del prompt** para orientar qué debe extraer el modelo, pero no se persiste como estructura en el contrato de datos.

## 3. Cálculo del Score de Relevancia

El diseño vigente reemplaza la fórmula ponderada continua por una suma entera simple y auditable de tres dimensiones, cada una evaluada por el LLM en una escala de 0 a 2 puntos, dentro del objeto `puntuacion_relevancia` (`PuntuacionRelevancia`) [[3]](#referencias):

| Dimensión | Rango | Qué evalúa |
|---|---|---|
| `evidencia_explicita` | 0–2 | Datos y hechos verificables presentes en el texto (nombres, resultados, cifras concretas). |
| `utilidad_comunitaria` | 0–2 | Valor formativo, técnico o motivacional para el resto de la comunidad. |
| `claridad_contexto` | 0–2 | Claridad temática y suficiencia de contexto para que el mensaje se entienda de forma aislada. |
| `total` | 0–6 | Suma de las tres dimensiones anteriores. |

No existen pesos (`wᵢ`) que calibrar ni funciones auxiliares (`ψ`, `ε`, `μ`, `ω`) — la objetividad del puntaje se sostiene en que el LLM debe documentar el porqué de cada sub-puntaje dentro de `motivo_seleccion`, no en una fórmula matemática externa.

### Enrutamiento editorial

El diseño vigente no enruta por umbral numérico sobre el *score*. En su lugar, el propio LLM asigna directamente, junto al análisis:

| Campo | Valores | Rol en el enrutamiento |
|---|---|---|
| `categoria_enrutamiento` | `"Logro"` \| `"Duda"` \| `"Dificultad"` | Orienta el enfoque editorial del contenido generado *downstream*. |
| `apto_para_publicacion` | `bool` | Determina si el mensaje califica para difusión pública (LinkedIn / resumen semanal). |
| `requiere_soporte` | `bool` | Marca casos que deben canalizarse a mentoría o soporte, independientemente del *score*. |

El `puntuacion_relevancia.total` (0–6) sirve como criterio de **priorización y ordenamiento** dentro de un lote — por ejemplo, para elegir el mejor testimonio cuando varios mensajes son aptos para publicación — no como *gate* automático de descarte por umbral fijo.

## 4. Especificación de Esquemas de Datos y Trazabilidad Estricta

El Requisito R2 [[2]](#referencias) exige una correspondencia auditable entre los datos primarios y las inferencias cognitivas. El contrato vigente separa dos niveles: el mensaje individual (`MensajeAnalizado`) y el sobre del lote (`AnalisisCognitivo`, con su `ResumenComunidad`) [[3]](#referencias).

### 4.1 Nivel de mensaje — `MensajeAnalizado`

| Campo | Tipado estricto | Invariante / regla de validación | Descripción y uso |
|---|---|---|---|
| `source_id` | `str` | Referencia exacta al `id` del mensaje de origen (`InteraccionValidada`). | Enlace persistente y auditable al mensaje original. |
| `sentimiento` | `Literal` (4 valores) | "Altamente Positivo" / "Positivo" / "Neutro" / "Dificultad/Negativo". | Clasificación categórica de consumo inmediato. |
| `categoria_enrutamiento` | `Literal` (3 valores) | "Logro" / "Duda" / "Dificultad". | Orienta el enfoque editorial del contenido generado. |
| `regla_aplicada` | `str` | Obligatorio. | Criterio documentado que derivó la categorización. |
| `temas` | `List[str]` | Mínimo 1 elemento. | Temas identificados en el mensaje. |
| `entidades_relevantes` | `List[str]` | Por defecto, lista vacía. | Tecnologías, herramientas o conceptos mencionados. |
| `puntuacion_relevancia` | `PuntuacionRelevancia` | Objeto anidado, total 0–6. | Ver sección 3. |
| `motivo_seleccion` | `str` | Mínimo 10 caracteres. | Justificación objetiva de la puntuación y la categoría asignada. |
| `requiere_soporte` | `bool` | Por defecto `false`. | Marca casos que requieren canalización o mentoría. |
| `apto_para_publicacion` | `bool` | Obligatorio. | Determina si el mensaje califica para difusión pública. |

> Nota sobre `motivo_seleccion`: el esquema vigente exige solo 10 caracteres como mínimo — un umbral más permisivo que el rango de 20–100 palabras propuesto en el borrador original. Si el equipo quiere garantizar justificaciones más completas, sería necesario ajustar el `Field` en `esquemas.py` (por ejemplo, con un validador de conteo de palabras) — eso sí requiere el consenso previo del equipo que ya se acordó para cualquier cambio de contrato.

### 4.2 Nivel de lote — `AnalisisCognitivo` y `ResumenComunidad`

| Campo | Ubicación | Descripción |
|---|---|---|
| `run_id` | `AnalisisCognitivo` | ID de ejecución asignado por la API (no por mensaje). |
| `request_id` | `AnalisisCognitivo` | ID de la solicitud original, heredado del Contrato 1. |
| `resumen_comunidad` | `AnalisisCognitivo` | Objeto `ResumenComunidad` (ver abajo). |
| `mensajes_analizados` | `AnalisisCognitivo` | Lista de `MensajeAnalizado`, mínimo 1 elemento. |
| `total_interacciones_procesadas` / `registros_validos` / `registros_rechazados` | `ResumenComunidad` | Conteos del lote (aislamiento de fallos, Contrato 1). |
| `sentimiento_predominante` | `ResumenComunidad` | Polaridad dominante o `"Mixto"` si el lote está dividido. |
| `distribucion_sentimiento` | `ResumenComunidad` | Conteo por categoría de sentimiento. |
| `temas_principales` | `ResumenComunidad` | Mínimo 1 elemento. |
| `alertas_soporte` | `ResumenComunidad` | Lista de `source_id` que requieren soporte, por defecto vacía. |

`motivo_seleccion` cumple un rol central en la observabilidad del sistema: cada justificación debe identificar la tipología del contenido, explicitar qué evidencia y entidades sustentan la puntuación, y señalar la lógica que amerita la `categoria_enrutamiento` asignada — de modo que los auditores humanos puedan fiscalizar el pipeline sin recalcular nada.

## 5. Mecanismos de Resiliencia Operativa y Manejo de Excepciones

El procesamiento de lotes masivos expone al agente a variabilidad extrema en el texto de entrada y a eventualidades de red al comunicarse con LLMs. El ciclo de ejecución procesa los lotes en fases encapsuladas:

1. **Particionamiento y validación estructural** — el lote se fragmenta en bloques concurrentes y pasa el filtro de `InteraccionValidada` [[3]](#referencias). Registros sin `id` o con texto vacío tras sanitización se desvían a una cola de mensajes no procesables (*Dead Letter Queue*, DLQ) con su reporte de error, sin tumbar el resto del lote.
2. **Inferencia estructurada con restricción gramatical** — los mensajes válidos se evalúan con salida estructurada mandatoria contra `MensajeAnalizado`. Ante una respuesta mal formada, se ejecuta un reintento de autocorrección sintáctica a temperatura nula.
3. **Evaluación de concurrencia y respaldo heurístico** — ante errores de comunicación o límites de tasa, se activa retroceso exponencial con variación aleatoria (*exponential backoff with jitter*). Agotados los reintentos, se aplica degradación elegante: `puntuacion_relevancia` con las tres dimensiones en 0 (total 0), `apto_para_publicacion = false`, y el motivo de la falla temporal queda registrado en `motivo_seleccion` para auditoría posterior — nunca se omite el registro del `source_id`.
4. **Enriquecimiento paramétrico y persistencia** — los registros consolidados en `AnalisisCognitivo` se transfieren a OCI Object Storage, asegurando el estado inmutable necesario para los agentes de distribución (Contrato 3).

| Tipología de incidencia | Causa raíz detectada | Estrategia de mitigación |
|---|---|---|
| Saturación de contexto (tokens) | Volcados extensos de depuración, logs o binarios en el mensaje. | Truncamiento semántico (20% inicial + 80% final), extrayendo antes patrones de error comunes. |
| Filtración involuntaria de PII | Correos, teléfonos, tokens o credenciales en el texto. | Enmascaramiento determinista por RegEx antes de enviar el texto al LLM. |
| Agotamiento de cuota (*rate limiting*) | Sobrecarga de peticiones simultáneas a la API del modelo. | *Rate-throttling* adaptativo y división dinámica en micro-lotes. |
| Degeneración de formato JSON | Desalineación en la generación de tokens del LLM frente al esquema. | Enforzamiento gramatical rígido vía PydanticAI + *fallback* por RegEx. |

## 6. Plan de Fases de Construcción, Validación y Entrega (S1-1)

| Fase | Denominación técnica | Hitos principales | Entregables formales |
|---|---|---|---|
| **1** | Especificación de contratos y esquemas | Contratos ya formalizados en `esquemas.py` (Contrato 2 acordado con Sergio y Andrea); no se crea un esquema nuevo. | `esquemas.py` (ya existente); especificación OpenAPI del componente. |
| **2** | Construcción del pipeline de inferencia | Diseño de *prompts* estructurados; calibración por *few-shot* para sentimiento (4 categorías), temas y entidades. | `ai_modules/cognitive_analyzer.py` [[5]](#referencias); suite de *prompts* versionados en `ai_modules/prompts/`. |
| **3** | Lógica de *scoring* y trazabilidad | Codificación de la suma 0–6 de `PuntuacionRelevancia`; lógica de `motivo_seleccion`; anclaje de `source_id`. | Lógica de puntuación dentro de `cognitive_analyzer.py` (no se requiere un módulo `relevance_engine.py` aparte, dado que el cálculo es una suma simple, no una fórmula con pesos a mantener por separado); tests unitarios de trazabilidad. |
| **4** | Evaluación de rendimiento y calibración | Pruebas con lotes reales anonimizados de Discord; métricas de precisión sobre las categorías `Literal`. | Informe técnico de evaluación semántica; batería de tests de integración con `pytest`. |
| **5** | Despliegue e integración en OCI | Contenerización del agente; conexión con `orchestration/pipeline_runner.py` [[5]](#referencias); persistencia en OCI Object Storage vía `storage/oci_client.py`. | Imagen Docker homologada; *pipeline* verificado de extremo a extremo; manual técnico de S1-1. |

### Criterios de aceptación

| Criterio | Umbral exigido | Método de verificación |
|---|---|---|
| Trazabilidad integral de fuente | 100.0% de coincidencia | Comprobación automatizada de presencia/unicidad de `source_id` en toda salida persistida. |
| Integridad de `motivo_seleccion` | 0% de violaciones estructurales | Verificación del mínimo de 10 caracteres exigido por el esquema (o el umbral que el equipo decida ratificar). |
| Conformidad estricta de esquema | Cero excepciones de parseo | Validación Pydantic continua sobre `MensajeAnalizado` en el flujo persistido en OCI. |
| Alineación de categoría de enrutamiento | Kappa de Cohen ≥ 0.80 | Evaluación cruzada de `categoria_enrutamiento` entre el agente y un set de prueba etiquetado por supervisores humanos. |
| Concordancia de sentimiento | Exactitud ≥ 85.0% | Matriz de confusión de 4 clases (`sentimiento`) sobre una muestra calificada manualmente. |
| Tiempo de procesamiento por registro | ≤ 1.5 s de media | Telemetría sobre lotes concurrentes de 50 registros en el entorno de despliegue. |

## 7. Conclusiones y Recomendaciones de Implementación

El diseño del Agente de Análisis Cognitivo (S1-1), alineado con el Contrato 2 vigente en `esquemas.py`, sienta las bases analíticas que viabilizan la valorización de la interacción comunitaria digital. La combinación de categorías discretas auditables (`sentimiento`, `categoria_enrutamiento`) con una puntuación entera simple (`puntuacion_relevancia`) y la documentación obligatoria de `source_id` y `motivo_seleccion` garantiza el cumplimiento del Requisito R2 [[2]](#referencias) sin depender de una fórmula matemática que el equipo tendría que mantener y recalibrar por separado.

Se recomienda, durante las pruebas de integración, monitorizar la distribución de `puntuacion_relevancia.total` y de `categoria_enrutamiento` frente a las decisiones de curaduría humana en el panel de Streamlit. Si se detecta que el modelo sobrestima o subestima sistemáticamente algún sub-puntaje, la corrección se hace ajustando los ejemplos *few-shot* del prompt en `ai_modules/prompts/` — no ponderaciones internas, ya que el esquema vigente no las contempla.

---

## Referencias

1. Hackathon ONE G10 — Oracle Next Education & Alura, Proyecto 3: *CommunityLab* (brief oficial del proyecto; requisito obligatorio de persistencia en OCI Object Storage, capa Always Free).
2. «CommunityLab · Anexo de revisión de esquemas», Equipo 34 (Sergio Rebolledo) — origen de la numeración de requisitos (R2, R7, etc.) y de la matriz de cumplimiento interna del equipo.
3. «Especificación y Validación de Contratos JSON Canónicos con Pydantic» — Anexo Arquitectónico Armonizado, Equipo 34 (Michael Antonio Chacón Rossell), y el diff de trabajo de Sergio Rebolledo (`esquemas_propuesto.py`) — definen conjuntamente el Contrato 2 (`AnalisisCognitivo` / `MensajeAnalizado` / `PuntuacionRelevancia` / `ResumenComunidad`) vigente, fuente de verdad de esta revisión.
4. Documento fuente original: sesión compartida de Gemini, «Plan de Diseño y Construcción del Agente de Análisis Cognitivo para CommunityLab» — borrador base, ya reconciliado con el diseño oficial en esta versión.
5. Documento de organización del repositorio GitHub de CommunityLab — estructura de carpetas (`ai_modules/`, `orchestration/`, `storage/`) y mapeo de responsabilidades del equipo.

---

*Documento alineado con el Contrato 2 vigente en `esquemas.py`. Cualquier cambio futuro a los campos aquí descritos requiere el mismo consenso de equipo ya acordado para modificar los contratos de datos.*
