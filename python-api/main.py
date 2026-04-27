"""
API de CobrApp - Procesamiento de pagos Yape/Plin con OCR
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import easyocr
import cv2
import numpy as np
import re
from datetime import datetime

app = FastAPI(
    title="CobrApp API",
    description="API que procesa capturas de pagos Yape/Plin con OCR",
    version="1.0.0"
)

# Cargar el modelo UNA SOLA VEZ al arrancar
print("Cargando modelo easyocr...")
reader = easyocr.Reader(['es'], gpu=False)
print("Modelo listo ✓")

# Almacenamiento en memoria de los pagos del día
pagos_del_dia = []

# Palabras que indican zona de publicidad (todo lo que esté debajo se ignora)
PALABRAS_PUBLICIDAD = [
    'más en yape', 'mas en yape', 'conoce más', 'conoce mas',
    'aplican tyc', 'aplican t y c', 'cuarto de libra', 'papa regular',
    'yapea en el', 'p.o.s.', 'pos.', 'nuevo', 'sólo', 'solo',
    'yapea con', 'gana', 'sorteo', 'promoción', 'promocion'
]

# Patrón flexible para "S/" mal leído por OCR
PATRON_S_FLEXIBLE = r'[Ss8B]\s*[/Il1|]'

# Patrón de hora multi-formato
HORA_PATRON = r'(\d{1,2}[:\.]\d{2}\s*[ap]\s*\.?\s*m\s*\.?)'


def extraer_datos_de_imagen(img):
    """
    Recibe una imagen (array de numpy) y devuelve los datos del pago.
    Soporta capturas de Yape y Plin, incluso con publicidad.
    """
    alto_imagen = img.shape[0]
    resultados = reader.readtext(img, detail=1, paragraph=False)

    # ======================================================
    # DETECTAR ZONA DE PUBLICIDAD (para excluirla)
    # ======================================================
    y_inicio_publicidad = alto_imagen
    for bbox, texto, confianza in resultados:
        texto_lower = texto.lower().strip()
        for palabra in PALABRAS_PUBLICIDAD:
            if palabra in texto_lower:
                y_top = bbox[0][1]
                if y_top < y_inicio_publicidad:
                    y_inicio_publicidad = y_top
                break

    # Filtrar resultados: solo los que están ARRIBA de la publicidad
    resultados_validos = []
    for bbox, texto, confianza in resultados:
        y_top = bbox[0][1]
        if y_top < y_inicio_publicidad:
            resultados_validos.append((bbox, texto, confianza))

    texto_valido = "\n".join([t for _, t, _ in resultados_validos])
    texto_lower = texto_valido.lower()

    # ======================================================
    # TIPO
    # ======================================================
    es_plin = (
        'pago realizado' in texto_lower
        or ('plin' in texto_lower and 'yapeaste' not in texto_lower and 'yapearon' not in texto_lower)
    )
    es_yape = (
        'yapeaste' in texto_lower or 'yapearon' in texto_lower
    )

    if es_plin:
        tipo = 'Plin'
    elif es_yape:
        tipo = 'Yape'
    elif 'plin' in texto_lower:
        tipo = 'Plin'
    elif 'yape' in texto_lower:
        tipo = 'Yape'
    else:
        tipo = 'Desconocido'

    # ======================================================
    # HORA (detectar primero para no confundirla con monto)
    # ======================================================
    hora_match = re.search(HORA_PATRON, texto_valido, re.IGNORECASE)
    hora = hora_match.group(1).strip() if hora_match else None

    # Limpiar hora del texto antes de buscar monto
    texto_sin_hora = texto_valido
    if hora:
        texto_sin_hora = re.sub(HORA_PATRON, '', texto_valido, flags=re.IGNORECASE)

    # ======================================================
    # Items en zona del monto (40% superior, sin publicidad, sin horas)
    # ======================================================
    limite_superior = alto_imagen * 0.40

    items_zona_monto = []
    for bbox, texto, confianza in resultados_validos:
        y_top = bbox[0][1]
        if y_top > limite_superior:
            continue
        if re.search(HORA_PATRON, texto, re.IGNORECASE):
            continue
        if re.match(r'^\d{1,2}:\d{2}$', texto.strip()):
            continue
        items_zona_monto.append((bbox, texto, confianza))

    # ======================================================
    # MONTO
    # ======================================================
    monto = None

    # Intento 1: item completo "S/XX" (con cualquier variación de S/)
    for bbox, texto, confianza in items_zona_monto:
        match = re.match(
            rf'^{PATRON_S_FLEXIBLE}\s*\.?\s*(\d+(?:[.,]\d{{1,2}})?)\s*$',
            texto.strip()
        )
        if match:
            valor = float(match.group(1).replace(',', '.'))
            # Descartar montos sospechosamente bajos (típicos de publicidad)
            if valor >= 1.0:
                monto = match.group(1).replace(',', '.')
                break

    # Intento 2: regex en texto de zona superior
    if not monto:
        texto_zona = "\n".join([t for _, t, _ in items_zona_monto])
        match = re.search(
            rf'{PATRON_S_FLEXIBLE}\s*\.?\s*(\d+(?:[.,]\d{{1,2}})?)',
            texto_zona
        )
        if match:
            monto = match.group(1).replace(',', '.')

    # Intento 3: "S/" suelto y siguiente número
    if not monto:
        items = [r[1] for r in items_zona_monto]
        patrones_s_solo = [
            r'^[Ss]\s*[/Il1|]\s*$',
            r'^[Ss]/?$',
            r'^[8Bb]\s*[/Il1|]\s*$',
        ]
        for i, item in enumerate(items):
            if any(re.match(p, item.strip()) for p in patrones_s_solo):
                if i + 1 < len(items):
                    match_num = re.search(r'(\d+(?:[.,]\d{1,2})?)', items[i + 1])
                    if match_num:
                        monto = match_num.group(1).replace(',', '.')
                        break

    # Intento 4 (fallback): número con pinta de monto en zona superior
    if not monto:
        for bbox, texto, confianza in items_zona_monto[:6]:
            texto_limpio = texto.strip()
            if ':' in texto_limpio:
                continue
            match_num = re.match(r'^(\d{1,5}(?:[.,]\d{1,2})?)$', texto_limpio)
            if match_num and confianza > 0.5:
                monto = match_num.group(1).replace(',', '.')
                break

    # ======================================================
    # NÚMERO DE OPERACIÓN
    # ======================================================
    op = re.search(
        r'(?:operaci[oó]n|c[oó]d\.?\s*operaci[oó]n)[:\s]*(\d+)',
        texto_valido,
        re.IGNORECASE
    )
    if not op:
        op = re.search(r'\b(\d{7,10})\b', texto_valido)
    numero_operacion = op.group(1) if op else None

    # ======================================================
    # FECHA (múltiples formatos)
    # ======================================================
    fecha = None

    # Formato 1: "23 abr. 2026" (Yape con año)
    fecha_match = re.search(r'(\d{1,2}\s+\w+\.?\s+\d{4})', texto_valido)
    if fecha_match:
        fecha = fecha_match.group(1)

    # Formato 2: "21 Abr" (Plin sin año)
    if not fecha:
        fecha_match = re.search(
            r'(\d{1,2}\s+(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\.?)',
            texto_valido,
            re.IGNORECASE
        )
        if fecha_match:
            fecha = fecha_match.group(1)

    # Formato 3: "23/04/2026" (con barras)
    if not fecha:
        fecha_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', texto_valido)
        if fecha_match:
            fecha = fecha_match.group(1)

    # Formato 4: "23-04-2026" (con guiones)
    if not fecha:
        fecha_match = re.search(r'(\d{1,2}-\d{1,2}-\d{2,4})', texto_valido)
        if fecha_match:
            fecha = fecha_match.group(1)

    # ======================================================
    # NOMBRE
    # ======================================================
    nombre = None

    # Estrategia 1: item con asterisco (Yape)
    for bbox, texto, confianza in resultados_validos:
        if '*' in texto and any(c.isalpha() for c in texto):
            if re.search(r'[A-Za-záéíóúñÑ]{2,}', texto):
                nombre = texto.strip()
                break

    # Estrategia 2: nombre después del saludo (Plin)
    if not nombre:
        items = [r[1] for r in resultados_validos]
        for i, item in enumerate(items):
            if re.search(r'pago\s*realizado|yapeaste|yapearon', item, re.IGNORECASE):
                for j in range(i + 1, min(i + 5, len(items))):
                    candidato = items[j].strip()
                    if re.match(r'^[Ss]', candidato) or re.match(r'^\d', candidato):
                        continue
                    palabras = candidato.split()
                    if len(palabras) >= 2 and all(any(c.isalpha() for c in p) for p in palabras[:2]):
                        nombre = candidato
                        break
                if nombre:
                    break

    # ======================================================
    # ARMAR RESPUESTA
    # ======================================================
    es_valido = (
        monto is not None
        and numero_operacion is not None
        and tipo in ('Yape', 'Plin')
    )

    mensaje_error = None
    if not es_valido:
        if tipo == 'Desconocido':
            mensaje_error = "La imagen no corresponde a un pago Yape o Plin"
        elif monto is None:
            mensaje_error = "No se pudo extraer el monto"
        elif numero_operacion is None:
            mensaje_error = "No se pudo extraer el número de operación"
        else:
            mensaje_error = "Datos incompletos"

    return {
        "valido": es_valido,
        "tipo": tipo,
        "monto": float(monto) if monto else None,
        "nombre": nombre,
        "numero_operacion": numero_operacion,
        "fecha": fecha,
        "hora": hora,
        "mensaje_error": mensaje_error
    }


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/health")
async def health():
    """Verifica que la API está viva (n8n lo usa para verificar)."""
    return {"status": "ok", "servicio": "CobrApp API"}


@app.post("/procesar-imagen")
async def procesar_imagen(file: UploadFile = File(...)):
    """
    Procesa una captura de pago Yape/Plin y devuelve los datos extraídos.
    Acepta cualquier formato de imagen soportado por OpenCV:
    PNG, JPEG, JPG, BMP, WebP, TIFF, etc.
    """
    # Validar content_type SOLO si viene presente.
    # n8n manda imágenes como binario puro sin content_type, así que
    # solo rechazamos si HAY content_type y NO es de tipo imagen.
    # La validación final del contenido la hace cv2.imdecode más abajo.
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="El archivo debe ser una imagen"
        )

    contenido = await file.read()
    nparr = np.frombuffer(contenido, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Si OpenCV no pudo decodificar el archivo, no es una imagen válida
    if img is None:
        raise HTTPException(
            status_code=400,
            detail="No se pudo decodificar la imagen. Formatos soportados: PNG, JPEG, JPG, BMP, WebP, TIFF."
        )

    datos = extraer_datos_de_imagen(img)

    if datos["valido"]:
        datos_guardados = {
            **datos,
            "registrado_en": datetime.now().isoformat()
        }
        pagos_del_dia.append(datos_guardados)

    return JSONResponse(content=datos)


@app.get("/pagos")
async def listar_pagos():
    """Lista los pagos procesados del día (útil para debug)."""
    return {
        "total_pagos": len(pagos_del_dia),
        "pagos": pagos_del_dia
    }


@app.get("/reporte")
async def reporte_del_dia():
    """Devuelve el total recaudado del día."""
    total = sum(p["monto"] for p in pagos_del_dia if p.get("monto"))
    return {
        "fecha": datetime.now().strftime("%d/%m/%Y"),
        "total_pagos": len(pagos_del_dia),
        "total_recaudado": round(total, 2)
    }