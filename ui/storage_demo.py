"""Persistencia explícitamente local: nunca produce evidencia de OCI."""
import json
from pathlib import Path

LOCAL_ROOT = Path(__file__).resolve().parents[1] / 'data' / 'oci_sim'


def guardar_local(package, object_path, root=None):
    root = Path(root) if root is not None else LOCAL_ROOT
    # Aplanar la clave evita interpretar rutas externas suministradas por un lote.
    filename = object_path.replace('/', '__').replace('\\', '__')
    if ':' in filename or filename in ('', '.', '..'):
        raise ValueError('Ruta de objeto inválida')
    root.mkdir(parents=True, exist_ok=True)
    destination = root / filename
    content = json.dumps(package, ensure_ascii=False, sort_keys=True, indent=2)
    try:
        with destination.open('x', encoding='utf-8') as output:
            output.write(content)
    except FileExistsError:
        if destination.read_text(encoding='utf-8') != content:
            raise ValueError('La revisión ya existe con otro contenido')
    if destination.read_text(encoding='utf-8') != content:
        raise ValueError('No coincide la lectura posterior')
    return str(destination)
