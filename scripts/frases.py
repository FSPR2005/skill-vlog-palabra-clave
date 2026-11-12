"""Subtítulo por frase que se va armando palabra por palabra.

Cada palabra aparece (sin fundido) en el segundo en que se dice y se queda hasta que termina la frase; entonces se
borra todo y empieza la siguiente. Las palabras chicas van en una línea; la palabra clave va sola en su línea, más
grande y en color pastel; las líneas bajan en escalera (cada una empieza un poco más a la derecha).
"""
import os

from estilo import RAIZ

ARCHIVOS = {
    "Poppins SemiBold": "Poppins-SemiBold.ttf",
    "Poppins ExtraBold": "Poppins-ExtraBold.ttf",
    "Great Vibes": "GreatVibes-Regular.ttf",
    "Gochi Hand": "GochiHand-Regular.ttf",
}
MULETILLAS = {
    "a", "al", "ante", "con", "de", "del", "el", "en", "es", "la", "las", "lo", "los", "me", "mi", "mis", "no", "o",
    "para", "pero", "por", "que", "se", "si", "sí", "su", "sus", "te", "tu", "tus", "un", "una", "y", "ya", "yo",
    "este", "esta", "eso", "esto", "como", "más", "muy", "pues", "bueno", "entonces", "osea", "o sea", "porque",
    "the", "and", "to", "of", "is", "it", "in", "my", "you", "i", "so", "but", "that", "this",
}
_cache = {}


def ancho_texto(texto, fuente, tamano):
    """Ancho en px de lienzo 1080 tal como lo dibuja libass (su tamaño = alto ascendente+descendente)."""
    ruta = os.path.join(RAIZ, "fuentes", ARCHIVOS.get(fuente, ""))
    if fuente not in _cache:
        try:
            from PIL import ImageFont
            f = ImageFont.truetype(ruta, 200)
            a, d = f.getmetrics()
            _cache[fuente] = (f, 200 / (a + d))
        except Exception:
            _cache[fuente] = None
    c = _cache[fuente]
    if c is None:
        return 0.55 * tamano * len(texto)
    f, k = c
    return f.getlength(texto) / 200 * tamano * k


def agrupar_frases(palabras, max_palabras=4, pausa=0.35):
    frases, actual = [], []
    for i, w in enumerate(palabras):
        if actual and (w["ini"] - actual[-1]["fin"] > pausa or len(actual) >= max_palabras):
            frases.append(actual)
            actual = []
        actual.append(w)
        if w["p"].rstrip().endswith((".", "?", "!", "…", ",")):
            frases.append(actual)
            actual = []
    if actual:
        frases.append(actual)
    return frases


def _limpia(p):
    from textos import limpiar_palabra
    return limpiar_palabra(p, True)


def elegir_clave(frase, claves=None):
    """Índice de la palabra clave de la frase, o None. Con lista, solo las de la lista."""
    if claves is not None:
        cl = {_limpia(c) for c in claves}
        for i, w in enumerate(frase):
            if _limpia(w["p"]) in cl:
                return i
        return None
    mejor, largo = None, 3
    for i, w in enumerate(frase):
        p = _limpia(w["p"])
        if p in MULETILLAS:
            continue
        if len(p) > largo:
            mejor, largo = i, len(p)
    return mejor


def maquetar_frase(frase, i_clave, est, variante=0, x0=None, y0=None):
    """Devuelve [{texto, x, y, estilo}] con \\an7 (esquina superior izquierda) en un lienzo 1080x1920."""
    W, H = 1080, 1920
    f = est["subtitulos"]["frases"]
    min_ = est["subtitulos"]["minusculas"]
    from textos import limpiar_palabra
    x0 = int(W * f["posicion_x"]) if x0 is None else x0
    y0 = int(H * f["posicion_y"]) if y0 is None else y0
    clave = f["claves"][variante % len(f["claves"])] if f["claves"] else None
    lineas, actual = [], []
    for i, w in enumerate(frase):
        t = limpiar_palabra(w["p"], min_)
        if not t:
            continue
        if i == i_clave and clave:
            if actual:
                lineas.append(("chica", actual))
                actual = []
            lineas.append(("clave", [t]))
        else:
            actual.append(t)
    if actual:
        lineas.append(("chica", actual))
    out = []
    x, y = x0, y0
    ancho_prev = 0
    esp = ancho_texto(" ", f["fuente"], f["tamano"])
    margen = int(W * (1 - f["ancho_max"]) / 2)
    for n, (tipo, palabras) in enumerate(lineas):
        fuente, tam = (clave["fuente"], clave["tamano"]) if tipo == "clave" else (f["fuente"], f["tamano"])
        ancho = sum(ancho_texto(p, fuente, tam) for p in palabras) + esp * (len(palabras) - 1)
        # si la línea no cabe entre los márgenes se encoge (fscx/fscy) en vez de salirse
        escala = min(100, int(100 * (W - 2 * margen) / ancho)) if ancho else 100
        ancho = ancho * escala / 100
        if n:
            x = int(x + f["escalon"] * ancho_prev)
        x = max(margen, min(x, W - margen - int(ancho)))
        xx = x
        for p in palabras:
            out.append({"texto": p, "x": int(xx), "y": int(y), "escala": escala,
                        "estilo": "Clave%d" % (variante % len(f["claves"])) if tipo == "clave" else "Frase"})
            xx += (ancho_texto(p, fuente, tam) + esp) * escala / 100
        y += int(tam * f["interlineado"] * (clave.get("alto_linea", 1.0) if tipo == "clave" else 1.0))
        ancho_prev = ancho
    return out


def eventos_frases(palabras, est, claves=None, posiciones=()):
    """[{texto, x, y, estilo, ini, fin}]: cada palabra entra en su segundo y sale al final de su frase."""
    f = est["subtitulos"]["frases"]
    hueco = est["subtitulos"]["hueco_max"]
    frases = agrupar_frases(palabras, f["max_palabras"], f["pausa"])
    ev = []
    variante = 0
    for k, fr in enumerate(frases):
        fin = fr[-1]["fin"] + hueco
        if k + 1 < len(frases):
            fin = min(fin, frases[k + 1][0]["ini"])
        ic = elegir_clave(fr, claves)
        x0 = y0 = None
        for pos in posiciones:
            if pos["ini"] <= fr[0]["ini"] < pos["fin"]:
                x0, y0 = int(1080 * pos["x"]), int(1920 * pos["y"])
        caja = maquetar_frase(fr, ic, est, variante, x0, y0)
        visibles = [w for w in fr if _limpia(w["p"])]
        for w, c in zip(visibles, caja):
            if fin - w["ini"] > 0.01:
                ev.append(dict(c, ini=round(w["ini"], 3), fin=round(fin, 3)))
        if ic is not None:
            variante += 1
    return ev
