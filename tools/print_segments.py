"""Script de ayuda para imprimir los segmentos calculados por la lógica del splitter
Sin tocar archivos de vídeo: calcula start_ms/end_ms para una duración dada y longitud de segmento.
Usar: python tools/print_segments.py <duration_seconds> <segment_length_seconds>
Activa DEBUG con la variable de entorno PYVID_DEBUG=1 para ver logs.
"""
import sys
import logging
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from splitter import _seconds_to_ms, _ms_to_seconds


def compute_segments(duration_s: float, segment_len_s: float):
    total_ms = _seconds_to_ms(duration_s)
    seg_ms = _seconds_to_ms(segment_len_s)
    segments = []
    index = 0
    while index * seg_ms < total_ms:
        start_ms = index * seg_ms
        end_ms = min((index + 1) * seg_ms, total_ms)
        segments.append((start_ms, end_ms))
        index += 1
    return segments


if __name__ == '__main__':
    if os.environ.get('PYVID_DEBUG', '').lower() in ('1', 'true', 'yes'):
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    if len(sys.argv) < 3:
        print('Uso: python tools/print_segments.py <duration_seconds> <segment_length_seconds>')
        sys.exit(1)

    duration = float(sys.argv[1])
    seglen = float(sys.argv[2])
    segs = compute_segments(duration, seglen)
    for i, (s, e) in enumerate(segs, start=1):
        print(f'part={i} start_ms={s} end_ms={e} dur_ms={e-s}')
    print(f'total parts: {len(segs)}')

