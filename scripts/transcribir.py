"""Tiempos por palabra con faster-whisper, local y en CPU (int8). Devuelve [{"p", "ini", "fin"}]."""
import os
import subprocess
import tempfile


def transcribir(video, modelo="small", idioma=None, hilos=4, desde=None, hasta=None):
    """Con desde/hasta solo transcribe ese tramo; los tiempos salen en segundos del video completo."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise SystemExit("Falta faster-whisper: pip install faster-whisper") from e
    tmp = tempfile.mkdtemp()
    wav = os.path.join(tmp, "voz16k.wav")
    corte = (["-ss", str(desde)] if desde else []) + (["-to", str(hasta)] if hasta else [])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, *corte, "-vn", "-ac", "1", "-ar", "16000", wav],
                   check=True)
    base = float(desde or 0)
    m = WhisperModel(modelo, device="cpu", compute_type="int8", cpu_threads=hilos)
    segs, _ = m.transcribe(wav, language=idioma, word_timestamps=True, vad_filter=True)
    pal = []
    for s in segs:
        for w in s.words or []:
            pal.append({"p": w.word.strip(), "ini": round(base + w.start, 3), "fin": round(base + w.end, 3)})
    try:
        os.remove(wav)
        os.rmdir(tmp)
    except OSError:
        pass
    return pal
