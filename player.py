from PySide6.QtCore import Qt, QUrl, QThread, Signal, QObject, QEvent
from PySide6.QtWidgets import (
    QWidget, QPushButton, QSlider, QLabel,
    QHBoxLayout, QVBoxLayout, QFileDialog, QStyle, QInputDialog, QMessageBox, QProgressDialog, QCheckBox, QListWidget, QMenu, QAbstractItemView, QSizePolicy
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtGui import QGuiApplication, QShortcut, QKeySequence
import os
import logging
import random


class VideoPlayer(QWidget):
    """Reproductor de vídeo simple usando PySide6.

    Controles adicionales: cola de reproducción, anterior/siguiente, pantalla completa,
    bucle (loop) y aleatorio (shuffle).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PyVideoPlayer")
        self.resize(900, 640)

        # Estado de la cola/reproducción
        self.playlist = []  # list[str]
        self.current_index = -1
        self.loop = False
        self.shuffle = False

        # Guardar ruta del archivo actual
        self.current_file = None

        # Player multimedia
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        # Widget de vídeo
        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)

        # Botones principales (iconos + tooltips para una UI más compacta)
        self.open_btn = QPushButton()
        self.open_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.open_btn.setToolTip('Abrir archivo')
        self.open_btn.clicked.connect(self.open_file)

        self.add_queue_btn = QPushButton()
        self.add_queue_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        self.add_queue_btn.setToolTip('Añadir archivos a la cola')
        self.add_queue_btn.clicked.connect(self.add_to_queue_dialog)

        self.import_btn = QPushButton()
        self.import_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.import_btn.setToolTip('Importar cola (JSON)')
        self.import_btn.clicked.connect(self.import_playlist_dialog)

        self.export_btn = QPushButton()
        self.export_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.export_btn.setToolTip('Exportar cola (JSON)')
        self.export_btn.clicked.connect(self.export_playlist_dialog)

        self.add_folder_btn = QPushButton()
        self.add_folder_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.add_folder_btn.setToolTip('Añadir carpeta entera a la cola')
        self.add_folder_btn.clicked.connect(self.add_folder_dialog)

        self.remove_btn = QPushButton()
        self.remove_btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self.remove_btn.setToolTip('Eliminar seleccionado')
        self.remove_btn.clicked.connect(self.remove_selected)

        self.clear_btn = QPushButton()
        self.clear_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.clear_btn.setToolTip('Limpiar cola')
        self.clear_btn.clicked.connect(self.clear_playlist)

        self.prev_btn = QPushButton()
        self.prev_btn.setEnabled(False)
        self.prev_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.prev_btn.setToolTip('Anterior')
        self.prev_btn.clicked.connect(self.prev_track)

        self.play_btn = QPushButton()
        self.play_btn.setEnabled(False)
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_btn.setToolTip('Play / Pause (Space)')
        self.play_btn.clicked.connect(self.toggle_play)

        self.next_btn = QPushButton()
        self.next_btn.setEnabled(False)
        self.next_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.next_btn.setToolTip('Siguiente')
        self.next_btn.clicked.connect(self.next_track)

        self.stop_btn = QPushButton()
        self.stop_btn.setEnabled(False)
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_btn.setToolTip('Stop')
        self.stop_btn.clicked.connect(self.stop)

        self.fullscreen_btn = QPushButton()
        self.fullscreen_btn.setCheckable(True)
        self.fullscreen_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
        self.fullscreen_btn.setToolTip('Pantalla completa (F / Esc para salir)')
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        # Nuevo: botón para cortar en segmentos
        self.split_btn = QPushButton("Cortar")
        self.split_btn.setEnabled(False)
        self.split_btn.clicked.connect(self.request_split)

        # Opciones como botones toggle (compactos con iconos)
        # Forzar cortes precisos
        self.btn_force_precise = QPushButton()
        self.btn_force_precise.setCheckable(True)
        try:
            self.btn_force_precise.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        except Exception:
            pass
        self.btn_force_precise.setToolTip('Forzar cortes precisos: recodifica cada segmento para cortes exactos (más lento)')

        # Activar logs DEBUG
        self.btn_debug_logs = QPushButton()
        self.btn_debug_logs.setCheckable(True)
        try:
            self.btn_debug_logs.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        except Exception:
            pass
        self.btn_debug_logs.setToolTip('Activar logs DEBUG: muestra start_ms/end_ms y si se usó copy o recode')

        # Bucle (loop)
        self.btn_loop = QPushButton()
        self.btn_loop.setCheckable(True)
        try:
            self.btn_loop.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        except Exception:
            pass
        self.btn_loop.setToolTip('Bucle')
        self.btn_loop.toggled.connect(lambda s: (setattr(self, 'loop', bool(s)), self.save_settings()))

        # Aleatorio (shuffle)
        self.btn_shuffle = QPushButton()
        self.btn_shuffle.setCheckable(True)
        # Intentar icono de tema (media-playlist-shuffle), luego asset local, luego estándar
        try:
            from PySide6.QtGui import QIcon
            icon = QIcon.fromTheme('media-playlist-shuffle')
            if icon is None or icon.isNull():
                asset_path = os.path.join(os.path.dirname(__file__), 'assets', 'shuffle.svg')
                if os.path.exists(asset_path):
                    icon = QIcon(asset_path)
            if icon is None or icon.isNull():
                icon = self.style().standardIcon(QStyle.SP_BrowserStop)
            self.btn_shuffle.setIcon(icon)
        except Exception:
            try:
                self.btn_shuffle.setIcon(self.style().standardIcon(QStyle.SP_BrowserStop))
            except Exception:
                pass
        self.btn_shuffle.setToolTip('Aleatorio')
        self.btn_shuffle.toggled.connect(lambda s: (setattr(self, 'shuffle', bool(s)), self.save_settings()))

        # Slider de progreso
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.seek)

        # Volumen
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.audio_output.setVolume(self.volume_slider.value() / 100.0)

        # Etiqueta de tiempo
        self.time_label = QLabel("00:00 / 00:00")

        # Lista de reproducción
        self.playlist_widget = QListWidget()
        self.playlist_widget.setSelectionMode(QListWidget.SingleSelection)
        self.playlist_widget.setDragDropMode(QAbstractItemView.InternalMove)
        # Conectar reordenado para sincronizar la lista interna
        try:
            self.playlist_widget.model().rowsMoved.connect(self.on_playlist_reordered)
        except Exception:
            pass
        self.playlist_widget.itemDoubleClicked.connect(self.on_playlist_double_click)
        self.playlist_widget.setMinimumWidth(240)

        # Layouts
        control_layout = QHBoxLayout()
        control_layout.addWidget(self.open_btn)
        control_layout.addWidget(self.add_queue_btn)
        control_layout.addWidget(self.import_btn)
        control_layout.addWidget(self.export_btn)
        control_layout.addWidget(self.add_folder_btn)
        control_layout.addWidget(self.remove_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.addWidget(self.prev_btn)
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.next_btn)
        control_layout.addWidget(self.fullscreen_btn)
        control_layout.addWidget(self.split_btn)
        # botones compactos para opciones
        control_layout.addWidget(self.btn_force_precise)
        control_layout.addWidget(self.btn_debug_logs)
        control_layout.addWidget(self.btn_loop)
        control_layout.addWidget(self.btn_shuffle)
        control_layout.addWidget(QLabel("Vol:"))
        control_layout.addWidget(self.volume_slider)

        # Botón de ayuda compacto (abre cuadro informativo)
        self.info_btn = QPushButton()
        self.info_btn.setToolTip('Ayuda rápida')
        try:
            self.info_btn.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxQuestion))
        except Exception:
            pass
        def _show_quick_help():
            QMessageBox.information(self, 'Ayuda',
                'Forzar cortes precisos: recodifica cada parte para cortes exactos (más lento).\n'
                'Activar logs DEBUG: muestra start_ms/end_ms y si se usó copy o recode en la salida.\n'
                'Bucle: reproduce la cola en bucle. Aleatorio: reproduce en orden aleatorio.')
        self.info_btn.clicked.connect(_show_quick_help)

        # Etiqueta de ayuda compacta (muy breve)
        self.small_help_label = QLabel("Pulsa '?' para ayuda")
        self.small_help_label.setStyleSheet('color: #666666; font-size: 11px;')
        self.small_help_label.setToolTip('Forzar cortes precisos: recodifica cada parte para cortes exactos (más lento).\n'
                                        'Activar logs DEBUG: muestra start_ms/end_ms y si se usó copy o recode en la salida.')

        # Barra de tiempo (layout horizontal: slider expande, label a la derecha)
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.position_slider, 1)
        bottom_layout.addWidget(self.time_label)

        # Forzar que el video ocupe el espacio disponible
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Ajuste de la lista de reproducción para no ser demasiado ancha
        try:
            self.playlist_widget.setMaximumWidth(360)
            self.playlist_widget.setMinimumWidth(200)
        except Exception:
            pass

        # Componer layout: a la izquierda columna vertical con video(expand) -> tiempo -> controles (pegados abajo)
        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        # Video con stretch para ocupar todo el espacio disponible
        left_layout.addWidget(self.video_widget, 1)
        # Barra de tiempo encima de la botonera
        left_layout.addLayout(bottom_layout)
        # Botonera en la parte inferior
        left_layout.addLayout(control_layout)
        # Etiqueta de ayuda compacta debajo de la botonera (opcional, no ocupa mucho)
        left_layout.addWidget(self.small_help_label)

        main_layout.addLayout(left_layout)
        main_layout.addWidget(self.playlist_widget)

        self.setLayout(main_layout)

        # Habilitar drag & drop para añadir archivos a la cola
        self.setAcceptDrops(True)
        self.playlist_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self.show_playlist_context_menu)

        # Instalar event filter en el widget de vídeo para capturar teclas incluso cuando tenga el foco
        try:
            self.video_widget.installEventFilter(self)
        except Exception:
            pass

        # Shortcuts globales (mientras la ventana esté activa) para fullscreen y escape
        try:
            self._sc_toggle_fs = QShortcut(QKeySequence(Qt.Key_F), self)
            self._sc_toggle_fs.activated.connect(lambda: self.set_fullscreen(not self.fullscreen_btn.isChecked()))
            self._sc_escape = QShortcut(QKeySequence(Qt.Key_Escape), self)
            self._sc_escape.activated.connect(lambda: self.set_fullscreen(False) if self.fullscreen_btn.isChecked() else None)
        except Exception:
            pass

        # Conexiones del player
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.playbackStateChanged.connect(self.playback_state_changed)
        self.player.errorOccurred.connect(self.handle_error)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)

        # Cargar settings guardados (last_dir, loop, shuffle)
        try:
            self._settings_path = os.path.join(os.path.expanduser('~'), '.pyvideoplayer.json')
            self.load_settings()
        except Exception:
            self._settings_path = None

    def export_playlist_dialog(self):
        if not self.playlist:
            QMessageBox.information(self, 'Exportar cola', 'La cola está vacía.')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar cola', os.path.expanduser('~'), 'JSON files (*.json);;All Files (*)')
        if not path:
            return
        try:
            import json
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.playlist, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, 'Exportar cola', f'Cola exportada a: {path}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'No se pudo exportar la cola: {e}')

    def import_playlist_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Importar cola', os.path.expanduser('~'), 'JSON files (*.json);;All Files (*)')
        if not path:
            return
        try:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                # filtrar rutas existentes
                files = [p for p in data if os.path.isfile(p)]
                if files:
                    self.add_to_queue(files)
                    QMessageBox.information(self, 'Importar cola', f'Se importaron {len(files)} entradas')
                else:
                    QMessageBox.information(self, 'Importar cola', 'No se encontraron archivos válidos en el JSON')
            else:
                QMessageBox.critical(self, 'Importar cola', 'Formato de archivo no válido')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'No se pudo importar la cola: {e}')

    def save_settings(self):
        try:
            if not hasattr(self, '_settings_path') or not self._settings_path:
                return
            import json
            s = {'last_dir': getattr(self, 'last_dir', os.path.expanduser('~')),
                 'loop': bool(self.loop),
                 'shuffle': bool(self.shuffle),
                 'force_precise': bool(getattr(self, 'btn_force_precise', False) and getattr(self, 'btn_force_precise').isChecked()),
                 'debug_logs': bool(getattr(self, 'btn_debug_logs', False) and getattr(self, 'btn_debug_logs').isChecked())}
            with open(self._settings_path, 'w', encoding='utf-8') as f:
                json.dump(s, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_settings(self):
        try:
            if not hasattr(self, '_settings_path') or not self._settings_path:
                self._settings_path = os.path.join(os.path.expanduser('~'), '.pyvideoplayer.json')
            if os.path.exists(self._settings_path):
                import json
                with open(self._settings_path, 'r', encoding='utf-8') as f:
                    s = json.load(f)
                self.last_dir = s.get('last_dir', os.path.expanduser('~'))
                self.loop = bool(s.get('loop', False))
                self.shuffle = bool(s.get('shuffle', False))
                self.btn_loop.setChecked(self.loop)
                self.btn_shuffle.setChecked(self.shuffle)
                # restaurar botones compactos si existen en settings
                try:
                    if 'force_precise' in s and hasattr(self, 'btn_force_precise'):
                        self.btn_force_precise.setChecked(bool(s.get('force_precise', False)))
                    if 'debug_logs' in s and hasattr(self, 'btn_debug_logs'):
                        self.btn_debug_logs.setChecked(bool(s.get('debug_logs', False)))
                    if hasattr(self, 'btn_loop'):
                        self.btn_loop.setChecked(self.loop)
                    if hasattr(self, 'btn_shuffle'):
                        self.btn_shuffle.setChecked(self.shuffle)
                except Exception:
                    pass
            else:
                self.last_dir = os.path.expanduser('~')
        except Exception:
            self.last_dir = os.path.expanduser('~')

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        mime = event.mimeData()
        files = []
        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if os.path.isfile(path):
                    files.append(path)
        if files:
            self.add_to_queue(files)
        event.acceptProposedAction()

    def keyPressEvent(self, event):
        key = event.key()
        # Space: play/pause
        if key == Qt.Key_Space:
            self.toggle_play()
            event.accept()
            return
        # Right: next
        if key == Qt.Key_Right:
            self.next_track()
            event.accept()
            return
        # Left: prev
        if key == Qt.Key_Left:
            self.prev_track()
            event.accept()
            return
        # F: fullscreen toggle
        if key == Qt.Key_F:
            self.fullscreen_btn.toggle()
            self.toggle_fullscreen(self.fullscreen_btn.isChecked())
            event.accept()
            return
        # Esc: salir de fullscreen si está activo
        if key == Qt.Key_Escape:
            if self.fullscreen_btn.isChecked():
                self.fullscreen_btn.setChecked(False)
                self.toggle_fullscreen(False)
                event.accept()
                return
        # Delete: remove selected
        if key == Qt.Key_Delete:
            self.remove_selected()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        # Capturar teclas en el video_widget para manejar fullscreen/escape
        try:
            if obj is self.video_widget and event.type() == QEvent.KeyPress:
                k = event.key()
                if k == Qt.Key_F:
                    # alternar fullscreen
                    new_state = not self.fullscreen_btn.isChecked()
                    self.fullscreen_btn.setChecked(new_state)
                    self.toggle_fullscreen(new_state)
                    return True
                if k == Qt.Key_Escape:
                    if self.fullscreen_btn.isChecked():
                        self.fullscreen_btn.setChecked(False)
                        self.toggle_fullscreen(False)
                        return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def show_playlist_context_menu(self, pos):
        row = self.playlist_widget.row(self.playlist_widget.itemAt(pos))
        menu = QMenu(self)
        play_act = menu.addAction("Reproducir")
        remove_act = menu.addAction("Eliminar")
        clear_act = menu.addAction("Limpiar cola")
        act = menu.exec(self.playlist_widget.mapToGlobal(pos))
        if act == play_act and row >= 0:
            self.play_index(row)
        elif act == remove_act and row >= 0:
            self.playlist.pop(row)
            if row == self.current_index:
                # si se estaba reproduciendo, parar o mover a siguiente
                if row < len(self.playlist):
                    self.play_index(row)
                elif len(self.playlist) > 0:
                    self.play_index(len(self.playlist)-1)
                else:
                    self.player.stop()
                    self.current_index = -1
            elif self.current_index > row:
                self.current_index -= 1
            self.update_playlist_view()
        elif act == clear_act:
            self.clear_playlist()

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir vídeo", "", "Video Files (*.mp4 *.mkv *.avi *.mov);;All Files (*)")
        if file_path:
            # Abrir un único archivo y reemplazar la cola
            self.playlist = [file_path]
            self.current_index = 0
            self.update_playlist_view()
            self.play_index(0)

    def add_to_queue_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Añadir archivos a la cola", getattr(self, 'last_dir', os.path.expanduser('~')), "Video Files (*.mp4 *.mkv *.avi *.mov);;All Files (*)")
        if files:
            self.last_dir = os.path.dirname(files[0])
            self.add_to_queue(files)

    def add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecciona carpeta", getattr(self, 'last_dir', os.path.expanduser('~')))
        if not folder:
            return
        # Buscar archivos de vídeo comunes en la carpeta (no recursivo)
        exts = ('.mp4', '.mkv', '.avi', '.mov')
        files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(exts)]
        files.sort()
        if files:
            self.last_dir = folder
            self.add_to_queue(files)

    def remove_selected(self):
        row = self.playlist_widget.currentRow()
        if row >= 0 and row < len(self.playlist):
            was_current = (row == self.current_index)
            removed = self.playlist.pop(row)
            # ajustar current_index
            if was_current:
                # intentar reproducir siguiente lógico
                if row < len(self.playlist):
                    self.play_index(row)
                elif len(self.playlist) > 0:
                    self.play_index(len(self.playlist)-1)
                else:
                    self.player.stop()
                    self.current_index = -1
                    self.current_file = None
            else:
                if self.current_index > row:
                    self.current_index -= 1
            self.update_playlist_view()

    def clear_playlist(self):
        self.playlist.clear()
        self.current_index = -1
        self.current_file = None
        self.player.stop()
        self.update_playlist_view()

    def add_to_queue(self, files, play_immediately=False):
        # Añadir archivos a la cola y opcionalmente reproducir el primero añadido
        start_index = len(self.playlist)
        self.playlist.extend(files)
        self.update_playlist_view()
        # Habilitar controles relacionados
        self.prev_btn.setEnabled(len(self.playlist) > 1)
        self.next_btn.setEnabled(len(self.playlist) > 1)
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)

        if play_immediately:
            self.current_index = start_index
            self.play_index(self.current_index)

    def update_playlist_view(self):
        self.playlist_widget.clear()
        for i, p in enumerate(self.playlist, start=1):
            name = os.path.basename(p)
            # intentar obtener duración
            dur_s = self._probe_duration_safe(p)
            dur_str = ''
            if dur_s is not None:
                s = int(round(dur_s))
                m, s = divmod(s, 60)
                dur_str = f" ({m:02d}:{s:02d})"
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(f"{i:02d}. {name}{dur_str}")
            # Almacenar la ruta real en UserRole para reconstrucciones seguras al reordenar
            item.setData(Qt.UserRole, p)
            self.playlist_widget.addItem(item)
        # seleccionar el item actual
        if 0 <= self.current_index < self.playlist_widget.count():
            self.playlist_widget.setCurrentRow(self.current_index)

    def play_index(self, index: int):
        if index < 0 or index >= len(self.playlist):
            return
        path = self.playlist[index]
        self.current_file = path
        url = QUrl.fromLocalFile(path)
        self.player.setSource(url)
        self.player.play()
        self.current_index = index
        self.update_playlist_view()
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.prev_btn.setEnabled(len(self.playlist) > 1)
        self.next_btn.setEnabled(len(self.playlist) > 1)

    def next_track(self):
        if not self.playlist:
            return
        if self.shuffle:
            next_idx = random.randrange(len(self.playlist))
            # evitar repetir la misma pista cuando sea posible
            if len(self.playlist) > 1:
                while next_idx == self.current_index:
                    next_idx = random.randrange(len(self.playlist))
        else:
            next_idx = self.current_index + 1
            if next_idx >= len(self.playlist):
                if self.loop:
                    next_idx = 0
                else:
                    # fin de cola
                    self.player.stop()
                    return
        self.play_index(next_idx)

    def prev_track(self):
        if not self.playlist:
            return
        prev_idx = self.current_index - 1
        if prev_idx < 0:
            if self.loop:
                prev_idx = len(self.playlist) - 1
            else:
                prev_idx = 0
        self.play_index(prev_idx)

    def toggle_fullscreen(self, checked: bool):
        # Mantener compatibilidad: recibir checked desde el botón
        self.set_fullscreen(bool(checked))

    def set_fullscreen(self, enable: bool):
        """Activar/desactivar fullscreen en el widget de vídeo y sincronizar el botón."""
        try:
            self.video_widget.setFullScreen(bool(enable))
            # sincronizar el botón
            try:
                self.fullscreen_btn.setChecked(bool(enable))
            except Exception:
                pass
            # cambiar icono visual
            try:
                if enable:
                    self.fullscreen_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarNormalButton))
                else:
                    self.fullscreen_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
            except Exception:
                pass
        except Exception:
            pass

    def on_media_status_changed(self, status):
        # Detectar fin de reproducción y saltar a la siguiente pista
        try:
            from PySide6.QtMultimedia import QMediaPlayer as _QMP
            if status == _QMP.MediaStatus.EndOfMedia:
                # Saltar a siguiente automáticamente
                self.next_track()
        except Exception:
            pass

    def on_playlist_double_click(self, item):
        row = self.playlist_widget.currentRow()
        if row >= 0:
            self.play_index(row)


    def toggle_play(self):
        state = self.player.playbackState()
        # QMediaPlayer.PlayingState == 1, PausedState == 2, StoppedState == 0
        if state == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def stop(self):
        self.player.stop()

    def seek(self, position_ms: int):
        # position_slider gives milliseconds
        self.player.setPosition(position_ms)

    def set_volume(self, value: int):
        # QAudioOutput volume is float 0.0 - 1.0
        self.audio_output.setVolume(max(0.0, min(1.0, value / 100.0)))

    def position_changed(self, position: int):
        # Evitar sobrescribir cuando el usuario está moviendo el slider podría ser una mejora
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(position)
        self.position_slider.blockSignals(False)
        self.update_time_label(position, self.player.duration())

    def duration_changed(self, duration: int):
        self.position_slider.setRange(0, duration)
        self.update_time_label(self.player.position(), duration)

    def update_time_label(self, position_ms: int, duration_ms: int):
        def ms_to_hhmmss(ms: int) -> str:
            if ms <= 0:
                return "00:00"
            seconds = ms // 1000
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            if h:
                return f"{h:02d}:{m:02d}:{s:02d}"
            return f"{m:02d}:{s:02d}"

        pos_str = ms_to_hhmmss(position_ms)
        dur_str = ms_to_hhmmss(duration_ms)
        self.time_label.setText(f"{pos_str} / {dur_str}")

    def playback_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def handle_error(self, error, error_string=None):
        # Mostrar error simple en etiqueta de tiempo
        if error != QMediaPlayer.NoError:
            # Algunos bindings envían sólo un enum, otros (error, str)
            msg = str(error_string) if error_string else str(error)
            self.time_label.setText(f"Error: {msg}")

    def closeEvent(self, event):
        try:
            self.player.stop()
        except Exception:
            pass
        super().closeEvent(event)

    # ----------------- Nuevas funciones para cortar -----------------
    def request_split(self):
        """Pide al usuario el tamaño de segmento (segundos) y la carpeta de salida, y lanza el worker."""
        if not self.current_file:
            QMessageBox.warning(self, "Advertencia", "No hay vídeo cargado.")
            return

        # Pedir duración del segmento en segundos
        seg, ok = QInputDialog.getInt(self, "Tamaño de segmento", "Duración en segundos:", 10, 1, 36000, 1)
        if not ok:
            return
        if seg <= 0:
            QMessageBox.warning(self, "Valor inválido", "La duración debe ser un entero positivo mayor que 0.")
            return

        out_dir = QFileDialog.getExistingDirectory(self, "Selecciona carpeta de salida", os.path.expanduser("~"))
        if not out_dir:
            return

        # Comprobar permisos de escritura en la carpeta seleccionada
        try:
            if not os.path.isdir(out_dir):
                raise RuntimeError("La ruta seleccionada no es un directorio válido.")
            test_path = os.path.join(out_dir, ".pv_write_test")
            with open(test_path, "w", encoding="utf-8") as _f:
                _f.write("ok")
            os.remove(test_path)
        except Exception as e:
            QMessageBox.critical(self, "Error de permisos", f"No se puede escribir en la carpeta seleccionada:\n{e}")
            return

        # Preparar y lanzar worker en QThread
        try:
            from splitter import split_video
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo importar el módulo de corte: {e}")
            return

        # Mostrar diálogo de progreso indeterminado
        self._progress = QProgressDialog("Cortando vídeo...", None, 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setCancelButton(None)
        self._progress.setMinimumDuration(0)
        self._progress.show()

        # Deshabilitar temporalmente el botón de cortar para evitar reentradas
        try:
            self.split_btn.setEnabled(False)
        except Exception:
            pass

        # Aplicar opciones seleccionadas: forzar recodificación precisa y activar logs
        try:
            # Forzar cortes precisos mediante variable de entorno que lee splitter
            if self.btn_force_precise.isChecked():
                os.environ['PYVID_SPLIT_FORCE_PRECISE'] = '1'
            else:
                if 'PYVID_SPLIT_FORCE_PRECISE' in os.environ:
                    del os.environ['PYVID_SPLIT_FORCE_PRECISE']

            # Activar logging DEBUG si el checkbox está marcado
            if self.btn_debug_logs.isChecked():
                logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
                try:
                    import splitter as _spl
                    _spl.__dict__['__split_debug'] = True
                except Exception:
                    pass
            else:
                try:
                    import splitter as _spl
                    if '__split_debug' in _spl.__dict__:
                        del _spl.__dict__['__split_debug']
                except Exception:
                    pass
        except Exception:
            # No abortar si no se pueden aplicar las opciones
            pass

        # Worker usando QThread
        class SplitWorker(QObject):
            finished = Signal(list, str)

            def __init__(self, in_path, out_dir, seg_len):
                super().__init__()
                self.in_path = in_path
                self.out_dir = out_dir
                self.seg_len = seg_len

            def run(self):
                try:
                    outputs = split_video(self.in_path, self.out_dir, self.seg_len)
                    self.finished.emit(outputs, "")
                except Exception as exc:
                    self.finished.emit([], str(exc))

        self._thread = QThread()
        self._worker = SplitWorker(self.current_file, out_dir, seg)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_split_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_split_finished(self, outputs, error_str):
        # Cerrar progreso
        try:
            self._progress.close()
        except Exception:
            pass

        # Re-habilitar botón de cortar
        try:
            self.split_btn.setEnabled(True)
        except Exception:
            pass

        if error_str:
            # Si el error indica falta de moviepy, ofrecer copiar el comando de instalación
            if "moviepy" in error_str.lower():
                cmd = "python -m pip install moviepy imageio-ffmpeg"
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("Error al cortar - falta moviepy")
                msg.setText("La biblioteca 'moviepy' no está disponible o falló al importarse.")
                msg.setInformativeText(f"Para instalarla, ejecuta este comando en un terminal:\n{cmd}")
                copy_btn = msg.addButton("Copiar comando", QMessageBox.ActionRole)
                msg.addButton(QMessageBox.Close)
                msg.exec()
                if msg.clickedButton() == copy_btn:
                    try:
                        QGuiApplication.clipboard().setText(cmd)
                        QMessageBox.information(self, "Copiado", f"Comando copiado al portapapeles:\n{cmd}")
                    except Exception:
                        # Si por alguna razón el portapapeles no está disponible, mostrar el comando en un cuadro simple
                        QMessageBox.information(self, "Instalación", f"Ejecuta en terminal:\n{cmd}")
                return

            QMessageBox.critical(self, "Error al cortar", f"Se produjo un error: {error_str}")
            return

        if outputs:
            # Mostrar confirmación con número de partes y carpeta, y ejemplos de archivos generados
            dir_used = os.path.dirname(outputs[0]) if outputs else ""
            sample = "\n".join(outputs[:5]) if outputs else ""
            QMessageBox.information(self, "Corte finalizado", f"Se han generado {len(outputs)} archivos en:\n{dir_used}\n\nEjemplos:\n{sample}")
        else:
            QMessageBox.information(self, "Corte finalizado", "No se generaron archivos.")

        # Limpiar flag debug en el módulo splitter
        try:
            import splitter as _spl2
            if '__split_debug' in _spl2.__dict__:
                del _spl2.__dict__['__split_debug']
        except Exception:
            pass

        # Limpiar variable de entorno usada para forzar recodificación precisa
        try:
            if 'PYVID_SPLIT_FORCE_PRECISE' in os.environ:
                del os.environ['PYVID_SPLIT_FORCE_PRECISE']
        except Exception:
            pass

    def on_playlist_reordered(self, parent, start, end, destination, row):
        # Reconstruir self.playlist leyendo la ruta real desde item.data(Qt.UserRole)
        new_order = []
        for i in range(self.playlist_widget.count()):
            it = self.playlist_widget.item(i)
            path = it.data(Qt.UserRole)
            if path:
                new_order.append(path)
        # Si la reconstrucción tiene la misma longitud, aceptarla
        if len(new_order) == self.playlist_widget.count():
            self.playlist = new_order
            # actualizar current_index según new order
            if self.current_file and self.current_file in self.playlist:
                self.current_index = self.playlist.index(self.current_file)
            else:
                self.current_index = -1
        # Guardar settings tras reordenado
        self.save_settings()

    def _probe_duration_safe(self, path: str):
        """Intentar obtener la duración del fichero usando splitter/ffprobe; devolver None si no es posible."""
        try:
            import splitter
            ff = splitter._find_ffmpeg_executable()
            if not ff:
                return None
            dur = splitter._probe_duration_with_ffprobe(ff, path)
            return dur
        except Exception:
            return None

