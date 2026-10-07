import json

from esquemas import (
    IngestionLote,
    MensajeAnalizado,
    PostLinkedIn,
    ResumenSemanal
)

from generador import (
    buscar_interaccion_por_source_id,
    generar_post_linkedin,
    generar_resumen_semanal
)


# ============================================================
# Análisis de prueba: msg_001
# ============================================================

analisis = MensajeAnalizado(
    source_id="msg_001",
    sentimiento="Altamente Positivo",
    categoria_enrutamiento="Logro",
    regla_aplicada="Testimonio de logro técnico documentado",
    temas=["OCI", "Base de datos", "Despliegue"],
    entidades_relevantes=["OCI"],
    puntuacion_relevancia={
        "evidencia_explicita": 2,
        "utilidad_comunitaria": 2,
        "claridad_contexto": 2,
        "total": 6
    },
    motivo_seleccion=(
        "El mensaje documenta un logro técnico concreto "
        "y agradece las guías de la comunidad."
    ),
    requiere_soporte=False,
    apto_para_publicacion=True
)


# ============================================================
# Análisis de prueba: msg_002
# ============================================================

analisis_2 = MensajeAnalizado(
    source_id="msg_002",
    sentimiento="Positivo",
    categoria_enrutamiento="Logro",
    regla_aplicada="Avance técnico documentado",
    temas=["Pydantic", "Esquemas", "Equipo"],
    entidades_relevantes=["Pydantic"],
    puntuacion_relevancia={
        "evidencia_explicita": 2,
        "utilidad_comunitaria": 2,
        "claridad_contexto": 2,
        "total": 6
    },
    motivo_seleccion=(
        "El mensaje documenta un avance técnico "
        "y una actividad de coordinación del equipo."
    ),
    requiere_soporte=False,
    apto_para_publicacion=True
)


# ============================================================
# Análisis de prueba: msg_003
# ============================================================

analisis_3 = MensajeAnalizado(
    source_id="msg_003",
    sentimiento="Neutro",
    categoria_enrutamiento="Duda",
    regla_aplicada="Consulta técnica sobre integración",
    temas=["n8n", "Webhook", "API"],
    entidades_relevantes=["n8n"],
    puntuacion_relevancia={
        "evidencia_explicita": 2,
        "utilidad_comunitaria": 2,
        "claridad_contexto": 2,
        "total": 6
    },
    motivo_seleccion=(
        "El mensaje plantea una duda técnica concreta "
        "sobre la integración de n8n con una API local."
    ),
    requiere_soporte=True,
    apto_para_publicacion=False
)


# ============================================================
# Cargar lote de prueba
# ============================================================

with open(
    "data/raw/lote_prueba_01.json",
    "r",
    encoding="utf-8"
) as archivo:
    datos = json.load(archivo)

lote = IngestionLote(**datos)


# ============================================================
# Lista de análisis
# ============================================================

analisis_lista = [
    analisis,
    analisis_2,
    analisis_3
]

print(
    "LISTA DE ANALISIS:",
    [a.source_id for a in analisis_lista]
)


# ============================================================
# PRUEBA: búsqueda válida de msg_001
# ============================================================

resultado = buscar_interaccion_por_source_id(
    "msg_001",
    lote.interacciones
)

assert resultado["encontrado"] is True
assert resultado["interaccion"] is not None
assert resultado["interaccion"].id == "msg_001"

print("Búsqueda de msg_001: OK")


# ============================================================
# PRUEBA: generación de PostLinkedIn
# ============================================================

post = generar_post_linkedin(
    resultado["interaccion"],
    analisis
)

assert isinstance(post, PostLinkedIn)
assert post.source_ids == ["msg_001"]

print("PostLinkedIn generado correctamente")


# ============================================================
# PRUEBA: ResumenSemanal
# ============================================================

resumen = generar_resumen_semanal(
    lote.interacciones,
    analisis_lista
)

assert isinstance(resumen, ResumenSemanal)

assert resumen.source_ids == [
    "msg_001",
    "msg_002",
    "msg_003"
]

assert resumen.titular == "Tema destacado: OCI"

print("ResumenSemanal generado correctamente")


# ============================================================
# PRUEBA DE FALLO: source_id inexistente
# ============================================================

resultado_fallo = buscar_interaccion_por_source_id(
    "msg_999",
    lote.interacciones
)

assert resultado_fallo["encontrado"] is False
assert resultado_fallo["interaccion"] is None

print("Fallo controlado: source_id no encontrado")


# ============================================================
# PRUEBA DE TRAZABILIDAD:
#     interacción real + source_id incorrecto
# ============================================================

analisis_inconsistente = analisis.model_copy(
    update={"source_id": "msg_999"}
)

try:
    generar_post_linkedin(
        resultado["interaccion"],
        analisis_inconsistente
    )

except ValueError as error:
    assert str(error) == (
        "La interacción y el análisis no corresponden "
        "al mismo source_id"
    )

    print("Fallo controlado: source_id inconsistente")

else:
    raise AssertionError(
        "Se esperaba ValueError por source_id inconsistente"
    )


print("Todas las pruebas de prueba_generador.py pasaron")

post_duda = generar_post_linkedin(
    lote.interacciones[2],
    analisis_3
)

assert post_duda is None

print("Duda no convertida en LinkedIn: OK")