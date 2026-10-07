from esquemas import Interaccion, PostLinkedIn, ResumenSemanal
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
    if not analisis.apto_para_publicacion:
        return None
    if analisis.entidades_relevantes:
        tema_principal = analisis.entidades_relevantes[0]
    else:
        tema_principal = analisis.temas[0]
    return PostLinkedIn(
            titulo=f"Logro destacado: {tema_principal}",
            canal_recomendado="LinkedIn Oficial",
            cuerpo=interaccion.texto,
            hashtags=[f"#{tema}" for tema in analisis.temas],
            source_ids=[analisis.source_id]

        )
def generar_resumen_semanal(interacciones, analisis_lista):
    source_ids = []
    textos = []
    casos_sin_interaccion = []

    for analisis in analisis_lista:

        resultado = buscar_interaccion_por_source_id(
            analisis.source_id,
            interacciones
        )
        if resultado["encontrado"]:
            interaccion = resultado["interaccion"]
            textos.append(interaccion.texto)
        else:
            casos_sin_interaccion.append(analisis.source_id)

        source_ids.append(analisis.source_id)

    conteo_temas = {}

    for analisis in analisis_lista:
         for tema in analisis.temas:
            if tema in conteo_temas:
                conteo_temas[tema] +=1
            else:
                conteo_temas[tema] =1
    mayor_tema = None
    mayor_conteo = 0

    for tema, cantidad in conteo_temas.items():
            if cantidad > mayor_conteo:
                mayor_conteo = cantidad
                mayor_tema = tema

    texto_concatenado = " ".join(textos)
    return ResumenSemanal(
            seccion="Temas destacados",
            titular=f"Tema destacado: {mayor_tema}",
            resumen=texto_concatenado,
            source_ids=source_ids
        )