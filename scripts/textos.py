"""Texto en pantalla como subtítulos ASS (los quema ffmpeg con libass):

- Frase / ClaveN: subtítulo que se arma palabra por palabra (ver frases.py), el modo principal.
- Palabra: UNA palabra chica y blanca al centro que cambia con la voz (tomas de apoyo).
- TituloChico + TituloGrande: el título del gancho; una línea chica en letra caligráfica y color pastel,
  encima y a la izquierda de una línea grande en sans negrita blanca.
- Nota: comentario escrito a mano, girado, cerca de la cabeza.
"""
import re

PUNTUACION = re.compile(r"[^\w\s'’:\-)(]", re.UNICODE)


def limpiar_palabra(p, minusculas=True):
    p = PUNTUACION.sub("", p).strip()
    p = p.strip("-")
    return p.lower() if minusculas else p


def bloques_de_palabras(palabras, n=1, hueco_max=0.4, minusculas=True):
    """Agrupa de n en n. Cada bloque se queda hasta que entra el siguiente, sin pasar de hueco_max de silencio."""
    limpias = [dict(w, p=limpiar_palabra(w["p"], minusculas)) for w in palabras]
    limpias = [w for w in limpias if w["p"]]
    bloques = []
    for i in range(0, len(limpias), n):
        g = limpias[i:i + n]
        bloques.append({"texto": " ".join(w["p"] for w in g), "ini": g[0]["ini"], "fin": g[-1]["fin"]})
    for a, b in zip(bloques, bloques[1:]):
        a["fin"] = round(min(b["ini"], a["fin"] + hueco_max), 3)
    if bloques:
        bloques[-1]["fin"] = round(bloques[-1]["fin"], 3)
    return bloques


def tiempo_ass(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def color_ass(hexa, alfa=0):
    h = hexa.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alfa:02X}{b}{g}{r}".upper()


def _escapar(texto):
    return texto.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def _estilo(nombre, fuente, tamano, color, sombra_col, sombra, alin=5, contorno=0, col_contorno="#000000"):
    return (f"Style: {nombre},{fuente},{tamano},{color_ass(color)},&H000000FF,{color_ass(col_contorno)},{sombra_col},"
            f"0,0,0,0,100,100,0,0,1,{contorno},{sombra},{alin},0,0,0,1")


def _encoger(texto, fuente, tamano, ancho_max=0.9 * 1080):
    """Etiqueta \\fscx\\fscy para que el texto quepa en ancho_max (o "" si ya cabe)."""
    from frases import ancho_texto
    w = ancho_texto(texto, fuente, tamano)
    if w <= ancho_max:
        return ""
    k = int(100 * ancho_max / w)
    return f"\\fscx{k}\\fscy{k}"


def _en_tramos(t, tramos):
    return any(a <= t < b for a, b in tramos)


def generar_ass(palabras, estilo, titulos=(), notas=(), claves=None, palabra_suelta=(), posiciones=()):
    """palabras ya en la línea de tiempo del video editado. Devuelve el texto del .ass.

    palabra_suelta: [[ini, fin]] donde se usa el modo de una palabra al centro (tomas de apoyo) en vez de frases.
    """
    from frases import eventos_frases
    W, H = 1080, 1920
    s, t, n = estilo["subtitulos"], estilo["titulo"], estilo["notas"]
    fr, pa = s["frases"], s["palabra"]
    sc = color_ass("#000000", int(255 * (1 - s["opacidad_sombra"])))
    estilos = [_estilo("Palabra", pa["fuente"], pa["tamano"], pa["color"], sc, s["sombra"]),
               _estilo("Frase", fr["fuente"], fr["tamano"], fr["color"], sc, s["sombra"], alin=7)]
    for i, c in enumerate(fr["claves"]):
        estilos.append(_estilo(f"Clave{i}", c["fuente"], c["tamano"], c["color"], sc, s["sombra"], alin=7))
    estilos += [_estilo("TituloChico", t["fuente_chica"], t["tamano_chica"], t["color_chica"], sc, t["sombra"]),
                _estilo("TituloGrande", t["fuente_grande"], t["tamano_grande"], t["color_grande"], sc, t["sombra"]),
                _estilo("Nota", n["fuente"], n["tamano"], n["color"], sc, 1)]
    cab = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2",
           "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
           "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
           "MarginL, MarginR, MarginV, Encoding", *estilos, "", "[Events]",
           "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    ev = []

    def fad(ms_in, ms_out=0):
        return f"\\fad({int(ms_in)},{int(ms_out)})" if (ms_in or ms_out) else ""

    if s["activar"]:
        if s["modo"] == "palabra":
            sueltas, en_frase = list(palabras), []
        else:
            sueltas = [w for w in palabras if _en_tramos(w["ini"], palabra_suelta)]
            en_frase = [w for w in palabras if not _en_tramos(w["ini"], palabra_suelta)]
        x, y = int(W * pa["posicion_x"]), int(H * pa["posicion_y"])
        pop = ""
        if pa["pop_ms"]:
            pop = f"\\fscx{pa['pop_desde']}\\fscy{pa['pop_desde']}\\t(0,{int(pa['pop_ms'])},\\fscx100\\fscy100)"
        cl = {limpiar_palabra(c, True) for c in (claves or [])}
        for b in bloques_de_palabras(sueltas, pa["palabras_por_bloque"], s["hueco_max"], s["minusculas"]):
            if b["fin"] - b["ini"] < 0.01:
                continue
            nombre, extra = "Palabra", pop
            if cl and b["texto"].lower() in cl and fr["claves"]:
                k = fr["claves"][0]
                nombre = "Clave0"
                extra = (f"\\an5\\3c{color_ass(k.get('color_brillo', k['color']))}\\bord{k.get('brillo', 0)}"
                         f"\\blur{k.get('brillo', 0)}" + _encoger(b["texto"], k["fuente"], k["tamano"]))
            px, py = x, y
            if _en_tramos(b["ini"], palabra_suelta):
                py = int(H * pa["posicion_y_apoyo"])
            for pos in posiciones:
                if pos["ini"] <= b["ini"] < pos["fin"]:
                    px, py = int(W * pos["x"]), int(H * pos["y"])
            ev.append(f"Dialogue: 1,{tiempo_ass(b['ini'])},{tiempo_ass(b['fin'])},{nombre},,0,0,0,,"
                      f"{{\\pos({px},{py}){extra}}}{_escapar(b['texto'])}")
        for e in eventos_frases(en_frase, estilo, claves, posiciones):
            extra = ""
            if e["estilo"].startswith("Clave"):
                k = fr["claves"][int(e["estilo"][5:])]
                extra = (f"\\3c{color_ass(k.get('color_brillo', k['color']))}\\bord{k.get('brillo', 0)}"
                         f"\\blur{k.get('brillo', 0)}")
            ev.append(f"Dialogue: 1,{tiempo_ass(e['ini'])},{tiempo_ass(e['fin'])},{e['estilo']},,0,0,0,,"
                      f"{{\\pos({e['x']},{e['y']}){extra}}}{_escapar(e['texto'])}")
    for ti in titulos:
        y = int(H * ti.get("posicion_y", t["posicion_y"]))
        xg = W // 2
        xc = int(W * (0.5 + t["desfase_chica_x"]))
        f = fad(t["entrada_ms"], t["salida_ms"])
        if ti.get("chico"):
            ev.append(f"Dialogue: 2,{tiempo_ass(ti['ini'])},{tiempo_ass(ti['fin'])},TituloChico,,0,0,0,,"
                      f"{{\\pos({xc},{y - t['separacion']}){f}{_encoger(ti['chico'], t['fuente_chica'], t['tamano_chica'])}}}"
                      f"{_escapar(ti['chico'])}")
        if ti.get("grande"):
            ev.append(f"Dialogue: 2,{tiempo_ass(ti['ini'])},{tiempo_ass(ti['fin'])},TituloGrande,,0,0,0,,"
                      f"{{\\pos({xg},{y}){f}{_encoger(ti['grande'], t['fuente_grande'], t['tamano_grande'])}}}"
                      f"{_escapar(ti['grande'])}")
    for no in notas:
        x = int(W * no.get("posicion_x", n["posicion_x"]))
        y = int(H * no.get("posicion_y", n["posicion_y"]))
        ev.append(f"Dialogue: 3,{tiempo_ass(no['ini'])},{tiempo_ass(no['fin'])},Nota,,0,0,0,,"
                  f"{{\\pos({x},{y})\\frz{-n['rotacion']}{fad(n['entrada_ms'])}}}{_escapar(no['texto'])}")
    return "\n".join(cab + ev) + "\n"
