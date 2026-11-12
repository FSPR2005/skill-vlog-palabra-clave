"""Color automático: mide el video del usuario y lo lleva a las métricas del estilo (no aplica un LUT ajeno).

Métricas (0-255): luma media, saturación media (HSV), negro (percentil 2), blanco (percentil 98) y calidez
(rojo medio - azul medio). El estilo pide blancos suaves (~222, sin quemar), saturación baja y un poco de calidez.
"""
import math
import os
import subprocess
import tempfile


def medir_color(video, muestras=8, desde=0.0, hasta=None):
    import numpy as np
    from PIL import Image
    if hasta is None:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                           capture_output=True, text=True, check=True)
        hasta = float(r.stdout.strip())
    tmp = tempfile.mkdtemp()
    vals = {"luma": [], "saturacion": [], "negro": [], "blanco": [], "calidez": []}
    for i in range(muestras):
        t = desde + (hasta - desde) * (i + 0.5) / muestras
        png = os.path.join(tmp, f"{i}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
                        "-vf", "scale=180:-2", png], check=False)
        if not os.path.exists(png):
            continue
        im = Image.open(png).convert("RGB")
        a = np.asarray(im).astype(float)
        y = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
        s = np.asarray(im.convert("HSV")).astype(float)[..., 1]
        vals["luma"].append(y.mean())
        vals["saturacion"].append(s.mean())
        vals["negro"].append(np.percentile(y, 2))
        vals["blanco"].append(np.percentile(y, 98))
        vals["calidez"].append(a[..., 0].mean() - a[..., 2].mean())
        os.remove(png)
    try:
        os.rmdir(tmp)
    except OSError:
        pass
    if not vals["luma"]:
        raise RuntimeError("no se pudo leer ningún cuadro para medir el color")
    return {k: float(np.median(v)) for k, v in vals.items()}


def _tope(x, a, b):
    return max(a, min(b, x))


def ajuste_color(medido, objetivo):
    """Cadena de filtros ffmpeg: colorlevels (negro/blanco) + eq (gamma, saturación) + colorbalance (calidez)."""
    n_in, b_in = medido["negro"] / 255, max(medido["blanco"], medido["negro"] + 20) / 255
    n_out, b_out = objetivo["negro"] / 255, objetivo["blanco"] / 255
    # luma esperada después de los niveles
    m = (medido["luma"] / 255 - n_in) / (b_in - n_in)
    m = _tope(n_out + m * (b_out - n_out), 0.02, 0.98)
    t = _tope(objetivo["luma"] / 255, 0.02, 0.98)
    gamma = _tope(math.log(m) / math.log(t), 0.75, 1.35)
    sat = _tope(objetivo["saturacion"] / max(medido["saturacion"], 1.0), 0.6, 1.4)
    calor = _tope((objetivo["calidez"] - medido["calidez"]) / 255 * 1.5, -0.12, 0.12)
    lv = ":".join(f"{c}imin={n_in:.4f}:{c}imax={b_in:.4f}:{c}omin={n_out:.4f}:{c}omax={b_out:.4f}" for c in "rgb")
    return (f"colorlevels={lv},eq=gamma={gamma:.3f}:saturation={sat:.3f},"
            f"colorbalance=rm={calor:.3f}:bm={-calor:.3f}")
