# 📱 CobrApp — Registro Automático de Pagos Yape/Plin

> Sistema automatizado que procesa capturas de pagos enviadas por Telegram, extrae los datos con OCR, los registra en Google Sheets y envía un reporte diario automático al grupo.

**Proyecto académico** · Equipo: Mayela Ticona + Milagros Ramos · 2026

---

## 📋 Tabla de Contenidos

- [¿Qué es CobrApp?](#-qué-es-cobrapp)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Stack Tecnológico](#-stack-tecnológico)
- [Estructura del Repositorio](#-estructura-del-repositorio)
- [Flujos de n8n](#-flujos-de-n8n)
- [Resultados de Pruebas](#-resultados-de-pruebas)
- [Dificultades y Soluciones](#-dificultades-y-soluciones)
- [Limitaciones Conocidas](#-limitaciones-conocidas)
- [Cómo Ejecutar el Proyecto](#-cómo-ejecutar-el-proyecto)
- [Equipo y Roles](#-equipo-y-roles)

---

## 🎯 ¿Qué es CobrApp?

**CobrApp** nació de una necesidad real: las academias y negocios pequeños reciben decenas de capturas de pago por Yape y Plin en grupos de WhatsApp o Telegram, y registrarlas manualmente consume tiempo y genera errores.

CobrApp automatiza ese proceso completo:

1. Un cliente envía su captura de pago al grupo de Telegram
2. El bot la detecta y la envía al motor de OCR
3. La API extrae nombre, monto, operación, fecha y hora
4. Los datos se registran automáticamente en Google Sheets
5. El bot confirma el pago en el grupo
6. Cada noche a las 23:55 se envía un reporte diario automático con el total recaudado

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                     GRUPO DE TELEGRAM                           │
│           "Academia Fitness Lima - Pagos"                       │
└──────────────────────┬──────────────────────────────────────────┘
                       │ captura de pago
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BOT @cobrapp_maye_mila_bot                     │
└──────────────────────┬──────────────────────────────────────────┘
                       │ webhook HTTPS
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ngrok (túnel HTTPS)                            │
│          embattled-mousy-donated.ngrok-free.dev                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  n8n (puerto 5678)                              │
│                                                                 │
│  Workflow 1: Registro de Pagos                                  │
│  [Telegram Trigger] → [IF foto?] → [Get file]                  │
│       → [HTTP Request] → [IF válido?]                          │
│       → [Google Sheets] → [Send mensaje]                       │
│                                                                 │
│  Workflow 2: Reporte Diario (23:55)                            │
│  [Schedule] → [Google Sheets Read] → [Code JS]                 │
│       → [Google Sheets Write] → [Send mensaje]                 │
└──────────┬───────────────────────────────────────────────────--┘
           │ POST /procesar-imagen
           ▼
┌─────────────────────────────────────────────────────────────────┐
│          API Python FastAPI (puerto 8000)                       │
│                                                                 │
│   easyocr → parser regex → validación → JSON response          │
│                                                                 │
│  {                                                              │
│    "valido": true,                                              │
│    "tipo": "Yape",                                              │
│    "monto": 45,                                                 │
│    "nombre": "Diana Rey*",                                      │
│    "numero_operacion": "21680629",                              │
│    "fecha": "23 abr. 2026",                                     │
│    "hora": "09:23 p.m."                                         │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│              Google Sheets (almacenamiento)                     │
│                                                                 │
│   Hoja 1: "Pagina 1" — registro de pagos individuales          │
│   Hoja 2: "ReportesDiarios" — resumen diario automático        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Stack Tecnológico

| Componente | Tecnología | Versión | Rol |
|---|---|---|---|
| Orquestador | [n8n](https://n8n.io) | 2.16.2 | Automatización de flujos |
| API OCR | Python + FastAPI | 3.11 / 0.115 | Procesamiento de imágenes |
| OCR Engine | easyocr | 1.7.x | Extracción de texto |
| Visión computacional | OpenCV | 4.x | Preprocesamiento de imagen |
| Bot mensajería | Telegram Bot API | v6 | Interfaz con el usuario |
| Almacenamiento | Google Sheets API | v4 | Base de datos en la nube |
| Contenerización | Docker + Compose | 26.x | Portabilidad y despliegue |
| Túnel HTTPS | ngrok | 3.38 | Exposición local a internet |

---

## 📁 Estructura del Repositorio

```
CobrApp/
├── python-api/
│   ├── main.py              # API FastAPI con OCR (Milagros)
│   ├── Dockerfile
│   └── requirements.txt
├── n8n-flows/
│   ├── CobrApp-Registro-de-Pagos.json     # Workflow principal
│   └── CobrApp-Reporte-Diario.json        # Workflow reporte
├── docs/
│   ├── seccion-tecnica-informe.md          # Sección técnica (Milagros)
│   └── arquitectura-diagrama.png
├── capturas/
│   └── dia7/                              # Evidencias de pruebas
├── docker-compose.yml
├── .env.example                           # Variables requeridas (sin secrets)
└── README.md
```

---

## 🔄 Flujos de n8n

### Workflow 1 — Registro de Pagos

Se activa cada vez que llega una imagen al grupo de Telegram.

```
[Telegram Trigger]
      │
      ▼
[IF: ¿Es foto?]
   Sí │          No │
      ▼               ▼
[Get a file]     [ignorar]
      │
      ▼
[HTTP Request → API Python]
      │
      ▼
[IF: ¿valido = true?]
   Sí │             No │
      ▼                  ▼
[Google Sheets]    [Mensaje de error al grupo]
[Append/Update]
      │
      ▼
[Send mensaje de confirmación]
```

**Ejemplo de mensaje de confirmación:**
```
✅ Pago registrado correctamente

👤 Nombre: Diana Rey*
💰 Monto: S/. 45.00
📋 Operación: 21680629
🕐 Hora: 09:23 p.m.
📅 Fecha: 23 abr. 2026
👨 Registrado por: Maye
```

### Workflow 2 — Reporte Diario Automático

Se ejecuta todos los días a las **23:55** sin intervención humana.

```
[Schedule Trigger — 23:55 daily]
      │
      ▼
[Google Sheets — Lee "Pagina 1"]
      │ (todos los pagos)
      ▼
[Code JavaScript]
  · Filtra pagos del día (zona horaria Lima UTC-5)
  · Calcula total recaudado
  · Cuenta Yape vs Plin
      │
      ▼
[Google Sheets — Escribe en "ReportesDiarios"]
      │
      ▼
[Send mensaje al grupo]
```

**Ejemplo de reporte automático:**
```
📊 REPORTE DIARIO COBRAPP
📅 29 abr. 2026

💰 Total recaudado: S/ 32.50
📋 Total de pagos: 3

📊 Por tipo:
   • Yape: 3 pagos → S/ 32.50
   • Plin: 0 pagos → S/ 0.00

¡Buen trabajo equipo! 💪
```

---

## 🧪 Resultados de Pruebas

Se realizaron pruebas con capturas reales del grupo durante los días de desarrollo:

| # | Captura | Tipo | Monto real | Monto extraído | Hora real | Hora extraída | Estado |
|---|---|---|---|---|---|---|---|
| 1 | Diana Rey* | Yape | S/45 | S/45 | 09:23 p.m. | 09.23 p.m. | ✅ OK |
| 2 | Culqi*sbfarma | Yape | S/6 | S/6 | 04:12 p.m. | 04:12 p.m. | ✅ OK |
| 3 | Alicia Fel* | Yape | S/1.50 | S/1.50 | 09:06 a.m. | 09:06 a.m. | ✅ OK |
| 4 | Yumi Cur* | Yape | S/7.50 | S/7.50 | 09:05 a.m. | 09.05 a.m. | ✅ OK |
| 5 | Shalom Empresarial | Yape | S/12 | S/12 | 01:25 p.m. | 01:25 p.m. | ✅ OK |
| 6 | Haide Santana Y | Plin | S/35 | S/35 | 08:13 a.m. | 08:13 a.m. | ✅ OK |
| 7 | Foto de persona (no pago) | — | — | — | — | — | ✅ Rechazada |
| 8 | Captura con barra de status | Yape | S/45 | S/8.2 | — | — | ⚠️ Limitación |

**Resultado general: 87.5% de casos procesados correctamente.**

---

## 🐛 Dificultades y Soluciones

Durante el desarrollo se enfrentaron y resolvieron varios problemas técnicos:

### 1. Cache de Docker — imagen vieja del OCR
El fix de OCR de Milagros no se aplicaba porque Docker usaba imagen cacheada.

**Solución:** `docker-compose build --no-cache` para forzar reconstrucción limpia.

### 2. Content-Type incorrecto — bug crítico de integración
n8n descargaba imágenes de Telegram con `Content-Type: application/octet-stream` en lugar de `image/jpeg`, lo cual hacía que la API rechazara todas las imágenes con error 400.

**Diagnóstico:** Revisión de logs con `docker logs cobrapp-api` + inspección del panel "Get a file" en n8n, donde se confirmó el mime type incorrecto.

**Solución:** Milagros cambió la validación de `or` a `and` en la línea 295 de `main.py`:
```python
# Antes (rechazaba todo sin Content-Type explícito):
if not file.content_type or not file.content_type.startswith("image/"):

# Después (acepta binarios sin Content-Type, como los de Telegram):
if file.content_type and not file.content_type.startswith("image/"):
```
Este caso es un ejemplo de **debugging colaborativo**: Mayela diagnosticó la causa raíz desde el lado n8n, Milagros implementó el fix en la API.

### 3. Token de Telegram revocado accidentalmente
Al intentar consultar el token desde @BotFather, se ejecutó `/token` en lugar de `/mybots`, lo que revocó el token activo.

**Solución:** Generación de nuevo token + actualización en `.env` + actualización de credencial en n8n + reinicio de Docker.

### 4. Webhook de Telegram rechazando publicación
El workflow no se podía publicar porque n8n no lograba registrar el webhook con la URL de ngrok.

**Solución:** Asegurar que Docker y ngrok estén corriendo antes de intentar publicar. El orden correcto es: ngrok → Docker → n8n → Publish.

### 5. Zona horaria UTC vs Lima
El reporte diario calculaba la fecha como UTC (5 horas adelantada), por lo que a las 22:40 hora Lima el código pensaba que era el día siguiente.

**Solución:** Fix en el nodo Code de n8n:
```javascript
// Antes: usaba UTC
const hoy = new Date();

// Después: fuerza zona horaria Lima
const hoyLima = new Date(
  new Date().toLocaleString('en-US', { timeZone: 'America/Lima' })
);
```

### 6. Reporte Diario leyendo hoja incorrecta
El nodo "Get rows" del Workflow 2 estaba apuntando a la hoja `ReportesDiarios` (vacía) en lugar de `Pagina 1` (con los pagos). Esto hacía que n8n no encontrara filas y detuviera el flujo.

**Solución:** Corregir la configuración del nodo para leer de `Pagina 1` y escribir el resumen en `ReportesDiarios`.

---

## ⚠️ Limitaciones Conocidas

### Fotos de pantalla vs. screenshots directos
La API está optimizada para procesar **screenshots directos** de la app Yape o Plin. Si un usuario envía una **foto tomada con otro celular** (donde se ve la barra de estado del sistema con la hora), el OCR puede confundir la hora del sistema con el monto del pago.

**Recomendación para usuarios:** Usar el botón "Compartir" dentro de la app Yape/Plin para generar un screenshot limpio, o hacer captura de pantalla directamente en el dispositivo.

### Disponibilidad del sistema
Al estar desplegado localmente con ngrok, el sistema solo opera cuando la PC anfitriona está encendida y Docker está corriendo. Para producción real, se recomienda migrar a un servidor con disponibilidad 24/7 (Railway, Render, AWS EC2, etc.).

### Capturas con publicidad de Yape
Las capturas que incluyen banners publicitarios debajo del monto pueden interferir con la detección. La API incluye un filtro de zona de publicidad, pero capturas con publicidad muy cercana al monto pueden fallar.

---

## 🚀 Cómo Ejecutar el Proyecto

### Prerrequisitos
- Docker Desktop instalado
- ngrok instalado y configurado con cuenta
- Cuenta de Google con acceso a Google Sheets
- Bot de Telegram creado en @BotFather

### Configuración

1. Clona el repositorio:
```bash
git clone https://github.com/Mayela3018/CobrApp.git
cd CobrApp
git checkout feature/n8n-flow
```

2. Crea el archivo `.env` a partir del ejemplo:
```bash
cp .env.example .env
# Edita .env con tus credenciales:
# TELEGRAM_BOT_TOKEN=tu_token_aquí
# TELEGRAM_CHAT_ID=id_del_grupo
# GOOGLE_SHEETS_ID=id_de_tu_sheet
```

3. Inicia ngrok en una terminal separada:
```bash
ngrok http 5678
# Copia la URL HTTPS que aparece (ej: https://xxxx.ngrok-free.dev)
# Actualiza WEBHOOK_URL y N8N_EDITOR_BASE_URL en docker-compose.yml
```

4. Levanta los servicios:
```bash
docker-compose up -d
docker ps  # Verifica que ambos contenedores estén Up
```

5. Configura n8n:
   - Accede a `http://localhost:5678`
   - Importa los flujos desde `n8n-flows/`
   - Configura las credenciales de Telegram y Google Sheets
   - Publica ambos workflows

---

## 👥 Equipo y Roles

| Integrante | Rol | Responsabilidades |
|---|---|---|
| **Mayela Ticona** | Frontend & Integración | Bot de Telegram, flujos n8n, Google Sheets, testing de integración, debugging end-to-end |
| **Milagros Ramos** | Backend & OCR | API Python con FastAPI, motor OCR con easyocr, Docker, parser de capturas Yape/Plin |

**Rama de Mayela:** `feature/n8n-flow`  
**Rama de Milagros:** `feature/api-python` (mergeada en `feature/n8n-flow`)

---

## 📄 Licencia

Proyecto académico — TECSUP 2026. Todos los derechos reservados.