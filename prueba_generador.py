import json

from esquemas import (
    IngestionLote,
    MensajeAnalizado,
    PostLinkedIn,
    ResumenSemanal,
    ActivosGenerados
)

from generador import (
    buscar_interaccion_por_source_id,
    generar_post_linkedin,
    generar_resumen_semanal,
    registrar_no_publicable,
    generar_activos
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

resumen, casos_no_publicables = generar_resumen_semanal(
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

# =============================================================
# Prueba generación de activos
# =============================================================
activos = generar_activos(
    lote.interacciones,
    analisis_lista
)

assert isinstance(activos, ActivosGenerados)
assert isinstance(activos.post_linkedin, PostLinkedIn)
assert isinstance(activos.resumen_semanal, ResumenSemanal)
assert len(activos.casos_no_publicables) == 1
assert activos.casos_no_publicables[0].source_id == "msg_003"

print("ActivosGenerados integrado correctamente: OK")

analisis_sin_publicables = [
    analisis.model_copy(update={"apto_para_publicacion": False}),
    analisis_2.model_copy(update={"apto_para_publicacion": False}),
    analisis_3.model_copy(update={"apto_para_publicacion": False})
]
try:
    generar_activos(
        lote.interacciones,
        analisis_sin_publicables
    )
except ValueError as error:
    assert str(error) == "No se encontró ninguna interacción apta para generar PostLinkedIn"
    print("Fallo controlado: ningún análisis publicable")
else:
    raise AssertionError(
        "Se esperaba ValueError cuando no existen análisis publicables"
    )

# Comprobación de casos no publicables
assert len(casos_no_publicables) == 1
assert casos_no_publicables[0].source_id == "msg_003"
assert casos_no_publicables[0].categoria_enrutamiento == "Duda"
assert casos_no_publicables[0].requiere_soporte is True

print("ResumenSemanal generado correctamente")
print("Casos no publicables conservados: OK")

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

registro_duda = registrar_no_publicable(analisis_3)

assert registro_duda.source_id == "msg_003"
assert registro_duda.categoria_enrutamiento == "Duda"
assert registro_duda.requiere_soporte is True

print("Duda conservada para ruteo: OK")