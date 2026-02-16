# PyVideoPlyer (Demo)

Reproductor de vídeo simple usando PySide6 (Qt6).

Requisitos
- Python 3.9+
- Windows (probado)

Instalación (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip; python -m pip install -r requirements.txt
```

Ejecución:

```powershell
python main.py
```

Controles implementados:
- Abrir archivo
- Play / Pause
- Stop
- Barra de progreso (seek)
- Volumen
- Cortar: dividir el vídeo cargado en fragmentos de N segundos (última parte = resto)

Uso de la funcionalidad "Cortar":
- Abra un vídeo, pulse el botón "Cortar", introduzca la duración en segundos y seleccione la carpeta donde se guardarán los MP4 resultantes.
- Si falta la dependencia `moviepy` se mostrará un mensaje con el comando para instalarla:

```powershell
python -m pip install moviepy imageio-ffmpeg
```

Notas:
- El soporte de formatos depende de los códecs del sistema. Si encuentra problemas con la reproducción de ciertos formatos, considere instalar códecs en Windows o usar la variante con VLC (requiere `python-vlc` y VLC instalado).
