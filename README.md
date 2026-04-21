<div align="center">

# 🤖 CobrApp

### Sistema Automatizado de Registro de Pagos Yape/Plin

*Automatización inteligente de cobros mediante OCR, Telegram y n8n*

![Status](https://img.shields.io/badge/status-en%20desarrollo-yellow)
![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![n8n](https://img.shields.io/badge/n8n-workflow-EA4B71?logo=n8n&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)

</div>

---

## 📋 Tabla de Contenidos

- [Descripción](#-descripción)
- [Problema que resuelve](#-problema-que-resuelve)
- [Solución propuesta](#-solución-propuesta)
- [Arquitectura](#-arquitectura)
- [Stack tecnológico](#️-stack-tecnológico)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Instalación](#-instalación)
- [Uso](#-uso)
- [Estado del proyecto](#-estado-del-proyecto)
- [Equipo](#-equipo)

---

## 📖 Descripción

**CobrApp** es un sistema de automatización que procesa capturas de pantalla de pagos realizados mediante **Yape** y **Plin** (las principales billeteras digitales del Perú), extrae automáticamente los datos del pago usando **OCR** (reconocimiento óptico de caracteres), y los registra en tiempo real en una hoja de cálculo.

Cuando un usuario envía una captura de pago al grupo de Telegram del negocio, el sistema:

1. 📥 Detecta la imagen automáticamente
2. 🔍 Extrae los datos del pago (nombre, monto, fecha, número de operación)
3. 📊 Los registra en Google Sheets
4. ✅ Envía una confirmación automática al grupo

---

## 🎯 Problema que resuelve

### 📌 Caso de estudio: Academia Fitness Lima

**Academia Fitness Lima** es un gimnasio con más de 200 socios activos que cobra mensualidades mediante Yape y Plin. El proceso actual es completamente manual:

| Problema | Impacto |
|----------|---------|
| ⏱️ Registro manual | 2-3 horas diarias del administrador |
| ❌ Errores humanos | Pagos duplicados, omitidos o mal registrados |
| 📂 Desorden | Capturas mezcladas con otros mensajes del grupo |
| 📊 Sin reportes en tiempo real | No se sabe cuánto se ha cobrado en el día |
| 😤 Mala experiencia | Socios son contactados por error pese a haber pagado |

---

## 💡 Solución propuesta

Un sistema **100% automatizado** que:

✅ Recibe capturas de pago desde un grupo de Telegram
✅ Procesa las imágenes con OCR para extraer datos
✅ Valida que sean pagos Yape o Plin reales
✅ Registra automáticamente en Google Sheets
✅ Envía confirmación inmediata al grupo
✅ Genera reportes diarios del total recaudado

---

## 🏗️ Arquitectura
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Telegram      │────>│     n8n      │────>│  Python + OCR   │
│   (Bot + Grupo) │     │ (Orquestador)│     │    (FastAPI)    │
└─────────────────┘     └──────┬───────┘     └─────────────────┘
│
▼
┌──────────────┐
│Google Sheets │
│  (Registro)  │
└──────────────┘

### Flujo de datos

1. **Usuario** envía captura Yape/Plin → Grupo de Telegram
2. **Telegram Bot** detecta la imagen → **n8n** (webhook)
3. **n8n** envía la imagen → **API Python** (OCR)
4. **API Python** extrae los datos → responde JSON estructurado
5. **n8n** valida datos → registra en **Google Sheets**
6. **n8n** envía confirmación → **Grupo de Telegram**

---

## 🛠️ Stack tecnológico

| Categoría | Tecnología | Propósito |
|-----------|-----------|-----------|
| 💬 **Mensajería** | Telegram Bot API | Recepción de capturas de pago |
| 🔄 **Orquestador** | n8n (self-hosted) | Coordinación del flujo completo |
| 🐍 **Backend API** | FastAPI + Python 3.11 | Procesamiento de imágenes |
| 👁️ **OCR** | easyocr | Extracción de texto de imágenes |
| 🖼️ **Procesamiento** | OpenCV + Pillow | Pre-procesamiento de imágenes |
| 📊 **Almacenamiento** | Google Sheets | Registro persistente de pagos |
| 🐳 **Contenedores** | Docker + Docker Compose | Despliegue y orquestación |
| 🔀 **Control de versiones** | Git + GitHub | Trabajo colaborativo |

---

## 📁 Estructura del proyecto
CobrApp/
│
├── 📁 python-api/              # API REST con FastAPI
│   ├── main.py                 # Endpoints y lógica OCR
│   ├── requirements.txt        # Dependencias Python
│   └── Dockerfile              # Imagen del contenedor API
│
├── 📁 n8n-flows/               # Flujos de n8n exportados
│   └── cobrapp-workflow.json   # Workflow principal
│
├── 📁 docs/                    # Documentación técnica
│   └── contrato-api.md         # Contrato de la API
│
├── 📁 capturas/                # Evidencias del sistema funcionando
├── 📁 pagos-prueba/            # Capturas de prueba Yape/Plin
│
├── 🐳 docker-compose.yml       # Orquestación de contenedores
├── 🔒 .gitignore               # Archivos ignorados por Git
└── 📖 README.md                # Este archivo

---

## 🚀 Instalación

### Requisitos previos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y corriendo
- [Git](https://git-scm.com/) para clonar el repositorio
- Cuenta de [Telegram](https://telegram.org/) con un bot creado vía [@BotFather](https://t.me/BotFather)
- Cuenta de [Google](https://accounts.google.com/) para acceder a Google Sheets

### Pasos de instalación

**1. Clonar el repositorio**

```bash
git clone https://github.com/Mayela3018/CobrApp.git
cd CobrApp
```

**2. Configurar variables de entorno**

Crear un archivo `.env` en la raíz del proyecto con el siguiente contenido:

```env
TELEGRAM_BOT_TOKEN=tu_token_del_bot
TELEGRAM_BOT_USERNAME=nombre_de_tu_bot
TELEGRAM_CHAT_ID=id_del_grupo
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin123
```

**3. Levantar los contenedores**

```bash
docker-compose up -d
```

Esto levanta dos servicios:

- **n8n** en `http://localhost:5678` (orquestador de flujos)
- **API Python** en `http://localhost:8000` (procesamiento OCR)

**4. Verificar que todo está funcionando**

```bash
# Verificar la API
curl http://localhost:8000/health

# Debería responder:
# {"status":"ok","servicio":"CobrApp API"}
```

**5. Configurar n8n**

Abrir `http://localhost:5678` en el navegador, iniciar sesión y:

- Crear una credencial de **Telegram API** con el token del bot
- Importar el flujo desde `n8n-flows/cobrapp-workflow.json`
- Activar el workflow

---

## 📸 Uso

### Flujo normal

1. El administrador agrega el bot al grupo de Telegram del negocio
2. Los socios envían sus capturas de pago (Yape o Plin) al grupo
3. El bot procesa la imagen automáticamente
4. El pago queda registrado en Google Sheets en segundos
5. El grupo recibe una confirmación: *"✅ Pago de S/. 50.00 de Juan Pérez registrado"*

### Endpoints disponibles de la API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/health` | Verifica que la API está viva |
| `POST` | `/procesar-imagen` | Procesa una captura y extrae los datos |
| `GET` | `/pagos` | Lista los pagos procesados del día |
| `GET` | `/reporte` | Retorna el total recaudado del día |

Ver el [contrato completo de la API](docs/contrato-api.md) para más detalles.

---

## 📊 Estado del proyecto

🟡 **En desarrollo activo**

### Progreso general

- [x] **Día 1** — Estructura del proyecto + Bot de Telegram configurado
- [x] **Día 2** — Docker Compose + n8n levantado + API Python integrada
- [ ] **Día 3-4** — Flujo n8n completo con procesamiento OCR
- [ ] **Día 5** — Integración con Google Sheets
- [ ] **Día 6-7** — Reporte diario automático
- [ ] **Día 8** — Pruebas end-to-end con capturas reales
- [ ] **Día 9** — Documentación y video demostrativo
- [ ] **Día 10** — Entrega final

---

## 👥 Equipo

| Integrante  |
|-----------|-----|-------------------|
| **Mayela Ticona** 
| **Milagros **
### Metodología de trabajo

Usamos **Git Feature Branch Workflow**:

- `main` — Rama principal (solo código revisado)
- `feature/api-python` — Desarrollo de la API + OCR (Mila)
- `feature/n8n-flow` — Configuración de flujos n8n (Maye)

Los cambios se integran mediante **Pull Requests** revisados en equipo.

---

## 📚 Contexto académico

Este proyecto es parte del curso **[Nombre del curso]** del ciclo **2026-I**,  en **[Tecsup]**.

---

<div align="center">

### 🇵🇪 Hecho con 💜 en Lima, Perú

*Proyecto académico - Uso educativo*

</div>