"""Cortes en salto (jump cuts): qué tramos del video crudo se quedan, a partir de los tiempos por palabra.

Funciones puras, sin ffmpeg, para poder probarlas.
"""


def calcular_tramos(palabras, duracion, silencio_max=0.3, margen_antes=0.05, margen_despues=0.1):
    """Agrupa las palabras separadas por <= silencio_max y devuelve [(ini, fin)] con márgenes.

    palabras: [{"ini": s, "fin": s, ...}] en orden. Sin palabras se queda el video entero.
    """
    pal = sorted((float(w["ini"]), float(w["fin"])) for w in palabras if w["fin"] > w["ini"])
    if not pal:
        return [(0.0, round(float(duracion), 3))]
    grupos = [[pal[0][0], pal[0][1]]]
    for a, b in pal[1:]:
        if a - grupos[-1][1] <= silencio_max:
            grupos[-1][1] = max(grupos[-1][1], b)
        else:
            grupos.append([a, b])
    tramos = []
    for a, b in grupos:
        a = max(0.0, a - margen_antes)
        b = min(float(duracion), b + margen_despues)
        if tramos and a <= tramos[-1][1]:
            tramos[-1] = (tramos[-1][0], max(tramos[-1][1], b))
        else:
            tramos.append((a, b))
    return [(round(a, 3), round(b, 3)) for a, b in tramos]


def ajustar_a_cuadros(tramos, fps):
    """Lleva cada borde a la rejilla de cuadros (k/fps) para que audio y video corten igual y no se desfasen."""
    out = []
    for a, b in tramos:
        ka, kb = int(round(a * fps)), int(round(b * fps))
        if out and ka < out[-1][1]:
            ka = out[-1][1]
        if kb <= ka:
            kb = ka + 1
        if out and ka == out[-1][1]:
            out[-1] = (out[-1][0], kb)
        else:
            out.append((ka, kb))
    return [(ka / fps, kb / fps) for ka, kb in out]


def duracion_total(tramos):
    return sum(b - a for a, b in tramos)


def mapear_tiempo(t, tramos):
    """Segundo del video crudo -> segundo del video editado. En un hueco, se pega al siguiente tramo."""
    acum = 0.0
    for a, b in tramos:
        if t < a:
            return acum
        if t <= b:
            return acum + (t - a)
        acum += b - a
    return acum
