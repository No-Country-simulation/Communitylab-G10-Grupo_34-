# Configuración del entorno — CommunityLab (Hackathon ONE G10)

Este proyecto usa **uv** como administrador de paquetes Python. Con `pyproject.toml` y `.python-version` ya fijados, `uv` instala automáticamente Python 3.11 si no lo tienen, y resuelve las mismas versiones de dependencias en Windows, macOS y Linux.

## 1. Instalar uv (una sola vez por máquina)

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verifiquen con `uv --version`.

## 2. Clonar el repo y sincronizar el entorno

```bash
git clone <url-del-repo>
cd communitylab
uv sync
```

`uv sync` lee `pyproject.toml` y `.python-version`, descarga Python 3.11 si hace falta, crea el `.venv` local y instala las dependencias exactas.

## 3. Generar y compartir el lockfile (lo hace la primera persona, una sola vez)

```bash
uv lock
git add uv.lock
git commit -m "Fijar versiones exactas de dependencias"
git push
```

A partir de ahí, cada integrante que haga `git pull` + `uv sync` obtiene **exactamente las mismas versiones**, sin importar su sistema operativo. Si alguien necesita agregar una dependencia nueva, usa `uv add <paquete>` (esto actualiza `pyproject.toml` y `uv.lock` automáticamente) en vez de `pip install`.

## 4. Ejecutar los servicios

```bash
# Backend (FastAPI)
uv run uvicorn app.main:app --reload

# Interfaz de curaduría (Streamlit)
uv run streamlit run app/streamlit_app.py
```

## Notas

- **Proveedor de LLM:** aún no definido en el equipo. PydanticAI permite cambiar de modelo sin tocar la arquitectura del agente, así que no bloquea el avance del resto del stack.
- **`oci` (SDK de Oracle):** ya validado como compatible con Python 3.11 en Windows, macOS y Linux (ver README del hackathon, requisito obligatorio de OCI Object Storage).
- Si Windows Defender o el antivirus corporativo bloquea el script de instalación de PowerShell, pueden instalar uv vía `pip install uv` como alternativa (menos recomendable, pero funciona).
