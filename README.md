# PyVideoPlyer

Reproductor de vídeo sencillo con funcionalidad de corte por segmentos (PySide6 + ffmpeg/moviepy).

Este repositorio contiene una demo de reproductor con GUI (PySide6) y utilidades para dividir un vídeo en fragmentos MP4 de duración fija. Incluye:

- Reproductor básico (abrir, reproducir/pausar, stop, seek, volumen).
- Función "Cortar" que divide el archivo cargado en partes de N segundos (la última parte contiene el resto).
- Opción para "Forzar cortes precisos" (recodificar cada segmento y evitar solapamientos).
- Verificación post-corte: los fragmentos se comprueban y se recodifican sólo si presentan problemas de duración (evita recodificar todo cuando no hace falta).
- Logging detallado en modo DEBUG para depurar start_ms/end_ms y el método usado por ffmpeg (copy vs recode).

Estado: demo / proof of concept.

---

Características principales

- División por segmentos en milisegundos (evita acumulación de floats y garantiza contigüidad aritmética).
- Dos estrategias de extracción con ffmpeg:
  - Stream copy (rápido): `-ss` antes de `-i` (puede reajustar al keyframe y aparentar solapamientos).
  - Precise recode (lento): `-i` antes de `-ss` (cortes exactos, sin solapamientos).
- Verificación automática que regraba sólo los fragmentos problemáticos usando recodificación precisa.
- Nombres de salida cortos y secuenciales: `VID-0001.mp4`, `VID-0002.mp4`, ...

---

Requisitos

- Python 3.9+
- Windows (probado), aunque muchas partes funcionan en Linux/macOS si instalas ffmpeg.
- Dependencias (ver `requirements.txt`):
  - PySide6
  - moviepy (opcional: si falta, el programa usa ffmpeg directamente)
  - imageio-ffmpeg (recomendado)

Para instalar dependencias (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Si no quieres instalar `moviepy`, asegúrate de tener `ffmpeg` y `ffprobe` disponibles (o instaladas a través de `imageio-ffmpeg`).

---

Ejecución

Desde PowerShell:

```powershell
python main.py
```

Se abrirá la ventana del reproductor.

---

Uso de la GUI (rápido)

1. Pulsa "Abrir" y selecciona un archivo de vídeo (MP4, MKV, AVI, MOV, ... según códecs instalados).
2. Usa Play / Pause / Stop y la barra de progreso para reproducir.
3. Para dividir el vídeo en partes: pulsa "Cortar". Se pedirá:
   - Duración del segmento en segundos (entero).
   - Carpeta donde guardar los MP4 resultantes.
4. Opciones (checkboxes junto al botón "Cortar"):
   - Forzar cortes precisos: recodifica cada segmento con ffmpeg para cortes exactos (más lento).
   - Activar logs DEBUG: activa logging en la terminal para ver start_ms/end_ms y mensajes de ffmpeg.

Notas sobre la verificación post-corte

- Tras generar los fragmentos la herramienta comprueba la duración real de cada MP4.
- Si un fragmento excede la duración esperada por más de una tolerancia (por defecto ~80 ms), se considera problemático y se reextrae (recodifica) sólo ese fragmento con modo preciso.
- Esto permite usar la vía rápida por defecto (stream-copy) y corregir solamente donde haga falta.

Formato de salida

- Los ficheros generados usan nombres cortos: `VID-0001.mp4`, `VID-0002.mp4`, ... y se guardan en la carpeta que indiques.

---

Variables de entorno útiles

- `PYVID_DEBUG=1` — activa logging DEBUG (misma funcionalidad que marcar "Activar logs DEBUG" en la GUI); muestra los start_ms/end_ms y mensajes de verificación.
- `PYVID_SPLIT_FORCE_PRECISE=1` — fuerza recodificación precisa para todos los segmentos (misma funcionalidad que marcar "Forzar cortes precisos").

Ejemplo (PowerShell):

```powershell
$env:PYVID_DEBUG='1'; $env:PYVID_SPLIT_FORCE_PRECISE='1'
python main.py
```

---

Uso desde línea de comandos / scripts

Se proporciona la función `split_video(input_path, output_dir, segment_length)` en `splitter.py`.
También hay scripts de utilidad en `tools/`:

- `tools/print_segments.py duration_seconds segment_length_seconds` — imprime start_ms/end_ms para una duración y longitud de segmento sin tocar archivos de vídeo.
- `tools/integration_test_split.py` — genera un vídeo de prueba (usa ffmpeg), corta en 2s con y sin forzar recodificación, y muestra logs. Útil para verificar el comportamiento de la librería en tu máquina.

---

Problemas comunes y soluciones

- "La biblioteca 'moviepy' no está disponible":
  - Mensaje que sugiere: `python -m pip install moviepy imageio-ffmpeg`.
  - Si no quieres instalar `moviepy`, asegúrate de tener `ffmpeg` (o `imageio-ffmpeg`) para que el splitter use ffmpeg directamente.
- Si ves que las partes parecen solaparse al reproducir:
  - Marca "Forzar cortes precisos" o ejecuta con `PYVID_SPLIT_FORCE_PRECISE=1` para recodificar en modo preciso.
  - La verificación post-corte debería recodificar automáticamente los fragmentos problemáticos incluso si usas la vía rápida.
- Si los cortes son lentos:
  - La recodificación precisa es más lenta; la estrategia por defecto intenta copia de streams (rápida) y corrige sólo lo necesario.

---

Desarrollo y tests

- Ejecuta los scripts de `tools/` para comprobar comportamiento en tu entorno.
- Si añades cambios al splitter o GUI:
  - Ejecuta `tools/integration_test_split.py` para una verificación rápida.
  - Puedes usar `pytest` si añades tests en `tests/` (no incluidos por defecto).

---

Licencia

Proyecto licenciado bajo MIT License — ver `LICENSE`.

---

Contribuciones

Pull requests bienvenidos. Para cambios grandes, abre primero una issue para discutir la aproximación.

---

Contacto

Si quieres que implemente mejoras (por ejemplo: prefijo configurable para nombres de salida, ajuste de tolerancia desde la GUI, o integración con ffmpeg en segundo plano con barra de progreso), dime cuál y lo implemento.
