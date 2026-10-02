# Guía de Contribución — CommunityLab (Equipo 34)

Flujo de trabajo para los ocho integrantes del equipo. Si es tu primera vez usando Git en un proyecto compartido, seguí los pasos en orden — no hace falta saber más que esto.

## 0. Antes de empezar

Asegurate de tener el entorno sincronizado (ver `SETUP.md`):

```bash
git clone <url-del-repo>
cd CommunityLab
uv sync
```

## 1. Flujo diario (clone → rama → commit → PR)

**Nunca se trabaja ni se commitea directo sobre `main`.** Cada tarea vive en su propia rama.

```bash
# 1. Actualizá tu main local antes de arrancar algo nuevo
git checkout main
git pull origin main

# 2. Creá tu rama de trabajo
git checkout -b feat/<modulo>-<detalle>

# 3. Trabajá y commiteá en pasos pequeños
git add <archivos>
git commit -m "feat(api): agrega idempotencia con hash sha256"

# 4. Subí tu rama
git push origin feat/<modulo>-<detalle>

# 5. Abrí el Pull Request en GitHub hacia main
#    (mínimo un compañero debe aprobarlo antes de fusionar)
```

### Nombres de rama

`feat/<modulo>-<detalle>` — por ejemplo: `feat/api-idempotencia`, `feat/datos-validador-sqlite`, `feat/ui-panel-aprobacion`.

### Mensajes de commit

Formato corto: `tipo(módulo): qué se hizo`. Tipos comunes: `feat` (funcionalidad nueva), `fix` (corrección), `docs` (documentación), `test` (pruebas).

## 2. Evitar y resolver conflictos

Con ocho personas tocando el mismo repo, el conflicto más común no es de código sino de ramas desactualizadas:

```bash
# Antes de abrir tu PR, traé los últimos cambios de main a tu rama
git checkout feat/<tu-rama>
git pull origin main
```

Si Git marca un conflicto (`CONFLICT` en la terminal), **no lo resuelvas solo/a a las apuradas**: avisá en el canal del equipo antes de forzar un push. Nunca uses `git push --force` sobre una rama que otra persona también esté usando.

## 3. Regla especial sobre `esquemas.py`

Es la única fuente de verdad de los contratos de datos. Ningún cambio se sube sin acuerdo previo del equipo:

1. Proponé el cambio en el canal (o como PR de discusión, sin fusionar).
2. Esperá el visto bueno del grupo responsable de la revisión de `esquemas.py` (ver la tabla de responsabilidades del equipo).
3. Recién ahí se fusiona a `main`, y el resto actualiza su rama local (`git pull origin main`) antes de seguir trabajando sobre los contratos.

## 4. Convenciones ya acordadas (para no reabrir la discusión)

- **Nombre de la clase de validación por registro:** `InteraccionValidada` (propuesta de Sergio, ya en el diff de trabajo). No usar `MensajeAptoParaIA` ni `ValidatedInteractionItem` en código nuevo.
- **`fecha` en `MetadataOrigen`:** se mantiene `str` en la capa de admisión (`Interaccion`); la versión estricta (`datetime`) vive en `MetadataOrigenValidado`, usada solo por `InteraccionValidada`.
- **`request_id` / `schema_version`:** se mantienen así en el JSON de entrada/salida y en OCI. Si querés usar nombres en español dentro del código Python, hacelo con alias de Pydantic (`Field(alias="request_id")`) — y no olvides `model_dump(by_alias=True)` al escribir a `data/raw/`.
- **`id` / `source_id` / `source_ids`:** se mantienen tal cual en los tres contratos (no se unifican). Mapeo interno en SQLite como `id_mensaje_origen` es válido, pero no cambia el nombre en el JSON de salida.

## 5. Antes de pedir revisión

- [ ] `uv run pytest` pasa en local
- [ ] La rama está actualizada con `main`
- [ ] El PR describe qué cambia y por qué (una o dos líneas alcanza)
- [ ] Si tocaste `esquemas.py`, ya tenés el visto bueno del equipo
