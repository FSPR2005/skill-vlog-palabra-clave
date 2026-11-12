"""Revisa un editado: hoja de cuadros (1 por segundo, con el segundo impreso) y ritmo de los cortes.

  python scripts/revisar.py editado.mp4 --trabajo carpeta [--cada 1.0] [--desde 0 --hasta 10]

Deja revision.jpg en la carpeta de trabajo. Míralo: la palabra va en el hueco sobre la cabeza, nunca sobre la cara.
"""
import argparse
import glob
import json
import os
import statistics
import subprocess
import sys
import tempfile


def _cortes_de_apoyos(apoyos):
    """Cada toma de apoyo es un corte al entrar; al salir también, salvo que otra empiece justo ahí."""
    ap = sorted((float(x["ini"]), float(x["fin"])) for x in apoyos)
    n = 0
    for i, (a, b) in enumerate(ap):
        n += 1
        if not (i + 1 < len(ap) and abs(ap[i + 1][0] - b) < 0.05):
            n += 1
    return n


def resumen_tramos(t, apoyos=()):
    tr = t["tramos"]
    dur = t["duracion_editada"]
    largos = [b - a for a, b in tr]
    apoyos = [x for x in apoyos if float(x["ini"]) < dur]
    cortes = max(0, len(tr) - 1) + _cortes_de_apoyos(apoyos)
    return {"cortes": cortes, "cortes_por_minuto": cortes / dur * 60 if dur else 0,
            "mediana_entre_cortes": statistics.median(largos) if largos else 0,
            "recorte": 1 - dur / t["duracion_cruda"] if t["duracion_cruda"] else 0}


def _fuente(tam):
    from PIL import ImageFont
    for f in ("C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, tam)
    return ImageFont.load_default()


def hoja_de_cuadros(video, salida, cada=1.0, desde=0.0, hasta=None, ancho=180, columnas=10):
    from PIL import Image, ImageDraw
    tmp = tempfile.mkdtemp()
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(desde), "-i", video]
    if hasta:
        cmd += ["-t", str(hasta - desde)]
    subprocess.run(cmd + ["-vf", f"fps=1/{cada},scale={ancho}:-2", os.path.join(tmp, "%04d.png")], check=True)
    fs = sorted(glob.glob(os.path.join(tmp, "*.png")))
    if not fs:
        raise RuntimeError("no salió ningún cuadro")
    w, h = Image.open(fs[0]).size
    filas = (len(fs) + columnas - 1) // columnas
    hoja = Image.new("RGB", (w * min(columnas, len(fs)), h * filas), "black")
    d = ImageDraw.Draw(hoja)
    fnt = _fuente(16)
    for i, f in enumerate(fs):
        x, y = w * (i % columnas), h * (i // columnas)
        hoja.paste(Image.open(f), (x, y))
        d.rectangle([x, y, x + 52, y + 20], fill="black")
        d.text((x + 3, y + 1), f"{desde + i * cada:.1f}s", fill="yellow", font=fnt)
        os.remove(f)
    os.rmdir(tmp)
    hoja.save(salida, quality=85)
    return salida


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--trabajo", default="trabajo-edicion")
    ap.add_argument("--cada", type=float, default=1.0)
    ap.add_argument("--desde", type=float, default=0.0)
    ap.add_argument("--hasta", type=float, default=None)
    a = ap.parse_args(argv)
    os.makedirs(a.trabajo, exist_ok=True)
    print("hoja:", hoja_de_cuadros(a.video, os.path.join(a.trabajo, "revision.jpg"), a.cada, a.desde, a.hasta))
    t = os.path.join(a.trabajo, "tramos.json")
    if os.path.exists(t):
        with open(t, encoding="utf-8") as f:
            tramos = json.load(f)
        apoyos = []
        ta = os.path.join(a.trabajo, "apoyos.json")
        if os.path.exists(ta):
            with open(ta, encoding="utf-8") as f:
                apoyos = json.load(f)
        print(json.dumps(resumen_tramos(tramos, apoyos), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
