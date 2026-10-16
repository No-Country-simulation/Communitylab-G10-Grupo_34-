import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from pydantic import ValidationError

from esquemas import (
    PostLinkedIn,
    ResumenSemanal,
    ActivosGenerados,
    AnalisisCognitivo,
    MetadatosEjecucion,
    PaqueteSalida,
    CasoNoPublicable
)
from generador import (
    buscar_interaccion_por_source_id,
    registrar_no_publicable,
    construir_paquete_salida
)


VERSION_PROMPTS = "1.0.0"
MODELO_GEMINI = "gemini-3.8-flash"


def crear_cliente_gemini():
    """Carga la configuración y construye el cliente de Gemini."""
    ruta_env = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=ruta_env, override=True)

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "tu_api_key_aqui":
        raise ValueError("GEMINI_API_KEY no está configurada.")

    return genai.Client(api_key=api_key)

def generar_post_con_gemini(interaccion, analisis):
    """Genera una propuesta de LinkedIn validada y trazable."""

    if interaccion.id != analisis.source_id:
        raise ValueError(
            "La interacción y el análisis no corresponden al mismo source_id"
        )

    if not analisis.apto_para_publicacion:
        raise ValueError(
            "No se puede generar una publicación con un análisis no publicable"
        )

    cliente = crear_cliente_gemini()

    prompt = f"""
    Eres redactor de comunicación para una comunidad tecnológica.

    Genera una propuesta de publicación para LinkedIn basándote
    exclusivamente en los datos proporcionados.

    Reglas:
    - No inventes logros, cifras, personas ni resultados.
    - Conserva el sentido del mensaje original.
    - Usa un tono profesional, claro y cercano.
    - Redacta un título y un cuerpo de al menos 20 caracteres.
    - Genera hashtags relacionados con los temas recibidos.
    - No afirmes que la publicación está aprobada o publicada.

    Mensaje original:
    {interaccion.texto}

    Temas identificados:
    {analisis.temas}

    Entidades relevantes:
    {analisis.entidades_relevantes}

    Devuelve exclusivamente los campos del contrato PostLinkedIn.
    """

    respuesta = cliente.models.generate_content(
        model=MODELO_GEMINI,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": PostLinkedIn,
        },
    )

    if not respuesta.text:
        raise ValueError("Gemini devolvió una respuesta vacía.")

    try:
        post = PostLinkedIn.model_validate_json(respuesta.text)
    except ValidationError as error:
        raise ValueError(
            "Gemini devolvió una publicación con estructura inválida."
        ) from error

    # Los IDs proceden del análisis validado, nunca de la IA.
    return post.model_copy(
        update={"source_ids": [analisis.source_id]}
    )
def generar_resumen_con_gemini(interacciones, analisis_lista):
    """Genera un resumen semanal validado y trazable."""

    # Asociar cada análisis con su interacción original.
    interacciones_por_id = {
        interaccion.id: interaccion
        for interaccion in interacciones
    }

    registros = []
    source_ids = []

    for analisis in analisis_lista:
        interaccion = interacciones_por_id.get(
            analisis.source_id
        )

        if interaccion is None:
            continue

        # Evitar generar un resumen sin contenido.
        if not analisis.temas:
            continue

        registro = {
            "source_id": analisis.source_id,
            "sentimiento": analisis.sentimiento,
            "categoria": analisis.categoria_enrutamiento,
            "temas": analisis.temas,
            "apto_para_publicacion": (
                analisis.apto_para_publicacion
            ),
        }

        # El texto original solo se proporciona cuando
        # el análisis permite su publicación.
        if analisis.apto_para_publicacion:
            registro["texto"] = interaccion.texto

        registros.append(registro)
        source_ids.append(analisis.source_id)

    if not registros:
        raise ValueError(
            "No hay análisis con interacción y temas "
            "para generar el resumen semanal."
        )

    cliente = crear_cliente_gemini()

    prompt = f"""
    Eres responsable de resumir la actividad semanal
    de una comunidad tecnológica.

    Redacta un resumen semanal profesional, claro y útil
    para revisión humana.

    Reglas:
    - Usa exclusivamente los datos proporcionados.
    - No inventes logros, cifras ni resultados.
    - Resume los temas y la actividad de la comunidad.
    - No reproduzcas el contenido individual de casos
      que no sean aptos para publicación.
    - Puedes describir sus temas de forma general.
    - No afirmes que el resumen está aprobado o publicado.

    Datos de la semana:
    {registros}

    Devuelve exclusivamente los campos del contrato
    ResumenSemanal en formato JSON.
    """

    respuesta = cliente.models.generate_content(
        model=MODELO_GEMINI,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": ResumenSemanal,
        },
    )

    if not respuesta.text:
        raise ValueError(
            "Gemini devolvió una respuesta vacía."
        )

    try:
        resumen = ResumenSemanal.model_validate_json(
            respuesta.text
        )
    except ValidationError as error:
        raise ValueError(
            "Gemini devolvió un resumen con estructura inválida."
        ) from error

    # La trazabilidad procede de los análisis validados.
    return resumen.model_copy(
        update={"source_ids": source_ids}
    )
def generar_activos_con_gemini(interacciones, analisis_lista):
    """Genera activos con IA y conserva los casos no publicables."""

    analisis_por_id = {
        analisis.source_id: analisis
        for analisis in analisis_lista
    }

    post_linkedin = None

    # Generar un post a partir del primer análisis publicable
    # cuya interacción original exista.
    for analisis in analisis_lista:
        if not analisis.apto_para_publicacion:
            continue

        resultado = buscar_interaccion_por_source_id(
            analisis.source_id,
            interacciones,
        )

        if not resultado["encontrado"]:
            continue

        post_linkedin = generar_post_con_gemini(
            resultado["interaccion"],
            analisis,
        )
        break

    if post_linkedin is None:
        raise ValueError(
            "No se encontró ninguna interacción apta "
            "para generar PostLinkedIn con IA."
        )

    resumen_semanal = generar_resumen_con_gemini(
        interacciones,
        analisis_lista,
    )

    casos_no_publicables = [
        registrar_no_publicable(analisis)
        for analisis in analisis_lista
        if not analisis.apto_para_publicacion
        and analisis.source_id in {
            interaccion.id for interaccion in interacciones
        }
    ]

    # Validar la trazabilidad antes de construir los activos.
    source_ids_validos = set(analisis_por_id)

    source_ids_activos = (
        post_linkedin.source_ids
        + resumen_semanal.source_ids
        + [caso.source_id for caso in casos_no_publicables]
    )

    if not set(source_ids_activos).issubset(source_ids_validos):
        raise ValueError(
            "Hay activos con source_id sin respaldo en el análisis."
        )

    return ActivosGenerados(
        post_linkedin=post_linkedin,
        resumen_semanal=resumen_semanal,
        casos_no_publicables=casos_no_publicables,
    )

def generar_activos_con_gemini(interacciones, analisis_lista):
    """Genera activos con IA y conserva los casos no publicables."""

    analisis_por_id = {
        analisis.source_id: analisis
        for analisis in analisis_lista
    }

    ids_interacciones = {
        interaccion.id for interaccion in interacciones
    }

    post_linkedin = None

    # Buscar el primer análisis publicable con interacción existente.
    for analisis in analisis_lista:
        if not analisis.apto_para_publicacion:
            continue

        resultado = buscar_interaccion_por_source_id(
            analisis.source_id,
            interacciones,
        )

        if not resultado["encontrado"]:
            continue

        post_linkedin = generar_post_con_gemini(
            resultado["interaccion"],
            analisis,
        )
        break

    if post_linkedin is None:
        raise ValueError(
            "No se encontró ninguna interacción apta "
            "para generar PostLinkedIn con IA."
        )

    # Generar la síntesis semanal.
    resumen_semanal = generar_resumen_con_gemini(
        interacciones,
        analisis_lista,
    )

    # Conservar los casos no publicables que tengan respaldo.
    casos_no_publicables = [
        registrar_no_publicable(analisis)
        for analisis in analisis_lista
        if (
            not analisis.apto_para_publicacion
            and analisis.source_id in ids_interacciones
        )
    ]

    # Validar la trazabilidad de todos los activos.
    source_ids_validos = set(analisis_por_id)

    source_ids_activos = (
        post_linkedin.source_ids
        + resumen_semanal.source_ids
        + [
            caso.source_id
            for caso in casos_no_publicables
        ]
    )

    if not set(source_ids_activos).issubset(source_ids_validos):
        raise ValueError(
            "Hay activos con source_id sin respaldo en el análisis."
        )

    return ActivosGenerados(
        post_linkedin=post_linkedin,
        resumen_semanal=resumen_semanal,
        casos_no_publicables=casos_no_publicables,
    )
def generar_activos_con_gemini(interacciones, analisis_lista):
    """Genera activos con IA y conserva los casos no publicables."""

    resumen_semanal = generar_resumen_con_gemini(
        interacciones,
        analisis_lista,
    )

    casos_no_publicables = [
        registrar_no_publicable(analisis)
        for analisis in analisis_lista
        if not analisis.apto_para_publicacion
    ]

    post_linkedin = None

    for analisis in analisis_lista:
        if not analisis.apto_para_publicacion:
            continue

        resultado = buscar_interaccion_por_source_id(
            analisis.source_id,
            interacciones,
        )

        if not resultado["encontrado"]:
            continue

        post_linkedin = generar_post_con_gemini(
            resultado["interaccion"],
            analisis,
        )
        break

    if post_linkedin is None:
        raise ValueError(
            "No se encontró ninguna interacción apta "
            "para generar PostLinkedIn"
        )

    return ActivosGenerados(
        post_linkedin=post_linkedin,
        resumen_semanal=resumen_semanal,
        casos_no_publicables=casos_no_publicables,
    )

def generar_paquete_con_gemini(analisis_cognitivo, interacciones):
    """Genera activos con Gemini y construye el paquete trazable."""

    inicio = time.perf_counter()

    activos = generar_activos_con_gemini(
        interacciones,
        analisis_cognitivo.mensajes_analizados,
    )

    latencia_ms = int((time.perf_counter() - inicio) * 1000)

    metadatos = MetadatosEjecucion(
        modelo=MODELO_GEMINI,
        prompt_version=VERSION_PROMPTS,
        latencia_ms=latencia_ms,
        tokens_totales=0,
    )

    return construir_paquete_salida(
        analisis_cognitivo,
        activos,
        metadatos,
    )
