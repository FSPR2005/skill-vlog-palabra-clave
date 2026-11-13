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


def agrupar_frases(palabras, max_palabras=4, pausa=0.35, unidas=frozenset()):
    """unidas: id() de palabras que no se separan de la anterior (una secuencia resaltada no se parte)."""
    frases, actual = [], []
    for i, w in enumerate(palabras):
        if actual and id(w) not in unidas and (w["ini"] - actual[-1]["fin"] > pausa or len(actual) >= max_palabras):
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


def _secuencia(texto):
    return [x for x in (_limpia(t) for t in str(texto).split()) if x]


def indices_resaltados(palabras, resaltar):
    """Índices de las palabras a resaltar. resaltar: ["palabra", "varias palabras", {"texto", "ini", "fin"}].

    Una entrada de varias palabras solo coincide con esas palabras seguidas (así "a" no se resalta suelta); ini/fin
    (segundos del video editado) limitan dónde vale. Se compara sin signos ni mayúsculas.
    """
    return {i for m in coincidencias_resaltadas(palabras, resaltar) for i in m}


def coincidencias_resaltadas(palabras, resaltar):
    """[[índices de una coincidencia], ...] (ver indices_resaltados)."""
    limpias = [(i, _limpia(w["p"])) for i, w in enumerate(palabras)]
    limpias = [(i, p) for i, p in limpias if p]
    out = []
    for r in resaltar or ():
        if isinstance(r, dict):
            sec, ini, fin = _secuencia(r.get("texto", "")), r.get("ini"), r.get("fin")
        else:
            sec, ini, fin = _secuencia(r), None, None
        n = len(sec)
        if not n:
            continue
        for k in range(len(limpias) - n + 1):
            if [p for _, p in limpias[k:k + n]] == sec:
                idx = [i for i, _ in limpias[k:k + n]]
                t = palabras[idx[0]]["ini"]
                if (ini is None or t >= ini) and (fin is None or t < fin):
                    out.append(idx)
    return out


def _fraccion_ascendente(fuente):
    ancho_texto("a", fuente, 10)  # llena la caché
    c = _cache.get(fuente)
    if not c:
        return 0.75
    a, d = c[0].getmetrics()
    return a / (a + d)


def maquetar_frase(frase, i_clave, est, variante=0, x0=None, y0=None, resaltadas=()):
    """Devuelve [{texto, x, y, estilo}] con \\an7 (esquina superior izquierda) en un lienzo 1080x1920.

    resaltadas: índices (dentro de la frase) que van con el estilo Resaltado, en su mismo renglón.
    """
    W, H = 1080, 1920
    f = est["subtitulos"]["frases"]
    min_ = est["subtitulos"]["minusculas"]
    from textos import limpiar_palabra
    x0 = int(W * f["posicion_x"]) if x0 is None else x0
    y0 = int(H * f["posicion_y"]) if y0 is None else y0
    clave = f["claves"][variante % len(f["claves"])] if f["claves"] else None
    r = est["subtitulos"]["resaltado"]
    lineas, actual = [], []
    for i, w in enumerate(frase):
        t = limpiar_palabra(w["p"], min_)
        if not t:
            continue
        if i == i_clave and clave:
            if actual:
                lineas.append(("chica", actual))
                actual = []
            lineas.append(("clave", [(t, "clave")]))
        elif i in resaltadas:
            actual.append((limpiar_palabra(w["p"], False).upper() if r["mayusculas"] else t, "res"))
        else:
            actual.append((t, "chica"))
    if actual:
        lineas.append(("chica", actual))

    def letra(tipo):
        if tipo == "clave":
            return clave["fuente"], clave["tamano"]
        if tipo == "res":
            return r["fuente"], r["tamano"]
        return f["fuente"], f["tamano"]

    out = []
    x, y = x0, y0
    ancho_prev = 0
    esp = ancho_texto(" ", f["fuente"], f["tamano"])
    margen = int(W * (1 - f["ancho_max"]) / 2)
    for n, (tipo, palabras) in enumerate(lineas):
        ancho = sum(ancho_texto(p, *letra(tp)) for p, tp in palabras) + esp * (len(palabras) - 1)
        tam = max(letra(tp)[1] for _, tp in palabras)
        # si la línea no cabe entre los márgenes se encoge (fscx/fscy) en vez de salirse
        escala = min(100, int(100 * (W - 2 * margen) / ancho)) if ancho else 100
        ancho = ancho * escala / 100
        if n:
            x = int(x + f["escalon"] * ancho_prev)
        x = max(margen, min(x, W - margen - int(ancho)))
        xx = x
        for p, tp in palabras:
            fuente, tam_p = letra(tp)
            # misma línea base aunque el resaltado sea de otro tamaño
            dy = (tam - tam_p) * _fraccion_ascendente(fuente) * escala / 100
            out.append({"texto": p, "x": int(xx), "y": int(y + dy), "escala": escala,
                        "estilo": ("Clave%d" % (variante % len(f["claves"])) if tp == "clave" else
                                   "Resaltado" if tp == "res" else "Frase")})
            xx += (ancho_texto(p, fuente, tam_p) + esp) * escala / 100
        y += int(tam * f["interlineado"] * (clave.get("alto_linea", 1.0) if tipo == "clave" else 1.0))
        ancho_prev = ancho
    return out


def eventos_frases(palabras, est, claves=None, posiciones=(), resaltar=()):
    """[{texto, x, y, estilo, ini, fin}]: cada palabra entra en su segundo y sale al final de su frase.

    Una frase con palabras resaltadas no lleva clave pastel: el resaltado ya es su énfasis.
    """
    f = est["subtitulos"]["frases"]
    hueco = est["subtitulos"]["hueco_max"]
    coinc = coincidencias_resaltadas(palabras, resaltar)
    res_ids = {id(palabras[i]) for m in coinc for i in m}
    unidas = {id(palabras[i]) for m in coinc for i in range(m[0] + 1, m[-1] + 1)}
    frases = agrupar_frases(palabras, f["max_palabras"], f["pausa"], unidas)
    ev = []
    variante = 0
    for k, fr in enumerate(frases):
        fin = fr[-1]["fin"] + hueco
        if k + 1 < len(frases):
            fin = min(fin, frases[k + 1][0]["ini"])
        loc = {j for j, w in enumerate(fr) if id(w) in res_ids}
        ic = None if loc else elegir_clave(fr, claves)
        x0 = y0 = None
        for pos in posiciones:
            if pos["ini"] <= fr[0]["ini"] < pos["fin"]:
                x0, y0 = int(1080 * pos["x"]), int(1920 * pos["y"])
        caja = maquetar_frase(fr, ic, est, variante, x0, y0, loc)
        visibles = [w for w in fr if _limpia(w["p"])]
        for w, c in zip(visibles, caja):
            if fin - w["ini"] > 0.01:
                ev.append(dict(c, ini=round(w["ini"], 3), fin=round(fin, 3)))
        if ic is not None:
            variante += 1
    return ev
