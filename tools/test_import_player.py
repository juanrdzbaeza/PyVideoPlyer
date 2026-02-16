import sys
import os
import traceback

# Añadir carpeta raíz del proyecto al sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

print('=== test_import_player: inicio ===')
try:
    import player
    print('import player: OK')
    if hasattr(player, 'VideoPlayer'):
        print('player.VideoPlayer: OK')
    else:
        print('player.VideoPlayer: MISSING')
except Exception as e:
    print('IMPORT ERROR:')
    traceback.print_exc()

print('=== test_import_player: fin ===')
