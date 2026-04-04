# 💧 HidroGestión Suite

<div align="center">

![HidroGestión](https://img.shields.io/badge/HidroGestión-Sistema%20de%20Agua-1A5FA8?style=for-the-badge&logo=water&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1.2-000000?style=for-the-badge&logo=flask&logoColor=white)
![React Native](https://img.shields.io/badge/React%20Native-Expo%20SDK%2054-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-Auth-000000?style=for-the-badge&logo=jsonwebtokens&logoColor=white)

**Sistema Comunitario de Gestión de Agua Potable**

Proyecto completo con backend Flask + app móvil React Native + dashboard web + módulo IoT con ESP32-S3 y caudalímetro YF-S201.

</div>

---

## 📁 Estructura del Repositorio

```
hidrogestion-suite/
├── backend/                        # API Flask + Dashboard Web
│   ├── run.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── instance/
│   │   └── hidrogestion.sqlite
│   ├── uploads/
│   └── app/
│       ├── __init__.py
│       ├── models.py
│       ├── routes/
│       ├── templates/
│       └── static/
│
└── frontend/
    └── hidrogestion_frontend/      # App móvil React Native (Expo)
        ├── App.tsx
        ├── package.json
        └── src/
            ├── config.ts           # ← Configura aquí la IP del backend
            ├── screens/
            └── services/
```

---

## 🚀 Instalación y Ejecución

### ⚙️ Backend Flask

**1. Entrar a la carpeta del backend**
```powershell
cd backend
```

**2. Crear entorno virtual e instalar dependencias**
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

**3. Configurar variables de entorno**
```powershell
Copy-Item .env.example .env
```
Edita `.env` con tus valores de `SECRET_KEY` y `JWT_SECRET_KEY`.

**4. Iniciar el servidor**
```powershell
.\.venv\Scripts\python.exe run.py
```

**Accesos disponibles:**

| Servicio | URL |
|---|---|
| API Health | `http://127.0.0.1:5000/api/health` |
| Dashboard Web | `http://127.0.0.1:5000/dashboard/login` |
| API REST | `http://127.0.0.1:5000/api` |

---

### 📱 Frontend Expo (App Móvil)

**1. Entrar a la carpeta del frontend**
```powershell
cd frontend/hidrogestion_frontend
```

**2. Instalar dependencias npm**
```powershell
npm install
```

**3. Instalar dependencias nativas de Expo**
```powershell
npx expo install expo-image-picker expo-location expo-status-bar @react-native-async-storage/async-storage react-native
npx expo install expo-camera expo-web-browser expo-sharing
```

**4. Configurar la IP del backend**

Edita el archivo `src/config.ts`:
```typescript
// Cambia esta IP por la IP de tu PC en la red local
export const API_BASE_URL = 'http://192.168.X.X:5000';
```

> 💡 Para encontrar tu IP local ejecuta `ipconfig` en Windows y busca la dirección IPv4.

**5. Iniciar Expo**
```powershell
npx expo start -c
```

Escanea el QR con la app **Expo Go** en tu celular (Android/iOS).

---

## 🔑 Credenciales de Prueba

> ⚠️ Solo para entorno de desarrollo. Cámbialas en producción.

| Rol | Username | Contraseña | Acceso |
|---|---|---|---|
| ADMIN | `admin` | `Admin123*` | Todo el sistema |
| TECNICO | `tecnico` | `Tecnico123*` | Operaciones de campo |
| SOCIO | `socio` | `Socio123*` | Consultas personales |

---

## 🛠️ Stack Tecnológico

### Backend
| Librería | Versión | Uso |
|---|---|---|
| Flask | 3.1.2 | Framework web principal |
| Flask-SQLAlchemy | 3.1.1 | ORM — 33 modelos |
| Flask-JWT-Extended | 4.7.1 | Autenticación JWT |
| Flask-CORS | 6.0.1 | Control de acceso CORS |
| Werkzeug | 3.1.3 | Hash de contraseñas |
| python-dotenv | 1.1.1 | Variables de entorno |
| requests | 2.x | Consultas HTTP al ESP32 |

### Frontend
| Librería | Versión | Uso |
|---|---|---|
| Expo SDK | ~54.0.0 | Plataforma de desarrollo |
| React Native | 0.81.5 | Framework móvil |
| expo-camera | ~17.0.10 | Escáner QR para lecturas |
| expo-location | ~19.0.8 | GPS para incidencias |
| expo-web-browser | ~15.0.10 | Abrir planillas PDF |
| expo-image-picker | ~17.0.10 | Fotos de evidencia |
| @react-native-async-storage | 2.2.0 | Almacenamiento local JWT |

### IoT
| Componente | Versión | Uso |
|---|---|---|
| Arduino IDE | 2.3.8 | Entorno de desarrollo |
| esp32 by Espressif | 3.3.7 | Soporte ESP32-S3 |
| ArduinoJson | 6.x/7.x | Serialización JSON |
| WiFi.h | Incluida | Conexión WiFi |
| WebServer.h | Incluida | Servidor HTTP embebido |
| HTTPClient.h | Incluida | POST de datos a Flask |

---

## 📡 Módulo IoT — ESP32-S3 + YF-S201

### Conexiones eléctricas

```
YF-S201 🔴 Rojo     → VIN  (5V)
YF-S201 ⚫ Negro    → GND
YF-S201 🟡 Amarillo → GPIO4
```

### Configuración del microcontrolador

```cpp
const char* WIFI_SSID        = "TU_WIFI";
const char* WIFI_PASSWORD    = "TU_PASSWORD";
const char* FLASK_URL        = "http://TU_IP:5000/api/iot/lectura";
const int   MEDIDOR_ID       = 3;
const float PULSOS_POR_LITRO = 7.5;   // Calibración YF-S201
// Intervalo de envío: cada 5 minutos (300,000 ms)
```

### Endpoints del ESP32 (servidor web embebido)

| Método | URL | Descripción |
|---|---|---|
| `GET` | `http://ESP32_IP/` | Panel HTML en tiempo real |
| `GET` | `http://ESP32_IP/datos` | JSON con telemetría completa |
| `POST` | `http://ESP32_IP/reset` | Reiniciar contadores |

### Endpoints IoT en el backend

| Método | Endpoint | Auth | Descripción |
|---|---|---|---|
| `POST` | `/api/iot/lectura` | Sin auth | Recibe datos del ESP32 |
| `GET` | `/api/iot/estadisticas/{id}` | JWT opcional | Historial por medidor |
| `GET` | `/api/iot/tiempo-real/{id}` | Sin auth | Proxy al ESP32 |
| `GET` | `/api/iot/mi-medidor` | JWT requerido | Medidor del socio logueado |

### Fórmulas de cálculo

```
Litros/s    = pulsos / 7.5
Caudal L/min = litros_s × 60
Caudal m³/h  = caudal_lpm × 0.001 × 60
Volumen m³   = litros / 1000
```

---

## 🌐 Dashboard Web

Acceso: `http://127.0.0.1:5000/dashboard/login`

| Sección | Descripción |
|---|---|
| Resumen | KPIs generales del sistema |
| Usuarios | CRUD completo con modal |
| Lecturas | Historial con filtros |
| Planillas | Cobros y pagos |
| **Monitor IoT** | ESP32 tiempo real + Chart.js |
| Recaudación | Movimientos de caja |
| Tarifas | Configuración por socio |
| Sesiones | Control de acceso JWT |
| Órdenes | Órdenes de trabajo |
| Incidencias | Reportes con mapa |

---

## 🔗 Endpoints principales de la API

```
POST   /api/auth/login                  Iniciar sesión
POST   /api/auth/refresh                Renovar token
GET    /api/auth/me                     Perfil actual
GET    /api/usuarios                    Listar usuarios
GET    /api/mi-vivienda                 Datos del socio
GET    /api/lecturas                    Listar lecturas
POST   /api/lecturas                    Registrar lectura
GET    /api/planillas                   Listar planillas
GET    /api/planillas/{id}/descargar    Descargar PDF
GET    /api/incidencias                 Listar incidencias
POST   /api/incidencias                 Crear incidencia
GET    /api/ordenes                     Mis órdenes de trabajo
POST   /api/ordenes/{id}/finalizar      Finalizar orden
GET    /api/notificaciones              Mis notificaciones
POST   /api/iot/lectura                 Recibir datos ESP32
GET    /api/iot/mi-medidor              Mi medidor IoT
GET    /api/health                      Estado del servidor
```

---

## 🗄️ Base de Datos

SQLite con **33 entidades** gestionadas por SQLAlchemy:

| Dominio | Tablas |
|---|---|
| Administración | usuarios, roles, sesiones, auditoria |
| Agua y territorio | socios, viviendas, medidores, sectores |
| Facturación | lecturas, planillas, pagos, tarifas_asignadas |
| Comunicación | avisos, incidencias, notificaciones, mensajes |
| Operación | ordenes_trabajo, reuniones, recordatorios |

---

## 👨‍💻 Autor

<div align="center">

**Edilson Francisco Guillín Carrión**

[![GitHub](https://img.shields.io/badge/GitHub-Edi--fran-181717?style=for-the-badge&logo=github)](https://github.com/Edi-fran)

*Tecnólogo en Desarrollo de Software*
*Universidad Estatal Amazónica — UEA*
*Puyo, Pastaza, Ecuador*

</div>

---

## 👥 Equipo del Proyecto

| Nombre | Rol |
|---|---|
| Edilson Francisco Guillín Carrión | Backend · IoT · App Móvil |
| David Paul Guerra Delgado | Frontend · Diseño UI |
| Luis Eduardo Argudo Guzmán | Testing · Documentación |

**Docente:** Ing. Julio César Hurtado Jerves
**Asignatura:** 2526 - Aplicaciones Móviles (B) — UEA-L-UFPTI-008-B
**Período:** 2025 – 2026 · Universidad Estatal Amazónica

---

## 📄 Licencia

Proyecto académico desarrollado para la Universidad Estatal Amazónica.

---

<div align="center">
💧 Desarrollado con ❤️ para las juntas comunitarias de agua potable
</div>