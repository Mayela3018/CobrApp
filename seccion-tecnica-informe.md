# Sección Técnica del Informe — CobrApp

> Documento que recopila las decisiones técnicas, implementaciones y dificultades encontradas durante el desarrollo de la API Python con OCR para CobrApp. Este borrador está pensado para ser integrado en el informe principal por MAY.

---

## 6.2 Desarrollo de la API Python con FastAPI

### Justificación de la tecnología

Para el backend del sistema se eligió **FastAPI** como framework web por las siguientes razones técnicas:

- **Alto rendimiento:** FastAPI es uno de los frameworks Python más rápidos disponibles, basado en Starlette y Pydantic.
- **Documentación automática:** genera una interfaz Swagger UI nativa en `/docs`, lo cual facilitó las pruebas durante el desarrollo sin necesidad de herramientas externas como Postman.
- **Validación automática de datos:** mediante type hints de Python, FastAPI valida los datos de entrada y los serializa automáticamente.
- **Soporte nativo para `multipart/form-data`:** esencial para recibir archivos de imagen desde n8n.
- **Asíncrono por defecto:** soporta llamadas concurrentes sin bloqueos.

### Endpoints implementados

La API expone 4 endpoints REST:

| Endpoint | Método | Función |
|---|---|---|
| `/health` | GET | Verifica que el servicio esté activo |
| `/procesar-imagen` | POST | Procesa una imagen y devuelve los datos del pago |
| `/pagos` | GET | Lista los pagos procesados del día |
| `/reporte` | GET | Devuelve el total recaudado del día |

### Estructura de la respuesta JSON

La API devuelve siempre un JSON estructurado con los siguientes campos:

```json
{
  "valido": true,
  "tipo": "Yape",
  "monto": 50.00,
  "nombre": "Diana Rey*",
  "numero_operacion": "21680629",
  "fecha": "23 abr. 2026",
  "hora": "09.23 p. m.",
  "mensaje_error": null
}
```

El campo `valido` es `true` solo cuando se pudieron extraer correctamente el `tipo`, `monto` y `numero_operacion`. Si falta alguno, la API devuelve `valido: false` con un `mensaje_error` descriptivo.

---

## 6.3 Implementación del OCR con easyocr

### Decisión técnica: pytesseract vs easyocr

Inicialmente se planificó usar **pytesseract** por su velocidad. Sin embargo, durante las pruebas con capturas reales de Yape se identificaron problemas críticos:

- El monto era leído incorrectamente (ej: "S/ 80" se leía como "S/B0")
- Las fuentes estilizadas de Yape confundían al motor OCR
- Los montos con decimales no se extraían de forma confiable

Se tomó la decisión técnica de **migrar a easyocr**, que utiliza deep learning (basado en PyTorch) para reconocimiento de texto. Las ventajas observadas fueron:

| Criterio | pytesseract | easyocr |
|---|---|---|
| Precisión con fuentes estilizadas | Baja | Alta |
| Detección de decimales | Inconsistente | Confiable |
| Soporte de español | Sí | Sí |
| Velocidad | Muy rápido | Más lento (compensable con pre-carga del modelo) |
| Tamaño de la dependencia | Pequeño | Grande (incluye PyTorch) |

### Preprocesamiento de imágenes

Para optimizar la lectura se utiliza **OpenCV** en:

- Carga y decodificación de la imagen recibida (`cv2.imdecode`)
- Conversión a array NumPy compatible con easyocr
- Validación de que el archivo sea una imagen real (si OpenCV no puede decodificar, devuelve error 400)

### Parser con estrategias escalonadas

El parsing de los datos extraídos se realiza con **expresiones regulares (regex)** organizadas en estrategias escalonadas. Para cada campo crítico se implementaron múltiples intentos de extracción.

**Ejemplo: extracción del monto**

1. **Intento 1:** buscar patrón `S/XX` o `S/ XX` con o sin decimales
2. **Intento 2:** buscar un item del OCR que sea exactamente un monto
3. **Intento 3:** tolerar lecturas mal hechas del OCR (ej: "SI" en vez de "S/", "Sl" en vez de "S/")
4. **Intento 4 (fallback):** buscar un número con formato de monto en los primeros items detectados

Este enfoque hace que el parser sea **robusto** ante variaciones en cómo easyocr interpreta las imágenes.

### Soporte dual: Yape y Plin

El parser detecta ambas billeteras peruanas con sus particularidades:

| Característica | Yape | Plin |
|---|---|---|
| Frase clave | "¡Yapeaste!" / "¡Te Yapearon!" | "¡Pago realizado!" |
| Formato del nombre (persona) | Con asterisco (ej: "Diana Rey*") | Sin asterisco (ej: "Haide Santana Y") |
| Formato del nombre (empresa) | Sin asterisco (ej: "Shalom Empresarial") | Sin asterisco |
| Formato de fecha | Con año (ej: "20 dic. 2025") | Sin año (ej: "21 Abr") |
| Campo de operación | "Nro. de operación" | "Cód. operación" |

### Privacidad

El **código de seguridad** de las capturas (3 dígitos antifraude que cambian cada día) **NO se procesa ni se guarda**, por consideraciones de privacidad y porque es un dato irrelevante para el sistema de registro de pagos.

---

## 6.5 Containerización con Docker

### Justificación

Se decidió usar Docker por tres razones principales:

1. **Reproducibilidad:** el sistema funciona igual en cualquier laptop, eliminando el problema de "en mi máquina funciona".
2. **Aislamiento de dependencias:** Tesseract/easyocr, n8n y Python no interfieren entre sí.
3. **Despliegue simple:** un solo comando (`docker-compose up`) levanta todo el sistema.

### Estructura del Dockerfile de la API

El Dockerfile de la API Python realiza los siguientes pasos:

1. Parte de `python:3.11-slim` como imagen base (ligera).
2. Instala dependencias del sistema necesarias para OpenCV (`libgl1`, `libglib2.0-0`, etc.).
3. Instala las librerías Python desde `requirements.txt`.
4. **Pre-descarga el modelo de easyocr** al momento de construir la imagen. Esta optimización evita que la primera petición tarde 60+ segundos (el modelo pesa ~64 MB).
5. Copia el código y expone el puerto 8000.
6. Inicia el servidor Uvicorn.

### docker-compose.yml

El archivo orquesta dos servicios:

- **`python-api`**: construido desde nuestro Dockerfile, expone el puerto 8000.
- **`n8n`**: usa la imagen oficial `n8nio/n8n`, expone el puerto 5678.

Ambos servicios están en la misma red Docker interna, lo que permite que n8n llame a la API usando el hostname `python-api` (por ejemplo: `http://python-api:8000/procesar-imagen`).

---

## 8. Dificultades encontradas y soluciones

### Dificultad 1: OCR impreciso con pytesseract

**Problema:** pytesseract confundía caracteres en los montos de Yape (leyendo "80" como "B0", "5" como "S").

**Solución:** migración a easyocr, más robusto con fuentes estilizadas. Trade-off aceptable: easyocr tarda ~30 segundos en cargar el modelo la primera vez, pero se compensó pre-cargándolo en el Dockerfile.

### Dificultad 2: Captura de Plin con formato distinto

**Problema:** el parser inicialmente solo soportaba Yape. La primera prueba con Plin falló en 3 campos (tipo, nombre, fecha).

**Solución:** generalización del parser para detectar ambas billeteras:

- Detección de Plin por frase "pago realizado" (no solo por la palabra "plin")
- Estrategia alternativa para nombres sin asterisco
- Regex flexible para fechas con o sin año

### Dificultad 3: Capturas con publicidad de Yape

**Problema:** algunas capturas de Yape incluyen publicidad al final ("Cuarto de Libra S/ 1.90 - Yapea en el P.O.S."). El parser confundía el precio de la promoción con el monto real del pago.

**Solución:** implementación de detección de **zona de publicidad**:

1. Se identifican palabras clave de publicidad ("Más en Yape", "Cuarto de Libra", "Aplican TyC", etc.).
2. Se calcula la posición Y de la primera palabra de publicidad detectada.
3. Todos los textos por debajo de esa posición Y se ignoran.

Esto hace al parser robusto ante capturas reales con anuncios sin perder los datos del pago.

### Dificultad 4: Bug del `content_type` con n8n (debugging colaborativo)

**Problema:** la API funcionaba al subir imágenes desde Swagger UI, pero **fallaba al recibir imágenes desde n8n** con error 400 "El archivo debe ser una imagen", aunque la imagen era válida.

**Investigación colaborativa:**

- Se revisaron los logs del contenedor: `POST /procesar-imagen 400 Bad Request`
- Se identificó que n8n descarga las imágenes de Telegram como **binario puro sin `content_type`**
- La validación original `if not file.content_type or not file.content_type.startswith("image/")` rechazaba archivos sin `content_type`, aunque sí fueran imágenes

**Solución:** se cambió la lógica de validación de `or` a `and`:

```python
# Antes (incorrecto):
if not file.content_type or not file.content_type.startswith("image/"):
    raise HTTPException(...)

# Después (correcto):
if file.content_type and not file.content_type.startswith("image/"):
    raise HTTPException(...)
```

La nueva lógica **solo rechaza** si HAY un `content_type` y NO es de tipo imagen. Si viene vacío (caso n8n), deja pasar y la validación final la hace `cv2.imdecode`. Esto no compromete la seguridad porque OpenCV rechaza archivos que no sean imágenes reales.

### Dificultad 5: Variaciones en el formato de hora

**Problema:** el OCR leía las horas en distintos formatos según la captura:

- "01:25 p. m." (con dos puntos y espacios)
- "04:12 p.m." (sin espacios)
- "09:06 a. m." (con espacios variables)
- "09.23 p.m." (con punto en lugar de dos puntos)

**Solución:** regex altamente tolerante:

```python
HORA_PATRON = r'(\d{1,2}[:\.]\d{2}\s*[ap][\s\.\,]*m[\s\.\,]*)'
```

Este patrón acepta cualquier combinación de espacios, puntos y comas entre `a/p` y `m`.

### Dificultad 6: Nombres de empresas sin asterisco

**Problema:** el sistema asumía que todos los nombres tenían asterisco (ej: "Diana Rey*"). Pero los pagos a empresas en Yape muestran el nombre completo sin asterisco (ej: "Shalom Empresarial").

**Solución:** se agregó una **Estrategia 3** al parser de nombres:

```python
# Si no hay asterisco, buscar el nombre debajo del monto
# (en Yape, el nombre siempre va inmediatamente después del S/XX)
if not nombre:
    for i, item in enumerate(items):
        if re.match(rf'^{PATRON_S_FLEXIBLE}\s*\.?\s*\d+', item.strip()):
            if i + 1 < len(items):
                candidato = items[i + 1].strip()
                # Validar: no empieza con número, no contiene año, tiene letras
                if (len(candidato) > 3
                    and not re.match(r'^\d', candidato)
                    and not re.search(r'\d{4}', candidato)
                    and re.search(r'[A-Za-záéíóúñÑ]{2,}', candidato)):
                    nombre = candidato
                    break
```

---

## 9. Limitaciones conocidas

### 9.1 Capturas tipo "foto del celular"

El sistema procesa correctamente **screenshots directos** de Yape/Plin, pero presenta limitaciones cuando el usuario envía una **foto de la pantalla del celular** tomada con otro dispositivo. En estos casos:

- Aparece la **barra de estado del sistema** en la parte superior (con la hora del celular, batería, etc.)
- El OCR puede confundir la hora del sistema con el monto del pago
- La calidad de la imagen suele ser inferior

**Recomendación al usuario:** enviar siempre el screenshot directo desde Yape (botón "Compartir") en lugar de fotos de la pantalla.

### 9.2 Formatos de imagen

La API acepta cualquier formato soportado por OpenCV (PNG, JPEG, JPG, BMP, WebP, TIFF), pero **NO soporta**:

- HEIC/HEIF (formato nativo de iPhone): los usuarios de iPhone deberían convertir a JPEG antes de enviar
- SVG: formato vectorial no aplicable a capturas de pantalla
- PDF: no es formato de imagen

En la práctica, esto no es un problema porque **Telegram convierte automáticamente** todas las imágenes a JPEG.

---

## Anexo: Pruebas realizadas

Se realizaron pruebas con capturas reales de pagos durante el desarrollo:

| # | Tipo | Caso | Resultado |
|---|---|---|---|
| 1 | Yape enviado | S/ 50.00 (caso base) | ✅ OK |
| 2 | Yape enviado | S/ 20.50 (decimal) | ✅ OK |
| 3 | Yape recibido | S/ 21.97 ("Te Yapearon") | ✅ OK |
| 4 | Yape enviado | S/ 1.50 (decimal pequeño) | ✅ OK |
| 5 | Yape enviado | S/ 5.00 (procesado vía n8n) | ✅ OK |
| 6 | Plin enviado | S/ 35.00 (formato distinto) | ✅ OK |
| 7 | Yape con publicidad | S/ 45 (Diana Rey, Cuarto de Libra abajo) | ✅ OK |
| 8 | Yape empresa | Shalom Empresarial (sin asterisco) | ✅ OK |
| 9 | Yape hora variable | "04:12 p.m." (sin espacios) | ✅ OK |
| 10 | Yape hora variable | "09:06 a. m." (espacios extra) | ✅ OK |

**Cobertura final:** 10/10 casos correctamente procesados después de las iteraciones del parser.

---

## Tecnologías utilizadas (resumen)

| Componente | Tecnología | Versión | Licencia |
|---|---|---|---|
| Framework web | FastAPI | 0.111.0 | MIT |
| Servidor ASGI | Uvicorn | 0.29.0 | BSD |
| OCR | easyocr | 1.7.1 | Apache 2.0 |
| Procesamiento de imagen | OpenCV | 4.9.0 | Apache 2.0 |
| Manipulación numérica | NumPy | 1.26.4 | BSD |
| Manejo de imágenes | Pillow | 10.3.0 | HPND |
| Soporte multipart | python-multipart | 0.0.9 | Apache 2.0 |
| Containerización | Docker | 24.x | Apache 2.0 |
| Orquestación | Docker Compose | 2.x | Apache 2.0 |

**Costo total de licencias:** S/ 0.00 (todo open source)