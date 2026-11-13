"""Modo antes-despues: el mismo clip se ve crudo y se va editando por capas, con una barra de capas de colores.

El video editado va en una tarjeta con esquinas redondeadas sobre un fondo claro, con un título arriba. Abajo corre
una línea de tiempo de bloques de colores (una capa por bloque: Original, Subtítulos, Zoom, Gráficos, Música y SFX)
bajo un cabezal fijo; cada capa se prende en el segundo en que el cabezal entra en su bloque. Los bloques que faltan
se ven tenues y se llenan al prenderse.

Cada capa prende uno o varios tipos de edición:
  subtitulos  eventos Palabra/Frase/Clave/Resaltado del .ass
  color       el filtro de color (auto o fijo), con enable='gte(t,ini)'
  zoom        zoom en salto entre cortes (intervalos_zoom), desde su segundo
  graficos    títulos y notas del .ass, y tomas de apoyo
  musica      la pista de --musica (antes de su segundo va en silencio)
Un tipo que no está en ninguna capa no sale. Todo el texto del marco es un .ass (lienzo 1080x1920).
"""
import re

from textos import tiempo_ass, color_ass, _escapar

TIPOS = ("subtitulos", "color", "zoom", "graficos", "musica")
_CATEGORIA = (("Palabra", "subtitulos"), ("Frase", "subtitulos"), ("Clave", "subtitulos"),
              ("Resaltado", "subtitulos"), ("Titulo", "graficos"), ("Nota", "graficos"))


def capas_con_material(capas, disponibles):
    """Quita las capas que no tienen nada que prender (p. ej. Música sin --musica). Devuelve (capas, nombres_fuera)."""
    dentro, fuera = [], []
    for c in capas:
        for t in c.get("tipos", []):
            if t not in TIPOS:
                raise ValueError(f"antes_despues.capas: tipo desconocido «{t}» (usa {', '.join(TIPOS)})")
        if not c.get("tipos") or any(t in disponibles for t in c["tipos"]):
            dentro.append(c)
        else:
            fuera.append(c["nombre"])
    return dentro, fuera


def tiempos_capas(capas, dur):
    """Agrega ini y fin (segundos del video editado). Sin ini en ninguna: reparto parejo."""
    if not capas:
        raise ValueError("antes_despues.capas está vacío")
    con = ["ini" in c for c in capas]
    if any(con) and not all(con):
        raise ValueError("antes_despues.capas: o todas llevan ini o ninguna")
    if all(con):
        inis = [float(c["ini"]) for c in capas]
        if inis[0] != 0 or any(b <= a for a, b in zip(inis, inis[1:])) or inis[-1] >= dur:
            raise ValueError("antes_despues.capas: los ini empiezan en 0, crecen y quedan antes del final")
    else:
        inis = [round(dur * i / len(capas), 4) for i in range(len(capas))]
    fines = inis[1:] + [dur]
    return [dict(c, ini=a, fin=b) for c, a, b in zip(capas, inis, fines)]


def inicios_por_tipo(capas_t):
    ini = {}
    for c in capas_t:
        for t in c.get("tipos", []):
            ini.setdefault(t, c["ini"])
    return ini


def _seg(txt):
    h, m, s = txt.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _categoria(estilo):
    for pref, cat in _CATEGORIA:
        if estilo.startswith(pref):
            return cat
    return None


_T = re.compile(r"\\t\((-?\d+),(-?\d+),((?:[^()]|\([^()]*\))*)\)")
_FAD = re.compile(r"\\fad\((\d+),(\d+)\)")
_MOVE = re.compile(r"\\move\((-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\)")


def _correr_animaciones(texto, off_ms, dur_ms):
    """El evento ahora empieza off_ms más tarde y dura dur_ms - off_ms: cada animación sigue donde iba.

    \\fad y \\t pasan a tiempos relativos al nuevo inicio, que pueden ser negativos (libass los acepta: medido,
    \\fscx50\\t(-500,500,\\fscx100) en el cuadro 0 dibuja la escala 75; \\fade con t1 negativo, la opacidad intermedia).
    """
    def fad(m):
        a, b = int(m.group(1)), int(m.group(2))
        return f"\\fade(255,0,255,{-off_ms},{a - off_ms},{dur_ms - b - off_ms},{dur_ms - off_ms})"
    texto = _FAD.sub(fad, texto)

    def t(m):
        t1, t2, mods = int(m.group(1)) - off_ms, int(m.group(2)) - off_ms, m.group(3)
        if t2 <= 0:
            return mods  # ya terminó: su estado final, en el acto
        return f"\\t({t1},{t2},{mods})"
    texto = _T.sub(t, texto)

    def mv(m):
        x1, y1, x2, y2 = (float(g) for g in m.groups())
        k = min(1.0, off_ms / dur_ms) if dur_ms > 0 else 1.0
        return f"\\move({_num(x1 + (x2 - x1) * k)},{_num(y1 + (y2 - y1) * k)},{_num(x2)},{_num(y2)})"
    return _MOVE.sub(mv, texto)


def recortar_ass(texto, inicios):
    """Cada evento de subtítulos o gráficos empieza en el segundo de su capa (o se quita si su capa no está)."""
    out = []
    for linea in texto.splitlines():
        if not linea.startswith("Dialogue:"):
            out.append(linea)
            continue
        p = linea.split(",", 9)
        cat = _categoria(p[3])
        if cat is None:
            out.append(linea)
            continue
        t0 = inicios.get(cat)
        ini, fin = _seg(p[1]), _seg(p[2])
        if t0 is None or fin <= t0 + 0.005:
            continue
        if ini < t0:
            p[1] = tiempo_ass(t0)
            p[9] = _correr_animaciones(p[9], int(round((t0 - ini) * 1000)), int(round((fin - ini) * 1000)))
        out.append(",".join(p))
    return "\n".join(out) + "\n"


def con_enable(cadena, t0):
    """Prende cada filtro de una cadena (sin comas anidadas) desde el segundo t0."""
    partes = []
    for f in cadena.split(","):
        partes.append(f + (":" if "=" in f else "=") + f"enable='gte(t,{t0:.4f})'")
    return ",".join(partes)


def cortes_editados(tramos):
    """Segundos del video editado donde cae un corte (fronteras entre tramos)."""
    cortes, acc = [], 0.0
    for a, b in tramos[:-1]:
        acc += b - a
        cortes.append(round(acc, 4))
    return cortes


def intervalos_zoom(cortes, dur, periodo, desde=0.0):
    """Tramos con zoom: uno sí y otro no entre cortes; los que pasan de 2 periodos se parten en trozos de ~periodo."""
    puntos = [0.0] + sorted(c for c in cortes if 0 < c < dur) + [dur]
    trozos = []
    for a, b in zip(puntos, puntos[1:]):
        n = int(round((b - a) / periodo)) if periodo and b - a > 2 * periodo else 1
        for k in range(n):
            trozos.append((a + (b - a) * k / n, a + (b - a) * (k + 1) / n))
    out = []
    for i, (a, b) in enumerate(trozos):
        if i % 2 == 1 and b > desde:
            out.append((round(max(a, desde), 4), round(b, 4)))
    return out


def geometria(est):
    """Tarjeta del video en píxeles de la salida: ancho y alto pares, centrada a lo ancho."""
    s, ad = est["salida"], est["antes_despues"]
    W, H = s["ancho"], s["alto"]
    w = 2 * int(round(W * ad["tarjeta_ancho"] / 2))
    h = 2 * int(round(w * H / W / 2))
    return {"x": (W - w) // 2, "y": int(round(H * ad["tarjeta_y"])), "w": w, "h": h}


def _num(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _rect(w, h, r):
    """Rectángulo con esquinas redondeadas como dibujo ASS (\\p1), desde (0, 0)."""
    r = max(0.0, min(r, w / 2, h / 2))
    c = 0.552 * r
    pts = ["m", r, 0, "l", w - r, 0, "b", w - r + c, 0, w, r - c, w, r, "l", w, h - r,
           "b", w, h - r + c, w - r + c, h, w - r, h, "l", r, h, "b", r - c, h, 0, h - r + c, 0, h - r,
           "l", 0, r, "b", 0, r - c, r - c, 0, r, 0]
    return " ".join(x if isinstance(x, str) else _num(x) for x in pts)


def _esquina(r, voltear_x, voltear_y):
    """Lo que queda fuera de un cuarto de círculo de radio r, en un cuadro r x r (para tapar con el fondo)."""
    c = 0.552 * r
    base = [("m", (0, 0)), ("l", (r, 0)), ("b", (r - c, 0), (0, r - c), (0, r)), ("l", (0, 0))]
    out = []
    for op, *pts in base:
        out.append(op)
        for x, y in pts:
            out += [_num(r - x if voltear_x else x), _num(r - y if voltear_y else y)]
    return " ".join(out)


def _estilo_ass(nombre, fuente, tamano, color, alin=7):
    return (f"Style: {nombre},{fuente},{tamano},{color_ass(color)},&H000000FF,&H00000000,&H00000000,"
            f"0,0,0,0,100,100,0,0,1,0,0,{alin},0,0,0,1")


def marco_ass(est, capas_t, dur):
    """El .ass del marco (lienzo 1080x1920): título, esquinas de la tarjeta, bloques de capas, etiquetas y cabezal."""
    ad = est["antes_despues"]
    W1, H1 = 1080, 1920
    k = W1 / est["salida"]["ancho"]
    g = {n: v * k for n, v in geometria(est).items()}
    estilos = [_estilo_ass("TituloAD", ad["fuente_titulo"], ad["tamano_titulo"], ad["color_titulo"], 5),
               _estilo_ass("Esquina", "Poppins SemiBold", 10, ad["fondo"]),
               _estilo_ass("Bloque", "Poppins SemiBold", 10, "#FFFFFF"),
               _estilo_ass("Etiqueta", ad["fuente_etiqueta"], ad["tamano_etiqueta"], ad["color_etiqueta"], 8),
               _estilo_ass("Cabezal", "Poppins SemiBold", 10, ad["color_cabezal"])]
    cab = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W1}", f"PlayResY: {H1}", "WrapStyle: 2",
           "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
           "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
           "MarginL, MarginR, MarginV, Encoding", *estilos, "", "[Events]",
           "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    T0, T1 = tiempo_ass(0), tiempo_ass(dur)
    ev = []

    def dlg(capa, a, b, estilo, etiquetas, texto):
        ev.append(f"Dialogue: {capa},{tiempo_ass(a)},{tiempo_ass(b)},{estilo},,0,0,0,,{{{etiquetas}}}{texto}")

    if ad["titulo"]:
        dlg(4, 0, dur, "TituloAD", f"\\an5\\pos(540,{int(H1 * ad['titulo_y'])})", _escapar(ad["titulo"]))
    r = ad["radio"]
    for vx, vy in ((False, False), (True, False), (False, True), (True, True)):
        x = g["x"] + (g["w"] - r if vx else 0)
        y = g["y"] + (g["h"] - r if vy else 0)
        ev.append(f"Dialogue: 4,{T0},{T1},Esquina,,0,0,0,,{{\\an7\\pos({_num(x)},{_num(y)})\\p1}}"
                  f"{_esquina(r, vx, vy)}")
    n = len(capas_t)
    px_s = (ad["bloque_ancho"] + ad["separacion"]) / (dur / n)
    cx = W1 / 2
    yb = H1 * ad["barra_y"]
    alto = ad["bloque_alto"]
    pendiente = f"\\1a&H{round(255 * (1 - ad['opacidad_pendiente'])):02X}&"

    def x_en(ini, t):
        return cx + (ini - t) * px_s

    for c in capas_t:
        ini, fin = round(c["ini"], 2), round(c["fin"], 2)
        ancho = max(4.0, (fin - ini) * px_s - ad["separacion"])
        forma = _rect(ancho, alto, ad["radio_bloque"])
        col = f"\\1c{color_ass(c['color'])}"
        nombre = _escapar(c["nombre"])
        tramos = []
        if ini > 0:
            tramos.append((0.0, ini, pendiente))
        tramos.append((ini, dur, ""))
        for a, b, alfa in tramos:
            mv = f"\\move({_num(x_en(ini, a))},{_num(yb)},{_num(x_en(ini, b))},{_num(yb)})"
            if not alfa and ad["brillo_bloque"]:
                dlg(1, a, b, "Bloque", f"\\an7{mv}{col}\\1a&H80&\\blur{ad['brillo_bloque']}\\p1", forma)
            dlg(2, a, b, "Bloque", f"\\an7{mv}{col}{alfa}\\p1", forma)
            mvt = (f"\\move({_num(x_en(ini, a) + ancho / 2)},{_num(yb + alto + 14)},"
                   f"{_num(x_en(ini, b) + ancho / 2)},{_num(yb + alto + 14)})")
            dlg(3, a, b, "Etiqueta", f"\\an8{mvt}{alfa}", nombre)
    dlg(5, 0, dur, "Cabezal", f"\\an7\\pos({_num(cx - 1.5)},{_num(yb - 30)})\\p1",
        _rect(3, alto + 30 + 70, 0))
    return "\n".join(cab + ev) + "\n"

