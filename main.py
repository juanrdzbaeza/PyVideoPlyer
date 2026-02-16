from PySide6.QtWidgets import QApplication
import sys
import logging
import os

from player import VideoPlayer


def main(argv=None):
    if argv is None:
        argv = sys.argv

    # Activar DEBUG si la variable de entorno PYVID_DEBUG está establecida
    if os.environ.get('PYVID_DEBUG', '').lower() in ('1', 'true', 'yes'):
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
        # marcar variable global para compatibilidad con splitter
        globals()['__split_debug'] = True

    app = QApplication(argv)
    player = VideoPlayer()
    player.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
