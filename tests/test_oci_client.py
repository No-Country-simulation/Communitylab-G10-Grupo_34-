"""Pruebas unitarias para storage/oci_client.py usando un cliente OCI simulado
(sin red real). La prueba de integración contra OCI real vive al final,
marcada con @pytest.mark.integration y se omite si no hay credenciales
(ver pyproject.toml: `addopts = "-m 'not integration'"`).
"""

from __future__ import annotations

import json
import os
from datetime import UTC

import pytest
from oci.exceptions import ServiceError

from storage.oci_client import OCIConfig, OCIStorageClient


class FakeOCIBackend:
    """Simula el ObjectStorageClient del SDK: guarda objetos en memoria y
    reproduce el comportamiento real de if_none_match='*' (409/412 si la
    ruta ya existe)."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.put_calls = 0
        self.get_calls = 0

    def put_object(self, *, object_name, put_object_body, if_none_match=None, **_kwargs):
        self.put_calls += 1
        if if_none_match == "*" and object_name in self.store:
            raise ServiceError(
                status=412, code="IfNoneMatchFailed", headers={}, message="Object already exists"
            )
        self.store[object_name] = put_object_body

    def get_object(self, *, object_name, **_kwargs):
        self.get_calls += 1
        if object_name not in self.store:
            raise ServiceError(status=404, code="ObjectNotFound", headers={}, message="Not found")
        body = self.store[object_name]

        class _Resp:
            class _Data:
                def __init__(self, content):
                    self.content = content

            def __init__(self, content):
                self.data = self._Data(content)

        return _Resp(body)

    def get_namespace(self):
        class _Resp:
            data = "fake-namespace"

        return _Resp()

    def get_bucket(self, **_kwargs):
        class _Resp:
            class _Data:
                storage_tier = "Standard"

            data = _Data()

        return _Resp()


@pytest.fixture
def client() -> OCIStorageClient:
    """Cliente con backend simulado, sin tocar credenciales reales ni la red."""
    c = OCIStorageClient.__new__(OCIStorageClient)
    c.config = OCIConfig(bucket_name="test-bucket")
    c._client = FakeOCIBackend()
    c._namespace = "fake-namespace"
    import structlog

    c._log = structlog.get_logger("test").bind(component="test")
    return c


# --- build_object_path ---------------------------------------------------


def test_build_object_path_formato_esperado(client):
    ruta = client.build_object_path("2026-Semana-38", "run-abc123", 1)
    assert ruta == "activos/2026-Semana-38/run-abc123/revision-001.json"


@pytest.mark.parametrize(
    "periodo,run_id",
    [
        ("2026/../etc", "run-1"),
        ("2026-S38", "run/../secreto"),
        ("", "run-1"),
        ("2026 S38", "run-1"),  # espacio no permitido
    ],
)
def test_build_object_path_rechaza_segmentos_invalidos(client, periodo, run_id):
    with pytest.raises(ValueError):
        client.build_object_path(periodo, run_id, 1)


@pytest.mark.parametrize("numero_revision", [0, -1, -100])
def test_build_object_path_rechaza_revision_menor_a_uno(client, numero_revision):
    with pytest.raises(ValueError):
        client.build_object_path("p", "r", numero_revision)


# --- serialización del payload -------------------------------------------


def test_upload_rechaza_tipo_no_soportado(client):
    resultado = client.upload_package(object(), "p", "run-1", 1)
    assert resultado.status_almacenamiento == "guardado_error"
    assert "no soportado" in resultado.mensaje_error
    assert client._client.put_calls == 0  # nunca debe intentar subir


def test_upload_serializa_datetime_dentro_de_dict(client):
    from datetime import datetime

    payload = {"generado_en": datetime(2026, 9, 28, tzinfo=UTC)}
    resultado = client.upload_package(payload, "p", "run-dt", 1)
    assert resultado.status_almacenamiento == "guardado_con_exito"
    guardado = json.loads(client._client.store[resultado.ruta_objeto])
    assert guardado["generado_en"] == "2026-09-28T00:00:00+00:00"


def test_upload_advierte_si_payload_trae_estado_precompuesto(client, capsys=None):
    payload = {
        "almacenamiento_oci": {"status_almacenamiento": "guardado_con_exito"},
        "dato": 1,
    }
    # No debe fallar: solo advertir y subir igual con el estado real resultante.
    resultado = client.upload_package(payload, "p", "run-warn", 1)
    assert resultado.status_almacenamiento == "guardado_con_exito"


# --- inmutabilidad / idempotencia -----------------------------------------


def test_upload_roundtrip_exitoso(client):
    resultado = client.upload_package({"a": 1}, "p", "run-ok", 1)
    assert resultado.status_almacenamiento == "guardado_con_exito"
    assert resultado.comprobacion_lectura is True
    assert resultado.hash_sha256_subido == resultado.hash_sha256_recuperado


def test_reintento_idempotente_mismo_contenido(client):
    r1 = client.upload_package({"a": 1}, "p", "run-idem", 1)
    r2 = client.upload_package({"a": 1}, "p", "run-idem", 1)  # mismo contenido exacto
    assert r1.status_almacenamiento == "guardado_con_exito"
    assert r2.status_almacenamiento == "guardado_con_exito"
    assert r2.reintento_idempotente is True
    # El contenido original no fue sobrescrito
    assert json.loads(client._client.store[r1.ruta_objeto]) == {"a": 1}


def test_colision_de_inmutabilidad_contenido_distinto(client):
    r1 = client.upload_package({"a": 1}, "p", "run-col", 1)
    r2 = client.upload_package({"a": 2}, "p", "run-col", 1)  # misma ruta, contenido distinto
    assert r1.status_almacenamiento == "guardado_con_exito"
    assert r2.status_almacenamiento == "guardado_error"
    assert "colisión" in r2.mensaje_error.lower() or "revisión inmutable" in r2.mensaje_error.lower()
    # El contenido original se conserva intacto
    assert json.loads(client._client.store[r1.ruta_objeto]) == {"a": 1}


# --- retry_upload_from_disk -------------------------------------------


def test_retry_upload_from_disk_requiere_json_valido(client, tmp_path):
    archivo_malo = tmp_path / "paquete_corrupto.json"
    archivo_malo.write_text("{esto no es json valido")

    resultado = client.retry_upload_from_disk(
        archivo_malo, "p", "run-bad", 1, request_id="req-99"
    )
    assert resultado.status_almacenamiento == "guardado_error"
    assert "JSON válido" in resultado.mensaje_error
    assert client._client.put_calls == 0  # nunca debe llegar a subirse


def test_retry_upload_from_disk_archivo_inexistente(client, tmp_path):
    resultado = client.retry_upload_from_disk(
        tmp_path / "no_existe.json", "p", "run-x", 1, request_id="req-1"
    )
    assert resultado.status_almacenamiento == "guardado_error"
    assert "no encontrado" in resultado.mensaje_error


def test_retry_upload_from_disk_sube_json_valido(client, tmp_path):
    archivo = tmp_path / "paquete.json"
    archivo.write_text(json.dumps({"ok": True}))

    resultado = client.retry_upload_from_disk(
        archivo, "p", "run-good", 1, request_id="req-2"
    )
    assert resultado.status_almacenamiento == "guardado_con_exito"


# --- precedencia de credenciales (env vs ~/.oci/config) --------------------


def test_env_vars_tienen_prioridad_sobre_config_file(monkeypatch, tmp_path):
    """Si OCI_USER_OCID está en el entorno, debe usarse aunque exista un
    ~/.oci/config válido — para que el perfil personal de un compañero no
    reemplace en silencio las credenciales de servicio del equipo."""
    key_file = tmp_path / "key.pem"
    key_file.write_text("fake-key")
    fake_home_config = tmp_path / "oci_config"
    fake_home_config.write_text("[DEFAULT]\nuser=ocid1.user.oc1..personal\n")

    monkeypatch.setenv("OCI_USER_OCID", "ocid1.user.oc1..servicio")
    monkeypatch.setenv("OCI_FINGERPRINT", "aa:bb")
    monkeypatch.setenv("OCI_KEY_FILE", str(key_file))
    monkeypatch.setenv("OCI_TENANCY_OCID", "ocid1.tenancy.oc1..x")
    monkeypatch.setenv("OCI_REGION", "mx-queretaro-1")

    capturado = {}

    def fake_validate_config(cfg):
        capturado["config"] = cfg

    class FakeClient:
        def __init__(self, cfg, **kwargs):
            capturado["client_config"] = cfg

        def get_namespace(self):
            class R:
                data = "ns"

            return R()

    import oci as oci_module

    monkeypatch.setattr(oci_module.config, "validate_config", fake_validate_config)
    monkeypatch.setattr(oci_module.config, "from_file", lambda **_k: pytest.fail(
        "no debió leer ~/.oci/config habiendo variables de entorno"
    ))
    monkeypatch.setattr(oci_module.object_storage, "ObjectStorageClient", FakeClient)
    monkeypatch.setattr(os.path, "isfile", lambda p: str(p) == str(key_file))

    cfg = OCIConfig.from_env()
    OCIStorageClient(cfg)

    assert capturado["config"]["user"] == "ocid1.user.oc1..servicio"


def test_env_ocid_con_key_file_invalido_no_cae_a_config_personal(monkeypatch, tmp_path):
    """Si OCI_USER_OCID está definido pero OCI_KEY_FILE no apunta a un
    archivo válido, el cliente NO debe caer en silencio a ~/.oci/config
    aunque ese archivo exista y sea válido — debe quedar sin credenciales
    (comentario de revisión de Roberto en el PR #14)."""
    fake_home_config = tmp_path / "oci_config"
    fake_home_config.write_text("[DEFAULT]\nuser=ocid1.user.oc1..personal\n")

    monkeypatch.setenv("OCI_USER_OCID", "ocid1.user.oc1..servicio")
    monkeypatch.setenv("OCI_KEY_FILE", str(tmp_path / "no_existe.pem"))  # clave inválida a propósito
    monkeypatch.setenv("OCI_FINGERPRINT", "aa:bb")
    monkeypatch.setenv("OCI_TENANCY_OCID", "ocid1.tenancy.oc1..x")
    monkeypatch.setenv("OCI_REGION", "mx-queretaro-1")
    monkeypatch.setenv("OCI_CONFIG_FILE", str(fake_home_config))

    import oci as oci_module

    monkeypatch.setattr(
        oci_module.config,
        "from_file",
        lambda **_k: pytest.fail(
            "no debió leer ningún archivo de config: OCI_USER_OCID estaba "
            "definido con una clave inválida, no debe haber fallback"
        ),
    )

    cfg = OCIConfig.from_env()
    cliente = OCIStorageClient(cfg)

    assert cliente._client is None  # sin credenciales válidas, no un perfil ajeno


# --- integración real (omitida por defecto, ver pyproject.toml) -----------


@pytest.mark.integration
def test_roundtrip_real_contra_oci():
    """Sube y lee un objeto real. Requiere credenciales válidas en el entorno.
    Ejecutar explícitamente con: uv run pytest -m integration
    """
    if not os.getenv("OCI_USER_OCID") and not os.path.isfile(os.path.expanduser("~/.oci/config")):
        pytest.skip("no hay credenciales OCI disponibles en este entorno")

    client = OCIStorageClient()
    diagnostico = client.check_connection()
    assert diagnostico["conectado"], diagnostico.get("motivo")

    resultado = client.upload_package(
        {"prueba": "integracion"}, "diagnostico-tests", "run-pytest-integration", 1,
    )
    assert resultado.status_almacenamiento == "guardado_con_exito"
    assert resultado.comprobacion_lectura is True
