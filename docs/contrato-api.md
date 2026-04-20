# Contrato del API - CobrApp

Define qué recibe y qué devuelve la API Python, para que n8n pueda integrarse sin esperar a que la API esté 100% terminada.

## Endpoints

### `GET /health`
Verifica que la API está viva.

**Respuesta:**
```json
{"status": "ok", "servicio": "CobrApp API"}
```

---

### `POST /procesar-imagen`

**Recibe:** archivo de imagen (`multipart/form-data`, campo `file`)  
**Formatos:** PNG, JPG, JPEG

#### ✅ Caso 1: Pago válido
```json
{
  "valido": true,
  "tipo": "Yape",
  "monto": 20.50,
  "nombre": "Raul Roj*",
  "numero_operacion": "19063168",
  "fecha": "18 abr. 2026",
  "hora": "03.48 p. m",
  "mensaje_error": null
}
```

#### ⚠️ Caso 2: Datos incompletos
```json
{
  "valido": false,
  "tipo": "Yape",
  "monto": null,
  "nombre": "Raul Roj*",
  "numero_operacion": "19063168",
  "fecha": "18 abr. 2026",
  "hora": null,
  "mensaje_error": "No se pudo extraer el monto"
}
```

#### ❌ Caso 3: No es un pago
```json
{
  "valido": false,
  "tipo": "Desconocido",
  "monto": null,
  "nombre": null,
  "numero_operacion": null,
  "fecha": null,
  "hora": null,
  "mensaje_error": "La imagen no corresponde a un pago Yape o Plin"
}
```

---

### `GET /pagos`
Lista los pagos procesados del día (útil para debug).

### `GET /reporte`
Devuelve el total recaudado del día.

---

## Campos

| Campo              | Tipo              | Descripción                                   |
|--------------------|-------------------|-----------------------------------------------|
| `valido`           | boolean           | `true` solo si tipo, monto y operación OK     |
| `tipo`             | string            | "Yape", "Plin" o "Desconocido"                |
| `monto`            | number o null     | Valor en soles                                |
| `nombre`           | string o null     | Nombre del pagador tal como aparece           |
| `numero_operacion` | string o null     | Código único de la transacción                |
| `fecha`            | string o null     | Fecha tal como aparece                        |
| `hora`             | string o null     | Hora tal como aparece                         |
| `mensaje_error`    | string o null     | Descripción del error si `valido` es `false`  |

---

## URL desde n8n

Dentro de la red Docker interna:
```
http://python-api:8000/procesar-imagen
```

NO usar `localhost` dentro de n8n — usar el nombre del servicio.

---

## Notas importantes

- El **código de seguridad** de Yape/Plin NO se procesa ni se guarda (privacidad).
- La **detección de duplicados** se hace en n8n al escribir en Google Sheets (no en la API).
- El modelo de easyocr se precarga al arrancar el contenedor, así la primera petición no tarda.