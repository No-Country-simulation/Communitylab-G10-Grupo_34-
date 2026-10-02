from esquemas import Interaccion, PostLinkedIn
def buscar_interaccion_por_source_id(source_id, interacciones):
    interaccion_encontrada = None

    for interaccion in interacciones:
        if interaccion.id == source_id:
            interaccion_encontrada = interaccion
            return {
                "encontrado": True,
                "interaccion": interaccion_encontrada
            }
    return {
        "encontrado": False,
        "interaccion": None
        }
def generar_post_linkedin(interaccion, analisis):

    if interaccion.id != analisis.source_id:
        raise ValueError("La interacción y el análisis no corresponden al mismo source_id")
    if analisis.entidades_relevantes:
        tema_principal = analisis.entidades_relevantes[0]
    else:
        tema_principal = analisis.temas[0]
    return PostLinkedIn(
            titulo=f"Primer despliegue exitoso en {tema_principal}",
            canal_recomendado="LinkedIn Oficial",
            cuerpo=interaccion.texto,
            hashtags=[f"#{tema}" for tema in analisis.temas],
            source_ids=[analisis.source_id]

        )