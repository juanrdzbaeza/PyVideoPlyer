from PySide6.QtCore import Qt, QUrl, QThread, Signal, QObject
from PySide6.QtWidgets import (
    QWidget, QPushButton, QSlider, QLabel,
    QHBoxLayout, QVBoxLayout, QFileDialog, QStyle, QInputDialog, QMessageBox, QProgressDialog, QCheckBox, QListWidget, QMenu, QAbstractItemView
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtGui import QGuiApplication
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

        # Botones principales
        self.open_btn = QPushButton("Abrir")
        self.open_btn.clicked.connect(self.open_file)

        self.add_queue_btn = QPushButton("Añadir a cola")
        self.add_queue_btn.clicked.connect(self.add_to_queue_dialog)

        self.import_btn = QPushButton("Importar cola")
        self.import_btn.clicked.connect(self.import_playlist_dialog)

        self.export_btn = QPushButton("Exportar cola")
        self.export_btn.clicked.connect(self.export_playlist_dialog)

        self.add_folder_btn = QPushButton("Añadir carpeta")
        self.add_folder_btn.clicked.connect(self.add_folder_dialog)

        self.remove_btn = QPushButton("Eliminar seleccionado")
        self.remove_btn.clicked.connect(self.remove_selected)

        self.clear_btn = QPushButton("Limpiar cola")
        self.clear_btn.clicked.connect(self.clear_playlist)

        self.prev_btn = QPushButton()
        self.prev_btn.setEnabled(False)
        self.prev_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.prev_btn.clicked.connect(self.prev_track)

        self.play_btn = QPushButton()
        self.play_btn.setEnabled(False)
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_btn.clicked.connect(self.toggle_play)

        self.next_btn = QPushButton()
        self.next_btn.setEnabled(False)
        self.next_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.next_btn.clicked.connect(self.next_track)

        self.stop_btn = QPushButton()
        self.stop_btn.setEnabled(False)
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_btn.clicked.connect(self.stop)

        self.fullscreen_btn = QPushButton("Pantalla completa")
        self.fullscreen_btn.setCheckable(True)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        # Nuevo: botón para cortar en segmentos
        self.split_btn = QPushButton("Cortar")
        self.split_btn.setEnabled(False)
        self.split_btn.clicked.connect(self.request_split)

        # Checkboxes para opciones de corte y logs
        self.chk_force_precise = QCheckBox("Forzar cortes precisos")
        self.chk_force_precise.setToolTip("Recodifica cada segmento para cortes exactos (más lento)")
        self.chk_debug_logs = QCheckBox("Activar logs DEBUG")
        self.chk_debug_logs.setToolTip("Activa logs DEBUG para ver start_ms/end_ms durante el corte")

        # Checkbox para loop y shuffle
        self.chk_loop = QCheckBox("Bucle")
        self.chk_loop.setToolTip("Si está activado, la cola se reproducirá en bucle")
        self.chk_loop.stateChanged.connect(lambda s: setattr(self, 'loop', bool(s)))

        self.chk_shuffle = QCheckBox("Aleatorio")
        self.chk_shuffle.setToolTip("Si está activado, se reproducirán pistas aleatorias de la cola")
        self.chk_shuffle.stateChanged.connect(lambda s: setattr(self, 'shuffle', bool(s)))

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
        control_layout.addWidget(self.chk_force_precise)
        control_layout.addWidget(self.chk_debug_logs)
        control_layout.addWidget(self.chk_loop)
        control_layout.addWidget(self.chk_shuffle)
        control_layout.addWidget(QLabel("Vol:"))
        control_layout.addWidget(self.volume_slider)

        # Explicación visible para los checkboxes (breve)
        self.chk_help_label = QLabel()
        self.chk_help_label.setText(
            "Forzar cortes precisos: recodifica cada parte para cortes exactos (más lento).\n"
            "Activar logs DEBUG: muestra start_ms/end_ms y si se usó copy o recode en la salida."
        )
        self.chk_help_label.setWordWrap(True)
        self.chk_help_label.setStyleSheet('color: #444444; font-size: 11px;')

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.position_slider)
        bottom_layout.addWidget(self.time_label)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.video_widget)
        main_layout.addLayout(bottom_layout)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.chk_help_label)

        self.setLayout(main_layout)

        # Conexiones del player
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.playbackStateChanged.connect(self.playback_state_changed)
        self.player.errorOccurred.connect(self.handle_error)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir vídeo", "", "Video Files (*.mp4 *.mkv *.avi *.mov);;All Files (*)")
        if file_path:
            url = QUrl.fromLocalFile(file_path)
            self.player.setSource(url)
            self.play_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.split_btn.setEnabled(True)
            self.current_file = file_path
            # Auto play al abrir
            self.player.play()

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
            if self.chk_force_precise.isChecked():
                os.environ['PYVID_SPLIT_FORCE_PRECISE'] = '1'
            else:
                if 'PYVID_SPLIT_FORCE_PRECISE' in os.environ:
                    del os.environ['PYVID_SPLIT_FORCE_PRECISE']

            # Activar logging DEBUG si el checkbox está marcado
            if self.chk_debug_logs.isChecked():
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
