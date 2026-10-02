import json

from esquemas import IngestionLote, MensajeAnalizado, PostLinkedIn

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
    motivo_seleccion="El mensaje documenta un logro técnico concreto y agradece las guías de la comunidad.",
    requiere_soporte=False,
    apto_para_publicacion=True
)
from generador import buscar_interaccion_por_source_id, generar_post_linkedin


with open("data/raw/lote_prueba_01.json", "r", encoding="utf-8") as archivo:
    datos = json.load(archivo)

lote = IngestionLote(**datos)

resultado = buscar_interaccion_por_source_id(
    "msg_001",
    lote.interacciones
)

print(resultado)
print(analisis)
post = generar_post_linkedin(resultado["interaccion"], analisis)

print(post)

assert isinstance(post, PostLinkedIn)
assert post.source_ids == ["msg_001"]

print("PostLinkedIn generado correctamente")