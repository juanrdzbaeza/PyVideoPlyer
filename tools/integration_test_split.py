"""Script de integración rápido para verificar split_video y la verificación post-corte.
Genera un vídeo corto con ffmpeg (usando el binario detectado), luego corta en segmentos de 2s
primero sin forzar recodificación, y después forzando recodificación precisa.

Imprime los resultados y logs.
"""
import os
import subprocess
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import splitter
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('integration_test')

work_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'test_out'))
os.makedirs(work_dir, exist_ok=True)
input_path = os.path.join(work_dir, 'test_input.mp4')

ff = splitter._find_ffmpeg_executable()
if not ff:
    print('No ffmpeg encontrado; abortando test')
    sys.exit(1)

# Generar un video de 6 segundos (testsrc)
if not os.path.exists(input_path):
    cmd = [ff, '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=30', '-t', '6', '-pix_fmt', 'yuv420p', '-c:v', 'libx264', input_path]
    print('Generando video de prueba...')
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print('ffmpeg fallo al crear video:', proc.stderr)
        sys.exit(1)
    print('Video creado en', input_path)
else:
    print('Video de prueba ya existe:', input_path)

# Ejecutar split sin forzar (intento de stream copy)
out1 = os.path.join(work_dir, 'out_fast')
os.makedirs(out1, exist_ok=True)
print('\nCortando sin forzar recodificación (rápido):')
try:
    splitter.__dict__['__split_debug'] = True
except Exception:
    pass
if 'PYVID_SPLIT_FORCE_PRECISE' in os.environ:
    del os.environ['PYVID_SPLIT_FORCE_PRECISE']

res1 = splitter.split_video(input_path, out1, 2)
print('Outputs fast:', res1)

# Ejecutar split forzando recodificación precisa
out2 = os.path.join(work_dir, 'out_precise')
os.makedirs(out2, exist_ok=True)
print('\nCortando forzando recodificación precisa:')
os.environ['PYVID_SPLIT_FORCE_PRECISE'] = '1'
res2 = splitter.split_video(input_path, out2, 2)
print('Outputs precise:', res2)

print('\nTest finalizado.')

