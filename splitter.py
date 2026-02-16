import os
from typing import List
import traceback
import subprocess
import shutil
import logging


def _find_ffmpeg_executable():
    """Intenta localizar un ejecutable de ffmpeg.
    Primero prueba imageio_ffmpeg.get_exe(), luego busca 'ffmpeg' en PATH.
    Devuelve la ruta o None.
    """
    try:
        import imageio_ffmpeg as iioff
        # get_exe() es lo más compatible entre versiones
        try:
            exe = iioff.get_exe()
        except Exception:
            # algunas versiones usan get_ffmpeg_exe()
            exe = getattr(iioff, 'get_ffmpeg_exe', lambda: None)()
        if exe:
            return exe
    except Exception:
        pass

    # fallback a PATH
    ff = shutil.which('ffmpeg')
    if ff:
        return ff
    return None


def _probe_duration_with_ffprobe(ffprobe_cmd: str, input_path: str) -> float:
    """Usa ffprobe para obtener la duración en segundos. Lanza CalledProcessError si falla."""
    # Intentar ffprobe (si ffprobe está disponible en el mismo directorio que ffmpeg, probarlo)
    ffprobe = None
    if ffprobe_cmd:
        # si recibimos ".../ffmpeg.exe" intentar reemplazar por ffprobe.exe
        base = os.path.dirname(ffprobe_cmd)
        candidate = os.path.join(base, 'ffprobe.exe' if os.name == 'nt' else 'ffprobe')
        if os.path.exists(candidate):
            ffprobe = candidate
    # si no, intentar ffprobe en PATH
    if not ffprobe:
        ffprobe = shutil.which('ffprobe')

    if ffprobe:
        # Comando que devuelve solo la duración
        cmd = [ffprobe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', input_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            out = proc.stdout.strip()
            try:
                return float(out)
            except Exception:
                raise RuntimeError(f"No se pudo parsear la duración desde ffprobe: {out}")
        else:
            raise RuntimeError(f"ffprobe falló: {proc.stderr}")

    # Si no hay ffprobe, usar ffmpeg -i y parsear stderr buscando 'Duration: HH:MM:SS.xx'
    ffmpeg = shutil.which('ffmpeg') or ffprobe_cmd
    if not ffmpeg:
        raise RuntimeError('No se encontró ffprobe ni ffmpeg para obtener la duración del archivo.')

    cmd = [ffmpeg, '-i', input_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stderr = proc.stderr
    # Buscar 'Duration: 00:05:59.15'
    import re
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.?\d*)', stderr)
    if not m:
        raise RuntimeError('No se pudo determinar la duración del vídeo a partir de ffmpeg/ffprobe.')
    h, mm, ss = m.groups()
    duration = int(h) * 3600 + int(mm) * 60 + float(ss)
    return duration


def _run_ffmpeg_segment(ffmpeg_cmd: str, input_path: str, start: float, dur: float, out_path: str) -> None:
    """Ejecuta ffmpeg para extraer un segmento. Intenta copia de streams y, si falla, recodifica.

    Si la variable de entorno PYVID_SPLIT_FORCE_PRECISE está establecida (1/true), se fuerza recodificación
    usando -i INPUT -ss START -t DUR para obtener cortes exactos (sin solapamientos), aunque más lentos.
    """
    logger = logging.getLogger(__name__)
    force_precise = os.environ.get('PYVID_SPLIT_FORCE_PRECISE', '').lower() in ('1', 'true', 'yes')

    # Si no forzamos precisión, intentar copia directa (rápido, sin recodificar)
    if not force_precise:
        # -ss antes de -i suele ser más rápido; usar -t para la duración
        copy_cmd = [ffmpeg_cmd, '-y', '-ss', str(start), '-i', input_path, '-t', str(dur), '-c', 'copy', '-avoid_negative_ts', '1', out_path]
        proc = subprocess.run(copy_cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            logger.debug("ffmpeg: used stream copy for start=%s dur=%s out=%s", start, dur, out_path)
            return
        else:
            logger.debug("ffmpeg: stream copy failed for start=%s dur=%s, will try precise recode. stderr: %s", start, dur, proc.stderr)

    # Recodificar con -i antes de -ss para cortes exactos
    recode_cmd = [ffmpeg_cmd, '-y', '-i', input_path, '-ss', str(start), '-t', str(dur), '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', out_path]
    proc2 = subprocess.run(recode_cmd, capture_output=True, text=True)
    if proc2.returncode == 0:
        logger.debug("ffmpeg: used recode precise for start=%s dur=%s out=%s", start, dur, out_path)
        return

    # Si ambos fallan, propagar error con detalles
    msg = f"ffmpeg falló al generar segmento (start={start}, dur={dur}).\nrecode stderr:\n{proc2.stderr}"
    raise RuntimeError(msg)


# Helpers para evitar acumulación de float: trabajamos en milisegundos enteros
def _seconds_to_ms(seconds: float) -> int:
    """Convierte segundos (float) a milisegundos enteros redondeando al ms más cercano."""
    return int(round(seconds * 1000.0))


def _ms_to_seconds(ms: int) -> float:
    """Convierte milisegundos enteros a segundos (float)."""
    return ms / 1000.0


def split_video(input_path: str, output_dir: str, segment_length: float) -> List[str]:
    """Divide `input_path` en fragmentos de `segment_length` segundos.
    La última parte contiene el resto si no cabe exactamente.
    Devuelve la lista de rutas de archivos escritos (MP4).

    Si moviepy está disponible se usa (recodificando con libx264/aac).
    Si no, se intentará usar ffmpeg (copiando streams si es posible, con fallback a recodificación).
    """
    if segment_length <= 0:
        raise ValueError("segment_length debe ser > 0")

    # Intentar moviepy primero
    try:
        from moviepy.editor import VideoFileClip
        have_moviepy = True
    except Exception as e:
        have_moviepy = False
        moviepy_exc = e

    os.makedirs(output_dir, exist_ok=True)
    base_name, _ = os.path.splitext(os.path.basename(input_path))
    outputs: List[str] = []

    logger = logging.getLogger(__name__)

    if have_moviepy:
        try:
            clip = VideoFileClip(input_path)
        except Exception as e:
            tb = traceback.format_exc()
            raise RuntimeError(f"Error al abrir el archivo de vídeo con moviepy:\n{tb}") from e

        try:
            duration = clip.duration
            total_ms = _seconds_to_ms(duration)
            segment_ms = _seconds_to_ms(segment_length)
            index = 0
            part_num = 1
            # Usar índices y ms enteros para evitar acumulación
            while index * segment_ms < total_ms:
                start_ms = index * segment_ms
                end_ms = min((index + 1) * segment_ms, total_ms)
                seg_dur_ms = end_ms - start_ms
                start = _ms_to_seconds(start_ms)
                end = _ms_to_seconds(end_ms)
                # Debug: imprimir tiempos en ms
                try:
                    debug = False
                    # si la función fue llamada con un kwarg debug, estará en locals() del scope superior; intenta leerlo
                    # Pero por claridad, permitimos que el caller pase debug a través de una variable global opcional `__split_debug`.
                    debug = globals().get('__split_debug', False)
                except Exception:
                    debug = False
                if debug or logger.isEnabledFor(logging.DEBUG):
                    logger.debug("[splitter][moviepy] part=%d start_ms=%d end_ms=%d dur_ms=%d", part_num, start_ms, end_ms, seg_dur_ms)

                subclip = clip.subclip(start, end)
                # Usar nombres cortos y secuenciales: VID-0001.mp4, VID-0002.mp4, ...
                out_name = f"VID-{part_num:04d}.mp4"
                out_path = os.path.join(output_dir, out_name)
                # write_videofile puede tardar; se usan valores por defecto para codec
                subclip.write_videofile(out_path, codec="libx264", audio_codec="aac", verbose=False, logger=None)
                subclip.close()
                outputs.append(out_path)
                index += 1
                part_num += 1
        finally:
            clip.close()

        # Verificación post-corte: corregir fragmentos problemáticos si es necesario
        try:
            outputs = _verify_and_fix_segments(input_path, outputs, segment_length)
        except Exception:
            # No abortar si la verificación falla; simplemente devolver los outputs generados
            logging.getLogger(__name__).exception('Error en verificación post-corte (moviepy)')

        return outputs

    # Si llegamos aquí, moviepy NO está disponible; intentar ffmpeg
    ffmpeg_exe = _find_ffmpeg_executable()
    if not ffmpeg_exe:
        tb = traceback.format_exc()
        raise RuntimeError(
            "La biblioteca 'moviepy' no está disponible o falló al importarse.\n"
            "Además no se encontró ffmpeg en el sistema.\n"
            "Instala moviepy (python -m pip install moviepy imageio-ffmpeg) o instala ffmpeg y vuelve a intentarlo.\n"
            f"Detalles original moviepy error: {moviepy_exc}\n{tb}"
        )

    # Obtener duración usando ffprobe/ffmpeg
    try:
        duration = _probe_duration_with_ffprobe(ffmpeg_exe, input_path)
    except Exception as e:
        raise RuntimeError(f"No se pudo determinar la duración del vídeo con ffmpeg/ffprobe: {e}") from e

    total_ms = _seconds_to_ms(duration)
    segment_ms = _seconds_to_ms(segment_length)
    index = 0
    part_num = 1
    try:
        while index * segment_ms < total_ms:
            start_ms = index * segment_ms
            end_ms = min((index + 1) * segment_ms, total_ms)
            seg_dur_ms = end_ms - start_ms
            # Usar nombres cortos y secuenciales: VID-0001.mp4, VID-0002.mp4, ...
            out_name = f"VID-{part_num:04d}.mp4"
            out_path = os.path.join(output_dir, out_name)
            # Debug: imprimir tiempos en ms si está activado
            try:
                debug = globals().get('__split_debug', False)
            except Exception:
                debug = False
            if debug or logger.isEnabledFor(logging.DEBUG):
                logger.debug("[splitter][ffmpeg] part=%d start_ms=%d end_ms=%d dur_ms=%d", part_num, start_ms, end_ms, seg_dur_ms)

            # Ejecutar ffmpeg para extraer segmento (pasamos segundos calculados desde ms)
            _run_ffmpeg_segment(ffmpeg_exe, input_path, _ms_to_seconds(start_ms), _ms_to_seconds(seg_dur_ms), out_path)
            outputs.append(out_path)
            index += 1
            part_num += 1
    except Exception as e:
        # Si algo falla, intentar limpiar lo ya creado
        tb = traceback.format_exc()
        # No eliminar por defecto; devolver error con la traza
        raise RuntimeError(f"Error al cortar con ffmpeg:\n{tb}") from e

    # Verificación post-corte: corregir fragmentos problemáticos si es necesario
    try:
        outputs = _verify_and_fix_segments(input_path, outputs, segment_length)
    except Exception:
        logging.getLogger(__name__).exception('Error en verificación post-corte (ffmpeg)')

    return outputs


def _get_duration_seconds(path: str) -> float:
    """Devuelve la duración en segundos del archivo `path` usando ffprobe/ffmpeg.
    Lanza RuntimeError si no es posible obtenerla."""
    ffmpeg_exe = _find_ffmpeg_executable()
    if not ffmpeg_exe:
        raise RuntimeError('No se encontró ffmpeg para obtener la duración.')
    return _probe_duration_with_ffprobe(ffmpeg_exe, path)


def _recode_precise_segment(ffmpeg_cmd: str, input_path: str, start_seconds: float, dur_seconds: float, out_path: str) -> None:
    """Recodifica desde el fichero original un segmento exacto (usando -i INPUT -ss START -t DUR).
    Reemplaza `out_path` si tiene éxito.
    """
    logger = logging.getLogger(__name__)
    # Crear archivo temporal y escribir recodificación
    tmp_out = out_path + '.recode_tmp.mp4'
    recode_cmd = [ffmpeg_cmd, '-y', '-i', input_path, '-ss', str(start_seconds), '-t', str(dur_seconds), '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', tmp_out]
    proc = subprocess.run(recode_cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        try:
            os.replace(tmp_out, out_path)
        except Exception:
            # Fallback: try remove and rename
            if os.path.exists(out_path):
                os.remove(out_path)
            os.rename(tmp_out, out_path)
        logger.debug("Recode precise succeeded for %s", out_path)
        return
    else:
        # limpiar tmp si existe
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except Exception:
                pass
        raise RuntimeError(f"ffmpeg recode falló para corregir segmento {out_path}: {proc.stderr}")


def _verify_and_fix_segments(input_path: str, outputs: List[str], segment_length: float, tolerance_ms: int = 80) -> List[str]:
    """Verifica las duraciones de `outputs` comparadas con la longitud esperada en ms (segment_length).
    Si algún fragmento excede la duración esperada por más de `tolerance_ms`, se considera "problema" y se
    reextrae ese fragmento desde el archivo original usando recodificación precisa.

    Devuelve la lista (posiblemente modificada) de paths resultantes.
    """
    logger = logging.getLogger(__name__)
    fixed = 0

    try:
        ffmpeg_exe = _find_ffmpeg_executable()
    except Exception:
        ffmpeg_exe = None

    total_ms = None
    try:
        total_ms = _seconds_to_ms(_probe_duration_with_ffprobe(ffmpeg_exe, input_path)) if ffmpeg_exe else None
    except Exception:
        total_ms = None

    expected_seg_ms = _seconds_to_ms(segment_length)

    # Iterar por cada archivo de salida y comprobar duración
    for idx, out in enumerate(outputs, start=1):
        try:
            real_s = None
            # Obtener duración del fragmento
            try:
                real_s = _probe_duration_with_ffprobe(ffmpeg_exe, out) if ffmpeg_exe else None
            except Exception:
                # Intentar con moviepy si ffmpeg no está disponible
                try:
                    from moviepy.editor import VideoFileClip
                    cl = VideoFileClip(out)
                    real_s = cl.duration
                    cl.close()
                except Exception:
                    real_s = None

            if real_s is None:
                logger.debug("No se pudo obtener duración para %s; omitiendo verificación.", out)
                continue

            real_ms = _seconds_to_ms(real_s)
            # calcular expected para este índice (la última parte puede ser más corta)
            # index base-0
            start_ms_expected = (idx - 1) * expected_seg_ms
            end_ms_expected = min(idx * expected_seg_ms, total_ms) if total_ms is not None else start_ms_expected + expected_seg_ms
            expected_ms = end_ms_expected - start_ms_expected

            # Si la duración real excede la esperada por más del umbral, corregir
            if real_ms > expected_ms + tolerance_ms:
                logger.info("Segment %d (%s) duration %dms > expected %dms (+%dms). Re-extrayendo preciso...", idx, os.path.basename(out), real_ms, expected_ms, real_ms - expected_ms)
                if not ffmpeg_exe:
                    logger.warning("No hay ffmpeg disponible para recodificar %s", out)
                    continue
                # recodificar desde el fichero original con start = start_ms_expected
                start_sec = _ms_to_seconds(start_ms_expected)
                dur_sec = _ms_to_seconds(expected_ms)
                try:
                    _recode_precise_segment(ffmpeg_exe, input_path, start_sec, dur_sec, out)
                    fixed += 1
                except Exception as e:
                    logger.error("Fallo al recodificar segmento %s: %s", out, e)
            else:
                logger.debug("Segment %d OK: real_ms=%d expected_ms=%d", idx, real_ms, expected_ms)
        except Exception as e:
            logger.exception("Error verificando segmento %s: %s", out, e)

    logger.info("Verificación completa. Fragmentos regrabados: %d", fixed)
    return outputs


# Función de diagnóstico útil para ejecutar desde la terminal
def check_moviepy() -> str:
    """Intenta importar moviepy y comprobar ffmpeg disponible.
    Devuelve una cadena con información útil o lanza una excepción con la traza.
    """
    try:
        import moviepy
        from moviepy.editor import VideoFileClip  # noqa: F401
    except Exception:
        tb = traceback.format_exc()
        info = ["IMPORT_ERROR:", tb]
        # Añadir info sobre ffmpeg
        ff = _find_ffmpeg_executable()
        if ff:
            info.append(f"ffmpeg encontrado en: {ff}")
        else:
            info.append("No se encontró ffmpeg (ni imageio-ffmpeg).")
        return "\n".join(info)

    # moviepy existe; comprobar imageio_ffmpeg/ffmpeg
    try:
        import imageio_ffmpeg as ffm
        try:
            exe = ffm.get_exe()
            ff_info = f"imageio_ffmpeg.get_exe() -> {exe}"
        except Exception:
            ff_info = f"imageio_ffmpeg presente (versión: {getattr(ffm, '__version__', 'desconocida')})"
    except Exception:
        ff = _find_ffmpeg_executable()
        ff_info = f"ffmpeg en PATH: {ff}" if ff else "No se encontró ffmpeg"

    import moviepy
    info = [f"moviepy version: {getattr(moviepy, '__version__', 'desconocida')}", f"ffmpeg info: {ff_info}"]
    return "\n".join(info)
