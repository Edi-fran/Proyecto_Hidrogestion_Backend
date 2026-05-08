"""
Punto de entrada WSGI para PythonAnywhere.
No requiere cambiar rutas hardcodeadas — detecta el proyecto automáticamente.

INSTRUCCIONES EN PYTHONANYWHERE:
1. Sube esta carpeta del proyecto a /home/TU_USUARIO/hidrogestion/
2. Ve a: Web → WSGI configuration file → haz clic en el enlace del archivo
3. Borra TODO el contenido del archivo WSGI de PythonAnywhere
4. Pega EXACTAMENTE esto (cambia TU_USUARIO y la carpeta si es diferente):

    import sys, os
    sys.path.insert(0, '/home/TU_USUARIO/hidrogestion')
    from wsgi import application

5. Guarda → Reload
"""
import sys
import os
from pathlib import Path

# Agrega la carpeta del proyecto al path de Python automáticamente
_project_root = str(Path(__file__).resolve().parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Establece el directorio de trabajo para que .env y rutas relativas funcionen
os.chdir(_project_root)

from app import create_app

application = create_app()
