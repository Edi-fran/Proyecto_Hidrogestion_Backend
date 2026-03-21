# HidroGestión Suite

Proyecto completo con dos carpetas:

- `backend/` en la raíz actual (`run.py`, `app/`, `instance/`, `uploads/`)
- `frontend/` con el proyecto Expo Go

## Backend Flask

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run.py
```

Rutas principales:
- API health: `http://127.0.0.1:5000/api/health`
- Dashboard: `http://127.0.0.1:5000/dashboard/login`

Credenciales demo:
- admin / Admin123*
- tecnico / Tecnico123*
- socio / Socio123*

## Frontend Expo

Entra a `frontend/hidrogestion_frontend` y ejecuta:

```powershell
npm install
npx expo install expo-image-picker expo-location expo-status-bar @react-native-async-storage/async-storage react-native
npx expo start -c
```

Actualiza `src/config.ts` con la IP local del backend.
