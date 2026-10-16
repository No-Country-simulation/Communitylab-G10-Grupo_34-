import json
from pathlib import Path
from types import SimpleNamespace
from esquemas import ResumenSemanal, ActivosGenerados

import pytest

import generador_ia
from esquemas import (
    IngestionLote,
    MensajeAnalizado,
    PuntuacionRelevancia,
)


@pytest.fixture
def datos_prueba():
    ruta = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "raw"
        / "lote_prueba_01.json"
    )

    with ruta.open("r", encoding="utf-8") as archivo:
        lote = IngestionLote(**json.load(archivo))

    interaccion = next(
        item for item in lote.interacciones
        if item.id == "msg_001"
    )

    analisis = MensajeAnalizado(
        source_id="msg_001",
        sentimiento="Altamente Positivo",
        categoria_enrutamiento="Logro",
        regla_aplicada="Logro técnico documentado",
        temas=["OCI", "Base de datos"],
        entidades_relevantes=["OCI"],
        puntuacion_relevancia=PuntuacionRelevancia(
            evidencia_explicita=2,
            utilidad_comunitaria=2,
            claridad_contexto=2,
            total=6,
        ),
        motivo_seleccion=(
            "Documenta un logro técnico concreto."
        ),
        requiere_soporte=False,
        apto_para_publicacion=True,
    )

    return interaccion, analisis


def cliente_simulado(texto):
    def generate_content(**kwargs):
        return SimpleNamespace(text=texto)

    return SimpleNamespace(
        models=SimpleNamespace(
            generate_content=generate_content
        )
    )


def test_generar_post_valido_y_trazable(
    datos_prueba, monkeypatch
):
    interaccion, analisis = datos_prueba

    respuesta = json.dumps({
        "titulo": "Primer despliegue de base de datos en OCI",
        "canal_recomendado": "LinkedIn Oficial",
        "cuerpo": (
            "La comunidad compartió conocimientos y logró "
            "completar un primer despliegue de base de datos."
        ),
        "hashtags": ["#OCI", "#ComunidadTech"],
        "source_ids": ["id_inventado_por_ia"],
    })

    monkeypatch.setattr(
        generador_ia,
        "crear_cliente_gemini",
        lambda: cliente_simulado(respuesta),
    )

    post = generador_ia.generar_post_con_gemini(
        interaccion, analisis
    )

    assert post.titulo
    assert len(post.cuerpo) >= 20
    assert isinstance(post.hashtags, list)

    # La trazabilidad procede del análisis validado.
    assert post.source_ids == [analisis.source_id]
    assert "id_inventado_por_ia" not in post.source_ids


def test_rechaza_source_id_diferente(
    datos_prueba, monkeypatch
):
    interaccion, analisis = datos_prueba
    analisis.source_id = "msg_diferente"

    def cliente_no_debe_crearse():
        raise AssertionError(
            "No debe llamarse a Gemini si los IDs no coinciden."
        )

    monkeypatch.setattr(
        generador_ia,
        "crear_cliente_gemini",
        cliente_no_debe_crearse,
    )

    with pytest.raises(ValueError, match="source_id"):
        generador_ia.generar_post_con_gemini(
            interaccion, analisis
        )


def test_rechaza_analisis_no_publicable(
    datos_prueba, monkeypatch
):
    interaccion, analisis = datos_prueba
    analisis.apto_para_publicacion = False

    def cliente_no_debe_crearse():
        raise AssertionError(
            "No debe llamarse a Gemini para un caso no publicable."
        )

    monkeypatch.setattr(
        generador_ia,
        "crear_cliente_gemini",
        cliente_no_debe_crearse,
    )

    with pytest.raises(ValueError, match="no publicable"):
        generador_ia.generar_post_con_gemini(
            interaccion, analisis
        )


def test_rechaza_respuesta_vacia(
    datos_prueba, monkeypatch
):
    interaccion, analisis = datos_prueba

    monkeypatch.setattr(
        generador_ia,
        "crear_cliente_gemini",
        lambda: cliente_simulado(""),
    )

    with pytest.raises(ValueError, match="respuesta vacía"):
        generador_ia.generar_post_con_gemini(
            interaccion, analisis
        )


def test_rechaza_json_invalido(
    datos_prueba, monkeypatch
):
    interaccion, analisis = datos_prueba

    monkeypatch.setattr(
        generador_ia,
        "crear_cliente_gemini",
        lambda: cliente_simulado("{json inválido"),
    )

    with pytest.raises(
        ValueError,
        match="estructura inválida",
    ):
        generador_ia.generar_post_con_gemini(
            interaccion, analisis
        )
def test_generar_resumen_valido_y_trazable(
    datos_prueba, monkeypatch
):
    interaccion, analisis = datos_prueba

    respuesta = json.dumps({
        "seccion": "Actividad semanal",
        "titular": "Avances técnicos de la comunidad",
        "resumen": (
            "La comunidad compartió avances técnicos "
            "y experiencias relacionadas con OCI."
        ),
        "source_ids": ["id_inventado_por_ia"],
    })

    monkeypatch.setattr(
        generador_ia,
        "crear_cliente_gemini",
        lambda: cliente_simulado(respuesta),
    )

    resumen = generador_ia.generar_resumen_con_gemini(
        [interaccion], [analisis]
    )

    assert isinstance(resumen, ResumenSemanal)
    assert resumen.titular == "Avances técnicos de la comunidad"
    assert resumen.source_ids == ["msg_001"]
    assert "id_inventado_por_ia" not in resumen.source_ids


def test_resumen_omite_texto_de_casos_no_publicables(
    datos_prueba, monkeypatch
):
    interaccion, analisis = datos_prueba
    texto_privado = "TEXTO_QUE_NO_DEBE_LLEGAR_AL_PROMPT"

    interaccion.texto = texto_privado
    analisis.apto_para_publicacion = False

    respuesta = json.dumps({
        "seccion": "Actividad semanal",
        "titular": "Temas de la comunidad",
        "resumen": (
            "Durante la semana se identificaron temas "
            "técnicos que requieren seguimiento."
        ),
        "source_ids": ["msg_001"],
    })

    def generar_content_controlado(**kwargs):
        assert texto_privado not in kwargs["contents"]
        return SimpleNamespace(text=respuesta)

    cliente = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=generar_content_controlado
        )
    )

    monkeypatch.setattr(
        generador_ia,
        "crear_cliente_gemini",
        lambda: cliente,
    )

    resumen = generador_ia.generar_resumen_con_gemini(
        [interaccion], [analisis]
    )

    assert resumen.source_ids == ["msg_001"]


def test_resumen_rechaza_analisis_sin_interaccion(
    datos_prueba, monkeypatch
):
    _, analisis = datos_prueba

    def cliente_no_debe_crearse():
        raise AssertionError(
            "No debe llamarse a Gemini sin registros válidos."
        )

    monkeypatch.setattr(
        generador_ia,
        "crear_cliente_gemini",
        cliente_no_debe_crearse,
    )

    with pytest.raises(ValueError, match="No hay análisis"):
        generador_ia.generar_resumen_con_gemini(
            [], [analisis]
        )

def test_generar_activos_con_gemini_integra_post_y_resumen(
    datos_prueba, monkeypatch
):
    interaccion, analisis = datos_prueba

    from esquemas import CasoNoPublicable

    post = {
        "titulo": "Logro técnico de la comunidad",
        "canal_recomendado": "LinkedIn Oficial",
        "cuerpo": (
            "La comunidad avanzó en su primer despliegue "
            "técnico con apoyo de las guías compartidas."
        ),
        "hashtags": ["#OCI"],
        "source_ids": ["msg_001"],
    }

    resumen = {
        "seccion": "Actividad semanal",
        "titular": "Avances técnicos de la comunidad",
        "resumen": (
            "Durante la semana se compartieron avances "
            "técnicos y experiencias relacionadas con OCI."
        ),
        "source_ids": ["msg_001"],
    }

    monkeypatch.setattr(
        generador_ia,
        "generar_post_con_gemini",
        lambda interaccion, analisis: (
            generador_ia.PostLinkedIn.model_validate(post)
        ),
    )

    monkeypatch.setattr(
        generador_ia,
        "generar_resumen_con_gemini",
        lambda interacciones, analisis_lista: (
            ResumenSemanal.model_validate(resumen)
        ),
    )

    activos = generador_ia.generar_activos_con_gemini(
        [interaccion], [analisis]
    )

    assert isinstance(activos, ActivosGenerados)
    assert activos.post_linkedin.source_ids == ["msg_001"]
    assert activos.resumen_semanal.source_ids == ["msg_001"]
    assert activos.casos_no_publicables == []


def test_generar_activos_con_gemini_rechaza_sin_post_publicable(
    datos_prueba, monkeypatch
):
    interaccion, analisis = datos_prueba
    analisis.apto_para_publicacion = False

    def no_debe_generar_post(*args, **kwargs):
        raise AssertionError(
            "No debe intentar generar un post no publicable."
        )

    monkeypatch.setattr(
        generador_ia,
        "generar_post_con_gemini",
        no_debe_generar_post,
    )

    with pytest.raises(ValueError, match="No se encontró"):
        generador_ia.generar_activos_con_gemini(
            [interaccion], [analisis]
        )
