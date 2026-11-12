"""Edita un video crudo con el estilo de estilo.json.

  python scripts/editar.py comprobar
  python scripts/editar.py preparar crudo.mp4 --trabajo carpeta          # transcribe, calcula cortes y escribe guion.txt
  python scripts/editar.py render   crudo.mp4 --salida editado.mp4 --trabajo carpeta [--textos textos.json]
                                    [--musica pista.mp3] [--estilo mio.json] [--sin-cortes] [--palabras p.json]
                                    [--modelo small] [--idioma es] [--desde S --hasta S]

guion.txt y textos.json usan la línea de tiempo del video YA editado (después de los cortes). textos.json:
  {"titulos": [{"chico", "grande", "ini", "fin"}], "notas": [{"texto", "ini", "fin", "posicion_x", "posicion_y"}],
   "claves": ["palabra", ...], "palabra_suelta": [[ini, fin]], "posiciones": [{"ini", "fin", "x", "y"}],
   "apoyos": [{"archivo", "desde", "ini", "fin"}]}
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from cortes import calcular_tramos, ajustar_a_cuadros, mapear_tiempo, duracion_total  # noqa: E402
from estilo import cargar_estilo, RAIZ  # noqa: E402
from render import filtro_video, filtro_audio  # noqa: E402
from textos import generar_ass  # noqa: E402

FUENTES = os.path.join(RAIZ, "fuentes")


def _probar(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                        "-of", "json", video], capture_output=True, text=True, check=True)
    info = json.loads(r.stdout)
    return float(info["format"]["duration"]), any(s["codec_type"] == "audio" for s in info["streams"])


def _es_hdr(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer",
                        "-of", "csv=p=0", video], capture_output=True, text=True)
    if r.stdout.strip() not in ("arib-std-b67", "smpte2084"):
        return False
    filtros = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    if " zscale " not in filtros:
        print("AVISO: el video es HDR y tu ffmpeg no trae zscale; los colores pueden salir lavados")
        return False
    return True


def _version_ffmpeg():
    import re
    r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    m = re.search(r"ffmpeg version n?(\d+)", r.stdout)
    return int(m.group(1)) if m else 7


def _grafo_desde_archivo(nombre):
    """El grafo va en un archivo (sin límite de largo de la línea de comando). ffmpeg 7+ usa -/filter_complex."""
    return ["-/filter_complex", nombre] if _version_ffmpeg() >= 7 else ["-filter_complex_script", nombre]


def comprobar():
    ok = True
    for prog in ("ffmpeg", "ffprobe"):
        if not shutil.which(prog):
            print(f"FALTA {prog}: instálalo (Windows: winget install Gyan.FFmpeg; Mac: brew install ffmpeg)")
            ok = False
    if shutil.which("ffmpeg"):
        filtros = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        if " ass " not in filtros:
            print("FALTA libass en tu ffmpeg (filtro 'ass'): usa una compilación completa")
            ok = False
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        print("FALTA faster-whisper: pip install faster-whisper (solo si no pasas --palabras)")
        ok = False
    for f in ("Poppins-SemiBold.ttf", "Poppins-ExtraBold.ttf", "GreatVibes-Regular.ttf", "GochiHand-Regular.ttf"):
        if not os.path.exists(os.path.join(FUENTES, f)):
            print(f"FALTA la fuente {f} en {FUENTES}")
            ok = False
    print("todo listo" if ok else "faltan cosas (arriba)")
    return 0 if ok else 1


def _palabras(a, trabajo):
    if a.palabras:
        with open(a.palabras, encoding="utf-8") as f:
            return json.load(f)
    nombre = "palabras.json" if a.desde is None and a.hasta is None else f"palabras_{a.desde or 0:g}-{a.hasta or 'fin'}.json"
    cache = os.path.join(trabajo, nombre)
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    from transcribir import transcribir
    pal = transcribir(a.video, a.modelo, a.idioma, a.hilos, a.desde, a.hasta)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(pal, f, ensure_ascii=False, indent=0)
    return pal


def _guion(pal_ed, ruta):
    """Frases (cortadas en pausas o puntuación) con su segundo en el video editado, para escribir textos.json."""
    lineas, actual = [], []
    for i, w in enumerate(pal_ed):
        actual.append(w)
        fin_frase = w["p"].rstrip().endswith((".", "?", "!", "…"))
        pausa = i + 1 < len(pal_ed) and pal_ed[i + 1]["ini"] - w["fin"] > 0.25
        if fin_frase or pausa or i == len(pal_ed) - 1:
            lineas.append(f"{actual[0]['ini']:7.2f} - {actual[-1]['fin']:7.2f}  " + " ".join(x["p"] for x in actual))
            actual = []
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")


def preparar(a, est):
    trabajo = os.path.abspath(a.trabajo)
    os.makedirs(trabajo, exist_ok=True)
    dur, hay_audio = _probar(a.video)
    pal = _palabras(a, trabajo) if hay_audio else []
    fps = est["salida"]["fps"]
    desde, hasta = a.desde or 0.0, a.hasta or dur
    pal = [w for w in pal if w["ini"] >= desde and w["fin"] <= hasta]
    if est["cortes"]["activar"] and not a.sin_cortes and pal:
        c = est["cortes"]
        tramos = calcular_tramos(pal, hasta, c["silencio_max"], c["margen_antes"], c["margen_despues"])
        tramos = [(max(x, desde), y) for x, y in tramos if y > desde]
    else:
        tramos = [(desde, hasta)]
    tramos = ajustar_a_cuadros(tramos, fps)
    pal_ed = [dict(w, ini=round(mapear_tiempo(w["ini"], tramos), 3), fin=round(mapear_tiempo(w["fin"], tramos), 3))
              for w in pal]
    with open(os.path.join(trabajo, "tramos.json"), "w", encoding="utf-8") as f:
        json.dump({"duracion_cruda": dur, "duracion_editada": round(duracion_total(tramos), 3), "tramos": tramos}, f,
                  indent=0)
    with open(os.path.join(trabajo, "palabras_editado.json"), "w", encoding="utf-8") as f:
        json.dump(pal_ed, f, ensure_ascii=False, indent=0)
    _guion(pal_ed, os.path.join(trabajo, "guion.txt"))
    print(f"crudo {dur:.1f} s -> editado {duracion_total(tramos):.1f} s en {len(tramos)} tramos; "
          f"guion en {os.path.join(trabajo, 'guion.txt')}")
    return trabajo, tramos, pal_ed, hay_audio, dur


def render(a, est):
    trabajo, tramos, pal_ed, hay_audio, dur = preparar(a, est)
    textos = {"titulos": [], "notas": []}
    if a.textos:
        with open(a.textos, encoding="utf-8") as f:
            textos.update(json.load(f))
    # fuentes y .ass junto al trabajo: el filtro ass de ffmpeg no acepta rutas C:\... (se corre con cwd=trabajo)
    dest_f = os.path.join(trabajo, "fuentes")
    os.makedirs(dest_f, exist_ok=True)
    for f in os.listdir(FUENTES):
        if f.lower().endswith((".ttf", ".otf")):
            shutil.copy2(os.path.join(FUENTES, f), dest_f)
    with open(os.path.join(trabajo, "textos.ass"), "w", encoding="utf-8") as f:
        f.write(generar_ass(pal_ed, est, textos.get("titulos", []), textos.get("notas", []), textos.get("claves"),
                            textos.get("palabra_suelta", []), textos.get("posiciones", [])))
    entero = len(tramos) == 1 and tramos[0][0] == 0 and abs(tramos[0][1] - dur) < 1 / est['salida']['fps']
    usar_tramos = None if entero else tramos
    s = est["salida"]
    entradas = ["-i", os.path.abspath(a.video)]
    if a.musica:
        entradas += ["-stream_loop", "-1", "-i", os.path.abspath(a.musica)]
    # tomas de apoyo: tapan la imagen en [ini, fin] del video editado; la voz sigue
    apoyos = []
    base_txt = os.path.dirname(os.path.abspath(a.textos)) if a.textos else os.getcwd()
    for k, ap_ in enumerate(textos.get("apoyos", [])):
        ruta = ap_["archivo"]
        if not os.path.isabs(ruta) and not os.path.exists(ruta):
            ruta = os.path.join(base_txt, ruta)  # relativa a la carpeta de textos.json
        if not os.path.exists(ruta):
            raise SystemExit(f"no existe la toma de apoyo: {ruta}")
        largo = float(ap_["fin"]) - float(ap_["ini"])
        entradas += ["-ss", str(float(ap_.get("desde", 0))), "-t", f"{largo + 0.1:.3f}", "-an", "-i", ruta]
        apoyos.append((1 + bool(a.musica) + k, float(ap_["ini"]), float(ap_["fin"])))
    color_filtro = None
    if est["color"]["activar"] and est["color"]["modo"] == "auto":
        from color import medir_color, ajuste_color
        medido = medir_color(os.path.abspath(a.video), 8, tramos[0][0], tramos[-1][1])
        color_filtro = ajuste_color(medido, est["color"]["objetivo"])
        with open(os.path.join(trabajo, "color.json"), "w", encoding="utf-8") as f:
            json.dump({"medido": medido, "objetivo": est["color"]["objetivo"], "filtro": color_filtro}, f, indent=1)
    with open(os.path.join(trabajo, "apoyos.json"), "w", encoding="utf-8") as f:
        json.dump(textos.get("apoyos", []), f, ensure_ascii=False, indent=0)
    hdr = _es_hdr(a.video)
    if hdr:
        print("video HDR: se convierte a SDR (BT.709) con zscale + tonemap")
    fv = filtro_video(est, usar_tramos, "textos.ass", "fuentes", apoyos, color_filtro, hdr)
    if hay_audio:
        fa = filtro_audio(est, usar_tramos, hay_musica=bool(a.musica))
    else:
        fa = (f"anullsrc=r=48000:cl=mono,atrim=0:{duracion_total(tramos):.3f}[aout]" if not a.musica else
              f"[1:a]aresample=48000,volume={est['audio']['musica_db']}dB,atrim=0:{duracion_total(tramos):.3f}[aout]")
    grafo = fv + ";" + fa
    with open(os.path.join(trabajo, "filtro.txt"), "w", encoding="utf-8") as f:
        f.write(grafo)
    salida = os.path.abspath(a.salida)
    cmd = ["ffmpeg", "-v", "error", "-stats", "-y", *entradas, *_grafo_desde_archivo("filtro.txt"),
           "-map", "[vout]", "-map", "[aout]",
           "-c:v", "libx264", "-preset", s["preset"], "-crf", str(s["crf"]), "-x264-params", "rc-lookahead=10",
           "-threads", str(a.hilos), "-c:a", "aac", "-b:a", f"{s['audio_kbps']}k", "-shortest",
           "-movflags", "+faststart", salida]
    r = subprocess.run(cmd, cwd=trabajo)
    if r.returncode == 0:
        print("listo:", salida)
    return r.returncode


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", choices=["comprobar", "preparar", "render"])
    ap.add_argument("video", nargs="?")
    ap.add_argument("--salida", default="editado.mp4")
    ap.add_argument("--trabajo", default="trabajo-edicion")
    ap.add_argument("--estilo", default=None, help="json con las claves que cambian respecto a estilo.json")
    ap.add_argument("--textos", default=None, help="json con titulos y notas (tiempos del video editado)")
    ap.add_argument("--musica", default=None, help="pista propia o con licencia; se repite y se baja bajo la voz")
    ap.add_argument("--palabras", default=None, help="json [{p, ini, fin}] para no transcribir")
    ap.add_argument("--sin-cortes", action="store_true")
    ap.add_argument("--modelo", default="small")
    ap.add_argument("--idioma", default=None, help="es, en... (vacío = detecta)")
    ap.add_argument("--desde", type=float, default=None)
    ap.add_argument("--hasta", type=float, default=None)
    ap.add_argument("--hilos", type=int, default=4)
    a = ap.parse_args(argv)
    if a.accion == "comprobar":
        return comprobar()
    if not a.video or not os.path.exists(a.video):
        ap.error("falta el video crudo (o no existe)")
    est = cargar_estilo(a.estilo)
    if a.accion == "preparar":
        preparar(a, est)
        return 0
    return render(a, est)


if __name__ == "__main__":
    sys.exit(main())
