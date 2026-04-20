FROM python:3.11-slim

# Dependencias del sistema para OpenCV y easyocr
RUN apt-get update && \
    apt-get install -y \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-descargar el modelo de easyocr para español
# (así no tarda en la primera petición)
RUN python -c "import easyocr; easyocr.Reader(['es'], gpu=False)"

# Copiar el código del proyecto
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]