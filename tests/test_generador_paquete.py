
import json
from pathlib import Path

from esquemas import (
    IngestionLote,
    PuntuacionRelevancia,
    MensajeAnalizado,
    ResumenComunidad,
    AnalisisCognitivo,
    MetadatosEjecucion,
    PaqueteSalida,
)
from generador import generar_activos, construir_paquete_salida


def test_construir_paquete_salida():
    # Cargar el lote sintético del proyecto.
    ruta = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "raw"
        / "lote_prueba_01.json"
    )

    with ruta.open("r", encoding="utf-8") as archivo:
        lote = IngestionLote(**json.load(archivo))

    # Crear resultados de análisis reproducibles.
    puntuacion = PuntuacionRelevancia(
        evidencia_explicita=2,
        utilidad_comunitaria=2,
        claridad_contexto=2,
        total=6,
    )

    analisis_lista = [
        MensajeAnalizado(
            source_id="msg_001",
            sentimiento="Altamente Positivo",
            categoria_enrutamiento="Logro",
            regla_aplicada="Logro técnico documentado",
            temas=["OCI", "Base de datos"],
            entidades_relevantes=["OCI"],
            puntuacion_relevancia=puntuacion,
            motivo_seleccion="Documenta un logro técnico concreto.",
            requiere_soporte=False,
            apto_para_publicacion=True,
        ),
        MensajeAnalizado(
            source_id="msg_002",
            sentimiento="Positivo",
            categoria_enrutamiento="Logro",
            regla_aplicada="Avance técnico documentado",
            temas=["Pydantic", "Equipo"],
            entidades_relevantes=["Pydantic"],
            puntuacion_relevancia=puntuacion,
            motivo_seleccion="Documenta un avance técnico del equipo.",
            requiere_soporte=False,
            apto_para_publicacion=True,
        ),
        MensajeAnalizado(
            source_id="msg_003",
            sentimiento="Neutro",
            categoria_enrutamiento="Duda",
            regla_aplicada="Consulta técnica",
            temas=["n8n", "Webhook", "API"],
            entidades_relevantes=["n8n"],
            puntuacion_relevancia=puntuacion,
            motivo_seleccion="Plantea una duda técnica que requiere atención.",
            requiere_soporte=True,
            apto_para_publicacion=False,
        ),
    ]

    resumen = ResumenComunidad(
        total_interacciones_procesadas=4,
        registros_validos=3,
        registros_rechazados=1,
        sentimiento_predominante="Mixto",
        distribucion_sentimiento={
            "Altamente Positivo": 1,
            "Positivo": 1,
            "Neutro": 1,
        },
        temas_principales=["OCI", "Pydantic", "n8n"],
    )

    analisis_cognitivo = AnalisisCognitivo(
        run_id="run-prueba-001",
        request_id=lote.request_id,
        resumen_comunidad=resumen,
        mensajes_analizados=analisis_lista,
    )

    activos = generar_activos(lote.interacciones, analisis_lista)

    # Los metadatos son sintéticos: aún no representan una llamada a un LLM.
    metadatos = MetadatosEjecucion(
        modelo="prueba_sintetica",
        prompt_version="mvp-sin-llm",
        latencia_ms=0,
        tokens_totales=0,
    )

    paquete = construir_paquete_salida(
        analisis_cognitivo,
        activos,
        metadatos,
    )

    # Verificar el contrato de salida.
    assert isinstance(paquete, PaqueteSalida)
    assert paquete.run_id == "run-prueba-001"
    assert paquete.request_id == lote.request_id

    # La revisión empieza pendiente, nunca aprobada automáticamente.
    assert paquete.revision.estado == "pendiente"
    assert paquete.revision.revisor is None
    assert paquete.revision.fecha_decision is None

    # No afirmar que se almacenó en OCI.
    assert paquete.almacenamiento_oci.status_almacenamiento == "no_iniciado"
    assert paquete.almacenamiento_oci.comprobacion_lectura is False

    # Comprobar que se conservaron los activos y su trazabilidad.
    assert paquete.activos.post_linkedin.source_ids == ["msg_001"]
    assert "msg_003" in paquete.activos.resumen_semanal.source_ids
    assert any(
        caso.source_id == "msg_003"
        for caso in paquete.activos.casos_no_publicables
    )

    # El resumen comunitario debe ser el recibido del análisis.
    assert (
        paquete.analisis_resumido.total_interacciones_procesadas == 4
    )

def test_rechaza_source_id_inexistente():
    import pytest

    from generador import construir_paquete_salida

    from esquemas import (
        AnalisisCognitivo,
        ResumenComunidad,
        MetadatosEjecucion,
        ActivosGenerados,
        PostLinkedIn,
        ResumenSemanal,
    )

    analisis = AnalisisCognitivo(
        run_id="run-prueba-002",
        request_id="req-prueba-001",
        resumen_comunidad=ResumenComunidad(
            total_interacciones_procesadas=1,
            registros_validos=1,
            registros_rechazados=0,
            sentimiento_predominante="Positivo",
            distribucion_sentimiento={"Positivo": 1},
            temas_principales=["Python"],
        ),
        mensajes_analizados=[
            MensajeAnalizado(
                source_id="msg_001",
                sentimiento="Positivo",
                categoria_enrutamiento="Logro",
                regla_aplicada="Logro técnico documentado",
                temas=["Python"],
                entidades_relevantes=["Python"],
                puntuacion_relevancia=PuntuacionRelevancia(
                    evidencia_explicita=2,
                    utilidad_comunitaria=2,
                    claridad_contexto=2,
                    total=6,
                ),
                motivo_seleccion="Ejemplo válido para probar la trazabilidad.",
                requiere_soporte=False,
                apto_para_publicacion=True,
            )
        ],
    )

    # Este activo referencia un mensaje que no existe en el análisis.
    activos = ActivosGenerados(
        post_linkedin=PostLinkedIn(
            titulo="Logro destacado: Python",
            cuerpo="La comunidad documentó un avance técnico en Python.",
            hashtags=["#Python"],
            source_ids=["msg_inexistente"],
        ),
        resumen_semanal=ResumenSemanal(
            seccion="Temas destacados",
            titular="Avances de la comunidad",
            resumen="Se registraron avances técnicos durante la semana.",
            source_ids=["msg_inexistente"],
        ),
        casos_no_publicables=[],
    )

    metadatos = MetadatosEjecucion(
        modelo="prueba_sintetica",
        prompt_version="mvp-sin-llm",
        latencia_ms=0,
        tokens_totales=0,
    )

    with pytest.raises(
        ValueError,
        match="source_id sin respaldo",
    ):
        construir_paquete_salida(analisis, activos, metadatos)