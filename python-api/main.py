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

# Cargar el modelo UNA SOLA VEZ al arrancar (no en cada petición)
print("Cargando modelo easyocr...")
reader = easyocr.Reader(['es'], gpu=False)
print("Modelo listo ✓")

# Almacenamiento en memoria de los pagos del día (para el endpoint GET /pagos)
pagos_del_dia = []


def extraer_datos_de_imagen(img):
    """
    Recibe una imagen (array de numpy) y devuelve los datos del pago.
    Soporta capturas de Yape y Plin.
    """
    resultados = reader.readtext(img, detail=1, paragraph=False)

    # Construir texto completo para las regex
    texto_completo = ""
    for bbox, texto, confianza in resultados:
        texto_completo += texto + "\n"

    texto_lower = texto_completo.lower()

    # === TIPO ===
    es_plin = (
        'pago realizado' in texto_lower
        or ('plin' in texto_lower and 'yapeaste' not in texto_lower and 'yapearon' not in texto_lower)
    )
    es_yape = (
        'yapeaste' in texto_lower
        or 'yapearon' in texto_lower
    )

    if es_plin:
        tipo = 'Plin'
    elif es_yape:
        tipo = 'Yape'
    else:
        if 'plin' in texto_lower:
            tipo = 'Plin'
        elif 'yape' in texto_lower:
            tipo = 'Yape'
        else:
            tipo = 'Desconocido'

    # === HORA (PRIMERO para no confundirla con monto después) ===
    # Acepta múltiples formatos:
    #   "10:41 a. m"      "09:06 a.m."     (con dos puntos)
    #   "03.48 p. m"      "08.05 p.m."     (con punto)
    hora_match = re.search(
        r'(\d{1,2}[:\.]\d{2}\s*[ap]\.?\s*m\.?)',
        texto_completo,
        re.IGNORECASE
    )
    hora = hora_match.group(1) if hora_match else None

    # Limpiar texto e items removiendo la hora antes de buscar el monto
    # Esto evita que el parser confunda la hora con el monto cuando este es entero
    texto_sin_hora = texto_completo
    if hora:
        texto_sin_hora = re.sub(
            r'\d{1,2}[:\.]\d{2}\s*[ap]\.?\s*m\.?',
            '',
            texto_completo,
            flags=re.IGNORECASE
        )

    # Crear lista de items "limpios" (sin horas) para búsqueda del monto
    items_sin_hora = []
    for bbox, texto, confianza in resultados:
        # Excluir items que parezcan ser una hora completa (con a.m./p.m.)
        if re.search(r'\d{1,2}[:\.]\d{2}\s*[ap]\.?\s*m\.?', texto, re.IGNORECASE):
            continue
        # Excluir items que sean solo números con dos puntos (formato hora sin a.m./p.m.)
        if re.match(r'^\d{1,2}:\d{2}$', texto.strip()):
            continue
        items_sin_hora.append((bbox, texto, confianza))

    # === MONTO ===
    monto = None

    # Intento 1: patrón "S/XX" o "S/ XX" en texto sin hora
    match = re.search(r'[Ss]\s*/\s*\.?\s*(\d+(?:[.,]\d{1,2})?)', texto_sin_hora)
    if match:
        monto = match.group(1).replace(',', '.')

    # Intento 2: item completo que sea "S/XX"
    if not monto:
        for bbox, texto, confianza in items_sin_hora:
            match_item = re.match(r'^[Ss]\s*/\s*(\d+(?:[.,]\d{1,2})?)\s*$', texto.strip())
            if match_item:
                monto = match_item.group(1).replace(',', '.')
                break

    # Intento 3: variaciones de "S/" mal leídas (SI, S1, etc.) y siguiente número
    if not monto:
        items = [r[1] for r in items_sin_hora]
        patrones_s = [
            r'^[Ss]\s*/\s*$',
            r'^[Ss]\s*[Il1|]\s*$',
            r'^[Ss]/?$',
            r'^[8Bb]\s*/\s*$',
        ]
        for i, item in enumerate(items):
            item_limpio = item.strip()
            if any(re.match(p, item_limpio) for p in patrones_s):
                if i + 1 < len(items):
                    siguiente = items[i + 1]
                    match_num = re.search(r'(\d+(?:[.,]\d{1,2})?)', siguiente)
                    if match_num:
                        monto = match_num.group(1).replace(',', '.')
                        break

    # Intento 4 (fallback): número con pinta de monto en los primeros items
    # Excluye cualquier item con dos puntos (que sería formato de hora)
    if not monto:
        primeros_items = items_sin_hora[:6]
        for bbox, texto, confianza in primeros_items:
            texto_limpio = texto.strip()
            # Saltar si tiene dos puntos (probablemente hora)
            if ':' in texto_limpio:
                continue
            match_num = re.match(r'^(\d{1,5}(?:[.,]\d{1,2})?)$', texto_limpio)
            if match_num and confianza > 0.5:
                monto = match_num.group(1).replace(',', '.')
                break

    # === NÚMERO DE OPERACIÓN ===
    op = re.search(
        r'(?:operaci[oó]n|c[oó]d\.?\s*operaci[oó]n)[:\s]*(\d+)',
        texto_completo,
        re.IGNORECASE
    )
    if not op:
        op = re.search(r'\b(\d{7,10})\b', texto_completo)
    numero_operacion = op.group(1) if op else None

    # === FECHA ===
    # Intento 1: "20 dic. 2025" (formato Yape)
    fecha_match = re.search(r'(\d{1,2}\s+\w+\.?\s+\d{4})', texto_completo)
    # Intento 2: "21 Abr" (formato Plin sin año)
    if not fecha_match:
        fecha_match = re.search(
            r'(\d{1,2}\s+(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\.?)',
            texto_completo,
            re.IGNORECASE
        )
    fecha = fecha_match.group(1) if fecha_match else None

    # === NOMBRE ===
    # Estrategia 1: buscar item con asterisco (formato Yape: "Juan Pere*")
    nombre = None
    for bbox, texto, confianza in resultados:
        if '*' in texto and any(c.isalpha() for c in texto):
            nombre = texto.strip()
            break

    # Estrategia 2: si no hay asterisco, buscar después del saludo (formato Plin)
    if not nombre:
        items = [r[1] for r in resultados]
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

    # === ARMAR RESPUESTA ===
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
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")

    contenido = await file.read()
    nparr = np.frombuffer(contenido, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="No se pudo leer la imagen")

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
    
    