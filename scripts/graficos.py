"""Gráficos dibujados con Pillow que ffmpeg superpone al video (textos.json):

- tarjetas: interfaz animada (lista que se palomea, insignia tipo píldora, mensaje con avatar, barra de comentario
  con flecha hacia abajo). Bordes muy redondeados, sombra suave, entrada con escala (pop), salida con desvanecido.
- flotantes: 1 a 4 clips del usuario en ventanas con esquinas redondeadas y sombra alrededor de la persona; entran con
  pop (escalonados si entran juntos) y salen; sin audio: la voz principal sigue.
- boceto: tramo donde el fondo real se vuelve dibujo de líneas (bordes del propio cuadro, en negro sobre papel) y la
  persona queda encima. Segmentación local opcional (mediapipe o rembg); sin ella, avisa y se salta.
- particulas: ráfaga corta de estrellas pastel que sale de un punto en un segundo dado, generada por código.

Cada gráfico se dibuja cuadro por cuadro en un lienzo transparente chico (solo lo que ocupa, no la pantalla entera) y
se guarda como un .mov con alfa (códec png) en <trabajo>/graficos/. render.filtro_video lo superpone en su segundo
(«sprite»: archivo, x, y, ini, fin; x, y = esquina del lienzo en px de la salida, pueden ser negativos).
Las medidas de estilo.json están en px de un lienzo de 1080x1920: aquí se escalan a la salida real.
"""
import math
import os
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from estilo import RAIZ
from frases import ARCHIVOS

SS = 2                 # se dibuja al doble y se reduce: orillas suaves sin depender del antialias de Pillow
HOLGURA = 1.12         # el lienzo crece un 12 % para que quepa el rebote del pop
TIPOS_TARJETA = ("lista", "insignia", "mensaje", "comentario")
ICONOS = ("✨", "▶")


# ---------------------------------------------------------------- utilidades

def _rgb(hexa):
    h = hexa.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgba(hexa, opacidad=1.0):
    return _rgb(hexa) + (int(round(255 * opacidad)),)


_fuentes = {}


def fuente_pil(nombre, px):
    px = max(1, int(round(px)))
    clave = (nombre, px)
    if clave not in _fuentes:
        ruta = os.path.join(RAIZ, "fuentes", ARCHIVOS.get(nombre, nombre))
        _fuentes[clave] = ImageFont.truetype(ruta, px)
    return _fuentes[clave]


def escala_pop(t, an):
    """Escala en el segundo t desde que entra: de pop_desde a 1 con un rebote (ease-out-back)."""
    pop = an["pop_ms"] / 1000
    if pop <= 0 or t >= pop:
        return 1.0
    p = max(0.0, t) / pop
    c1 = 1.70158
    f = 1 + (c1 + 1) * (p - 1) ** 3 + c1 * (p - 1) ** 2
    return an["pop_desde"] + (1 - an["pop_desde"]) * f


def alfa_anim(t, dur, an):
    """Opacidad: sube en la primera mitad del pop y baja a 0 en los últimos salida_ms."""
    pop, sal = an["pop_ms"] / 1000, an["salida_ms"] / 1000
    a = 1.0
    if pop > 0:
        a = min(a, max(0.0, t) / (pop / 2))
    if sal > 0:
        a = min(a, max(0.0, dur - t) / sal)
    return max(0.0, min(1.0, a))


def partes_texto(texto):
    """[("texto", s) | ("icono", c)]. ✨ y ▶ se dibujan como figuras (las fuentes no traen emojis); otros emojis
    y símbolos se quitan con un aviso."""
    partes, quitados = [], []
    for ch in texto:
        o = ord(ch)
        if ch in ICONOS:
            partes.append(("icono", ch))
            continue
        if o == 0xFE0F or o == 0x200D:
            continue
        if o >= 0x1F000 or 0x2190 <= o <= 0x2BFF:
            quitados.append(ch)
            continue
        if partes and partes[-1][0] == "texto":
            partes[-1] = ("texto", partes[-1][1] + ch)
        else:
            partes.append(("texto", ch))
    if quitados:
        print(f"AVISO: se quitaron {''.join(quitados)} de «{texto}»: solo se dibujan ✨ y ▶")
    return partes


def _estrella(d, cx, cy, r, color, puntas=4, interior=0.32, giro=0.0):
    pts = []
    for i in range(puntas * 2):
        ang = giro - math.pi / 2 + i * math.pi / puntas
        rr = r if i % 2 == 0 else r * interior
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    d.polygon(pts, fill=color)


def _icono(d, ch, x, base, px, color):
    """Dibuja el icono con su caja empezando en x; devuelve su ancho."""
    w = px * 0.95
    cy = base - px * 0.36
    if ch == "✨":
        _estrella(d, x + w * 0.42, cy, px * 0.42, color)
        _estrella(d, x + w * 0.85, cy - px * 0.32, px * 0.17, color)
    elif ch == "▶":
        r = px * 0.36
        d.polygon([(x + w * 0.5 - r * 0.8, cy - r), (x + w * 0.5 - r * 0.8, cy + r), (x + w * 0.5 + r, cy)],
                  fill=color)
    return w


def _ancho(partes, fnt):
    return sum(fnt.getlength(s) if k == "texto" else fnt.size * 0.95 for k, s in partes)


def _escribir(d, partes, x, base, fnt, color, color_icono=None):
    for k, s in partes:
        if k == "texto":
            d.text((x, base), s, font=fnt, fill=color, anchor="ls")
            x += fnt.getlength(s)
        else:
            x += _icono(d, s, x, base, fnt.size, color_icono or color)
    return x


def _envolver(texto, fnt, ancho):
    lineas, actual = [], ""
    for p in texto.split():
        prueba = (actual + " " + p).strip()
        if actual and _ancho(partes_texto(prueba), fnt) > ancho:
            lineas.append(actual)
            actual = p
        else:
            actual = prueba
    return lineas + ([actual] if actual else [])


def _con_sombra(forma, relleno_rgba, sombra, opacidad, bajada, margen):
    """forma: máscara L (a SS) de la tarjeta. Devuelve (lienzo RGBA con margen, sombra debajo y la tarjeta encima)."""
    w, h = forma.size
    lienzo = Image.new("RGBA", (w + 2 * margen, h + 2 * margen), (0, 0, 0, 0))
    m_grande = Image.new("L", lienzo.size, 0)
    m_grande.paste(forma, (margen, margen))
    som = Image.new("L", lienzo.size, 0)
    som.paste(forma.point(lambda v: int(v * opacidad)), (margen, margen + bajada))
    if sombra > 0:
        som = som.filter(ImageFilter.GaussianBlur(sombra))
    # la sombra solo por fuera: así una tarjeta translúcida no se ensucia por dentro
    fuera = m_grande.point(lambda v: 255 - v)
    som = Image.composite(som, Image.new("L", lienzo.size, 0), fuera)
    capa_sombra = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    capa_sombra.putalpha(som)
    tarjeta = Image.new("RGBA", lienzo.size, relleno_rgba[:3] + (0,))
    tarjeta.putalpha(m_grande.point(lambda v: int(v * relleno_rgba[3] / 255)))
    return Image.alpha_composite(capa_sombra, tarjeta)


def _reducir(im):
    return im.convert("RGBa").resize((max(1, im.width // SS), max(1, im.height // SS)),
                                     Image.BOX).convert("RGBA")


# ---------------------------------------------------------------- tarjetas

def _conf(t, est):
    ta = est["tarjetas"]
    c = dict(ta)
    c.update(ta.get(t["tipo"], {}))
    return c


def tiempos_palomeo(n, dur, an):
    """Segundos (desde que entra la tarjeta) en que se palomea cada renglón, parejos entre el pop y la salida."""
    ini = an["pop_ms"] / 1000 + 0.35
    fin = max(ini, dur - an["salida_ms"] / 1000 - 0.5)
    if n <= 1:
        return [ini] * n
    return [ini + i * (fin - ini) / (n - 1) for i in range(n)]


def _palomita(d, cx, cy, r, color_fondo, color_marca):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color_fondo)
    d.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)],
           fill=color_marca, width=max(2, int(r * 0.28)), joint="curve")


def dibujar_tarjeta(t, est):
    """Devuelve (estados, caja): imágenes RGBA en px de salida (una por estado; la lista tiene renglones+1) y la caja
    (x0, y0, x1, y1) de la tarjeta dentro de la imagen (lo demás es sombra y margen)."""
    tipo = t.get("tipo")
    if tipo not in TIPOS_TARJETA:
        raise ValueError(f"tarjetas: tipo desconocido «{tipo}» (usa {', '.join(TIPOS_TARJETA)})")
    c = _conf(t, est)
    W = est["salida"]["ancho"]
    u = W / 1080 * SS
    tam = c["tamano"] * u
    texto_c, tenue, acento = _rgba(c["color_texto"]), _rgba(c["color_tenue"]), _rgba(c["acento"])
    destello = _rgba(c["color_destello"])
    fnt, fnt_b = fuente_pil(c["fuente"], tam), fuente_pil(c["fuente_negrita"], tam)
    pad = c["relleno"] * u
    margen = int(c["sombra"] * u * 2.5 + c["bajada_sombra"] * u)
    dibujos = []          # funciones (d, ox, oy, estado) que pintan el contenido

    if tipo == "insignia":
        alto = tam * 2.0
        partes = partes_texto(t.get("texto", ""))
        ancho = _ancho(partes, fnt_b) + alto
        radio = alto / 2

        def contenido(d, ox, oy, k):
            _escribir(d, partes, ox + alto / 2, oy + alto / 2 + tam * 0.36, fnt_b, texto_c, destello)
        dibujos.append(contenido)
        estados = 1
    elif tipo == "lista":
        ancho = c["ancho"] * W * SS
        renglones = [r if isinstance(r, str) else r["texto"] for r in t.get("renglones", [])]
        tt = c["tamano_titulo"] * u
        f_tit, f_chi = fuente_pil(c["fuente_negrita"], tt), fuente_pil(c["fuente_chica"], tt * 1.25)
        alto_tit = tt * 1.5 if (t.get("titulo") or t.get("titulo_chico")) else 0
        alto_r = tam * 1.55
        alto = pad * 1.7 + alto_tit + alto_r * len(renglones)
        radio = c["radio"] * u
        r_cir = tam * 0.42

        def contenido(d, ox, oy, k):
            x, base = ox + pad, oy + pad + tt * 1.05
            if t.get("titulo_chico"):
                d.text((x, base), t["titulo_chico"] + " ", font=f_chi, fill=texto_c, anchor="ls")
                x += f_chi.getlength(t["titulo_chico"] + " ")
            if t.get("titulo"):
                _escribir(d, partes_texto(t["titulo"]), x, base, f_tit, texto_c, destello)
            for i, r in enumerate(renglones):
                cy = oy + pad + alto_tit + alto_r * (i + 0.5)
                cx = ox + pad + r_cir
                if i < k:
                    _palomita(d, cx, cy, r_cir, acento, (255, 255, 255, 255))
                    col, f_r = texto_c, fnt_b
                else:
                    d.ellipse([cx - r_cir, cy - r_cir, cx + r_cir, cy + r_cir], outline=tenue,
                              width=max(1, int(r_cir * 0.18)))
                    col, f_r = tenue, fnt
                _escribir(d, partes_texto(r), cx + r_cir + tam * 0.45, cy + tam * 0.36, f_r, col, destello)
            _estrella(d, ox + ancho - pad * 0.1, oy + pad * 0.1, tam * 0.55, acento, puntas=5, interior=0.45)
        dibujos.append(contenido)
        estados = len(renglones) + 1
    elif tipo == "mensaje":
        ancho = c["ancho"] * W * SS
        diam = tam * 1.7
        x_txt = pad + diam + tam * 0.5
        f_tit = fuente_pil(c["fuente_negrita"], tam * 0.6)
        lineas = _envolver(t.get("texto", ""), fnt, ancho - x_txt - pad)
        alto_tit = tam * 0.95 if t.get("titulo") else 0
        alto_l = tam * 1.3
        alto = pad * 2 + max(diam, alto_tit + alto_l * len(lineas))
        radio = c["radio"] * u

        def contenido(d, ox, oy, k):
            cy = oy + pad + diam / 2
            _avatar(d, ox + pad, cy, diam, t.get("iniciales", ""), acento, fnt_b)
            y = oy + pad + (tam * 0.6 if t.get("titulo") else 0)
            if t.get("titulo"):
                d.text((ox + x_txt, y), t["titulo"], font=f_tit, fill=acento, anchor="ls")
            for i, ln in enumerate(lineas):
                _escribir(d, partes_texto(ln), ox + x_txt, y + alto_l * (i + 0.85), fnt, texto_c, destello)
        dibujos.append(contenido)
        estados = 1
    else:  # comentario
        ancho = c["ancho"] * W * SS
        alto = tam * 2.1
        radio = alto / 2
        diam = alto * 0.66
        pal = t.get("palabra", "")
        pre = (t.get("texto") or c["texto"]) + " "

        def contenido(d, ox, oy, k):
            cy = oy + alto / 2
            x = ox + (alto - diam) / 2
            if t.get("iniciales"):
                _avatar(d, x, cy, diam, t["iniciales"], acento, fnt_b)
                x += diam + tam * 0.4
            else:
                x += tam * 0.3
            base = cy + tam * 0.36
            d.text((x, base), pre, font=fnt, fill=tenue, anchor="ls")
            d.text((x + fnt.getlength(pre), base), pal, font=fnt_b, fill=texto_c, anchor="ls")
            _icono(d, "▶", ox + ancho - alto * 0.5 - tam * 0.5, base, tam * 1.1, acento)
        dibujos.append(contenido)
        estados = 1

    forma = Image.new("L", (int(math.ceil(ancho)), int(math.ceil(alto))), 0)
    ImageDraw.Draw(forma).rounded_rectangle([0, 0, forma.width - 1, forma.height - 1], radius=radio, fill=255)
    base_img = _con_sombra(forma, _rgba(c["fondo"], c["opacidad_fondo"]), c["sombra"] * u, c["opacidad_sombra"],
                           int(c["bajada_sombra"] * u), margen)
    salida = []
    for k in range(estados):
        im = base_img.copy()
        d = ImageDraw.Draw(im)
        for f in dibujos:
            f(d, margen, margen, k)
        salida.append(_reducir(im))
    caja = tuple(int(round(v / SS)) for v in (margen, margen, margen + forma.width, margen + forma.height))
    return salida, caja


def _avatar(d, x, cy, diam, iniciales, color, fnt_b):
    d.ellipse([x, cy - diam / 2, x + diam, cy + diam / 2], fill=color)
    if iniciales:
        f = fuente_pil(fnt_b.path, diam * 0.42)
        d.text((x + diam / 2, cy), iniciales[:2].upper(), font=f, fill=(255, 255, 255, 255), anchor="mm")


def _flecha(d, cx, y0, largo, grosor, color):
    d.line([(cx, y0), (cx, y0 + largo)], fill=color, width=max(2, int(grosor)))
    a = grosor * 2.4
    d.polygon([(cx - a, y0 + largo - a * 0.6), (cx + a, y0 + largo - a * 0.6), (cx, y0 + largo + a * 0.9)],
              fill=color)


def _lienzo_animado(base, caja, t, dur, an):
    """Un cuadro: la imagen base escalada (pop) alrededor del centro de la caja y con su opacidad."""
    bw, bh = base.size
    cw, ch = int(math.ceil(bw * HOLGURA)), int(math.ceil(bh * HOLGURA))
    ox, oy = (cw - bw) // 2, (ch - bh) // 2
    lienzo = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    a = alfa_anim(t, dur, an)
    if a <= 0:
        return lienzo
    s = escala_pop(t, an)
    im = base
    if abs(s - 1) > 1e-3:
        im = base.convert("RGBa").resize((max(1, round(bw * s)), max(1, round(bh * s))),
                                         Image.BILINEAR).convert("RGBA")
    if a < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    ccx, ccy = (caja[0] + caja[2]) / 2, (caja[1] + caja[3]) / 2
    lienzo.paste(im, (int(round(ox + ccx - s * ccx)), int(round(oy + ccy - s * ccy))))
    return lienzo


def _desplazamiento(base):
    return _desplazamiento_tam(*base.size)


def _desplazamiento_tam(bw, bh):
    return (int(math.ceil(bw * HOLGURA)) - bw) // 2, (int(math.ceil(bh * HOLGURA)) - bh) // 2


def _validar_tiempos(cosa, nombre):
    if "ini" not in cosa or "fin" not in cosa:
        raise ValueError(f"{nombre}: cada elemento lleva ini y fin (segundos del video editado): {cosa}")
    if float(cosa["fin"]) <= float(cosa["ini"]):
        raise ValueError(f"{nombre}: fin debe ser mayor que ini: {cosa}")


def cuadros_tarjeta(t, est, fps):
    """Genera los cuadros (RGBA) de la tarjeta de ini a fin."""
    estados, caja = dibujar_tarjeta(t, est)
    an = est["tarjetas"]
    dur = float(t["fin"]) - float(t["ini"])
    palomeo = []
    if t["tipo"] == "lista":
        palomeo = tiempos_palomeo(len(estados) - 1, dur, an)
        for i, r in enumerate(t.get("renglones", [])):
            if isinstance(r, dict) and "en" in r:
                palomeo[i] = float(r["en"]) - float(t["ini"])
    c = _conf(t, est)
    flecha = t["tipo"] == "comentario" and t.get("flecha", c.get("flecha", True))
    for n in range(int(round(dur * fps))):
        tt = n / fps
        base = estados[sum(1 for p in palomeo if p <= tt)]
        if flecha:
            base = base.copy()
            d = ImageDraw.Draw(base)
            alto = caja[3] - caja[1]
            bote = alto * 0.12 * math.sin(2 * math.pi * 1.6 * tt)
            _flecha(d, (caja[0] + caja[2]) / 2, caja[3] + alto * 0.25 + bote, alto * 0.6, alto * 0.09,
                    _rgba(c["acento"]))
        yield _lienzo_animado(base, caja, tt, dur, an)


def posicion_tarjeta(t, caja, est):
    """Esquina (x, y) en px de salida donde va la caja de la tarjeta: centrada en (x, y) de la tarjeta o de su tipo y
    metida en la franja zona_y (debajo de la cara, lejos del subtítulo). Avisa si la tuvo que mover."""
    c = _conf(t, est)
    W, H = est["salida"]["ancho"], est["salida"]["alto"]
    w, h = caja[2] - caja[0], caja[3] - caja[1]
    if t.get("tipo") == "comentario" and t.get("flecha", c.get("flecha", True)):
        h_zona = h * 2.1          # la flecha cuelga debajo de la barra
    else:
        h_zona = h
    x = W * float(t.get("x", c["x"])) - w / 2
    y = H * float(t.get("y", c["y"])) - h / 2
    z0, z1 = c["zona_y"][0] * H, c["zona_y"][1] * H
    y_n = min(max(y, z0), z1 - h_zona)
    if abs(y_n - y) > 0.5:
        print(f"AVISO: la tarjeta «{t.get('tipo')}» de {t.get('ini', '?')} s se movió a la franja libre "
              f"{c['zona_y'][0]:.2f}-{c['zona_y'][1]:.2f} del alto (para no tapar la cara ni el subtítulo)")
    x = min(max(x, 0), W - w)
    return int(round(x)), int(round(y_n))


def avisos_ritmo(tarjetas, minimo=5.0):
    inis = sorted(float(t["ini"]) for t in tarjetas)
    for a, b in zip(inis, inis[1:]):
        if b - a < minimo:
            print(f"AVISO: dos tarjetas a {b - a:.1f} s (en {a:g} y {b:g} s); el estilo pide una cada {minimo:g}-8 s "
                  "como mucho")


def escribir_sprite(cuadros, ruta, fps):
    """Escribe los cuadros RGBA a un .mov con alfa (png). Devuelve (ancho, alto)."""
    proc, tam = None, None
    try:
        for im in cuadros:
            if proc is None:
                tam = im.size
                proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
                                         "-s", f"{tam[0]}x{tam[1]}", "-r", str(fps), "-i", "-", "-c:v", "png",
                                         "-pix_fmt", "rgba", ruta], stdin=subprocess.PIPE)
            proc.stdin.write(im.tobytes())
    finally:
        if proc is not None:
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError(f"ffmpeg no pudo escribir {ruta}")
    if tam is None:
        raise ValueError(f"sin cuadros para {ruta}")
    return tam


def preparar_tarjetas(tarjetas, est, carpeta):
    """Dibuja cada tarjeta a un .mov en carpeta. Devuelve sprites [{archivo, x, y, ini, fin}]."""
    for t in tarjetas:
        if t.get("tipo") not in TIPOS_TARJETA:
            raise ValueError(f"tarjetas: tipo desconocido «{t.get('tipo')}» (usa {', '.join(TIPOS_TARJETA)})")
        _validar_tiempos(t, "tarjetas")
    avisos_ritmo(tarjetas)
    fps = est["salida"]["fps"]
    sprites = []
    for k, t in enumerate(tarjetas):
        estados, caja = dibujar_tarjeta(t, est)
        x, y = posicion_tarjeta(t, caja, est)
        ox, oy = _desplazamiento(estados[0])
        ruta = os.path.join(carpeta, f"tarjeta{k}.mov")
        escribir_sprite(cuadros_tarjeta(t, est, fps), ruta, fps)
        sprites.append({"archivo": ruta, "x": x - ox - caja[0], "y": y - oy - caja[1],
                        "ini": float(t["ini"]), "fin": float(t["fin"])})
    return sprites


# ---------------------------------------------------------------- flotantes

def mascara_redondeada(w, h, radio):
    """Máscara L de w x h con esquinas redondeadas (dibujada al doble y reducida: orilla suave)."""
    m = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], radius=max(0, radio) * SS, fill=255)
    return m.resize((w, h), Image.BOX)


def _par(v):
    return max(2, 2 * int(round(v / 2)))


def _tam_flotante(f, est):
    """(ancho, alto) del clip dentro de la ventana y grosor del borde, en px de salida."""
    c = est["flotantes"]
    W = est["salida"]["ancho"]
    w = _par(W * float(f.get("ancho", c["ancho"])))
    h = _par(w / float(f.get("proporcion", c["proporcion"])))
    return w, h, int(round(c["borde"] * W / 1080))


def cajas_flotantes(flotantes, est):
    """Caja (x0, y0, x1, y1) de cada ventana (con borde) en px de salida. Las que no traen x, y toman los lugares
    de estilo.json (a los lados de la persona) en orden. Avisa si una tapa la cara (flotantes.cara)."""
    c = est["flotantes"]
    W, H = est["salida"]["ancho"], est["salida"]["alto"]
    lugares = iter(c["lugares"])
    cajas = []
    for f in flotantes:
        w, h, b = _tam_flotante(f, est)
        if "x" in f and "y" in f:
            x, y = float(f["x"]), float(f["y"])
        else:
            x, y = next(lugares, (0.5, 0.75))
        cx, cy = W * x, H * y
        wo, ho = w + 2 * b, h + 2 * b
        x0 = int(round(min(max(cx - wo / 2, 0), W - wo)))
        y0 = int(round(min(max(cy - ho / 2, 0), H - ho)))
        caja = (x0, y0, x0 + wo, y0 + ho)
        cara = c["cara"]
        if not (caja[2] <= cara["x"][0] * W or caja[0] >= cara["x"][1] * W or caja[3] <= cara["y"][0] * H
                or caja[1] >= cara["y"][1] * H):
            print(f"AVISO: el flotante «{f.get('archivo')}» de {f.get('ini', '?')} s tapa la zona de la cara "
                  f"(flotantes.cara); muévelo con x, y")
        cajas.append(caja)
    return cajas


def retrasos_flotantes(flotantes, est):
    """Los que entran en el mismo segundo no saltan a la vez: cada uno escalonado_ms después del anterior."""
    paso = est["flotantes"]["escalonado_ms"] / 1000
    vistos, r = {}, []
    for f in flotantes:
        k = round(float(f["ini"]), 3)
        r.append(vistos.get(k, 0) * paso)
        vistos[k] = vistos.get(k, 0) + 1
    return r


def leer_clip(archivo, desde, dur, tam, fps):
    """Cuadros RGB del clip, ya recortados a tam (llenan la ventana, se recorta lo que sobra)."""
    from render import _encuadre
    w, h = tam
    vf = ",".join(_encuadre("", w, h, fps)) + ",format=rgb24"
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{desde:.3f}", "-t", f"{dur + 0.1:.3f}", "-an", "-i",
                             archivo, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            stdout=subprocess.PIPE)
    n = w * h * 3
    try:
        while True:
            datos = proc.stdout.read(n)
            if len(datos) < n:
                break
            yield Image.frombytes("RGB", (w, h), datos)
    finally:
        proc.stdout.close()
        if proc.poll() is None:
            proc.kill()
        proc.wait()


def cuadros_flotante(f, est, fps, clip, tam, retraso=0.0):
    """Cuadros RGBA de la ventana: el clip con esquinas redondeadas, borde y sombra; pop al entrar (después de
    `retraso` s) y desvanecido al salir. Si el clip se acaba, se queda en su último cuadro."""
    c = est["flotantes"]
    k = est["salida"]["ancho"] / 1080
    w, h = tam
    b = int(round(c["borde"] * k))
    r = c["radio"] * k
    wo, ho = w + 2 * b, h + 2 * b
    margen = int(c["sombra"] * k * 2.5 + c["bajada_sombra"] * k)
    marco = _con_sombra(mascara_redondeada(wo, ho, r), _rgba(c["color_borde"]), c["sombra"] * k,
                        c["opacidad_sombra"], int(c["bajada_sombra"] * k), margen)
    m_in = mascara_redondeada(w, h, max(0, r - b))
    caja = (margen, margen, margen + wo, margen + ho)
    dur = float(f["fin"]) - float(f["ini"])
    ultimo = None
    for i in range(int(round(dur * fps))):
        tt = i / fps - retraso
        if tt >= 0 or ultimo is None:
            ultimo = next(clip, ultimo)
            if ultimo is None:
                raise ValueError(f"flotantes: el clip «{f.get('archivo')}» no dio ningún cuadro (¿desde de más?)")
        base = marco.copy()
        base.paste(ultimo, (margen + b, margen + b), m_in)
        yield _lienzo_animado(base, caja, tt, dur - retraso, c)


def preparar_flotantes(flotantes, est, carpeta):
    """archivo ya con ruta absoluta. Devuelve sprites [{archivo, x, y, ini, fin}]."""
    c = est["flotantes"]
    if len(flotantes) > c["maximo"]:
        raise ValueError(f"flotantes: como mucho {c['maximo']} ventanas (hay {len(flotantes)}); el estilo usa 2-4")
    for f in flotantes:
        _validar_tiempos(f, "flotantes")
    fps = est["salida"]["fps"]
    k = est["salida"]["ancho"] / 1080
    cajas, retrasos = cajas_flotantes(flotantes, est), retrasos_flotantes(flotantes, est)
    sprites = []
    for i, (f, caja, ret) in enumerate(zip(flotantes, cajas, retrasos)):
        w, h, b = _tam_flotante(f, est)
        margen = int(c["sombra"] * k * 2.5 + c["bajada_sombra"] * k)
        ox, oy = _desplazamiento_tam(w + 2 * b + 2 * margen, h + 2 * b + 2 * margen)
        dur = float(f["fin"]) - float(f["ini"])
        ruta = os.path.join(carpeta, f"flotante{i}.mov")
        clip = leer_clip(f["archivo"], float(f.get("desde", 0)), dur, (w, h), fps)
        escribir_sprite(cuadros_flotante(f, est, fps, clip, (w, h), ret), ruta, fps)
        sprites.append({"archivo": ruta, "x": caja[0] - ox - margen, "y": caja[1] - oy - margen,
                        "ini": float(f["ini"]), "fin": float(f["fin"])})
    return sprites


# ---------------------------------------------------------------- fondo en boceto

def mezcla_boceto(t, dur, c):
    """Cuánto boceto lleva el cuadro t de un tramo de dur s: entra y sale en transicion_ms."""
    tr = c["transicion_ms"] / 1000
    if tr <= 0:
        return 1.0 if 0 <= t <= dur else 0.0
    return max(0.0, min(1.0, t / tr, (dur - t) / tr))


_papeles = {}


def _papel(w, h, c, k):
    clave = (w, h, c["papel"], c["cuadricula"], c["color_cuadricula"], k)
    if clave not in _papeles:
        _papeles.clear()
        _papeles[clave] = _papel_nuevo(w, h, c, k)
    return _papeles[clave]


def _papel_nuevo(w, h, c, k):
    papel = Image.new("RGB", (w, h), _rgb(c["papel"]))
    paso = c["cuadricula"] * k
    if paso >= 3:
        d = ImageDraw.Draw(papel)
        col = _rgb(c["color_cuadricula"])
        x = 0.0
        while x < w:
            d.line([(int(x), 0), (int(x), h)], fill=col)
            x += paso
        y = 0.0
        while y < h:
            d.line([(0, int(y)), (w, int(y))], fill=col)
            y += paso
    return papel


def boceto_cuadro(img, mascara, est, mezcla=1.0):
    """El fondo de img se vuelve dibujo de líneas (bordes en negro sobre papel) y lo que marca la máscara (la
    persona, 255) queda encima tal cual. mezcla 0..1 para la transición."""
    if mezcla <= 0:
        return img.copy()
    c = est["boceto"]
    k = img.width / 1080
    gris = img.convert("L")
    if c["suavizado"] * k > 0.3:
        gris = gris.filter(ImageFilter.GaussianBlur(c["suavizado"] * k))
    bordes = gris.filter(ImageFilter.FIND_EDGES)
    g = max(1, int(round(c["grosor"] * k)))
    if g > 1:
        bordes = bordes.filter(ImageFilter.MaxFilter(g + 1 - g % 2))
    u, ct = c["umbral"], c["contraste"]
    tinta_a = bordes.point([max(0, min(255, int((v - u) * ct))) for v in range(256)])
    fondo = Image.composite(Image.new("RGB", img.size, _rgb(c["tinta"])), _papel(img.width, img.height, c, k),
                            tinta_a)
    m = mascara.convert("L")
    if m.size != img.size:
        m = m.resize(img.size, Image.BILINEAR)
    if c["borde_mascara"] * k > 0.3:
        m = m.filter(ImageFilter.GaussianBlur(c["borde_mascara"] * k))
    out = Image.composite(img.convert("RGB"), fondo, m)
    return out if mezcla >= 1 else Image.blend(img.convert("RGB"), out, mezcla)


def cargar_segmentador(est):
    """Función img -> máscara L de la persona, con mediapipe o rembg si están instalados (los dos son opcionales).
    None (con aviso) si no hay ninguno: el boceto se salta y el render sigue."""
    c = est["boceto"]
    modo = c["segmentador"]
    errores = []
    if modo in ("auto", "mediapipe"):
        try:
            import numpy as np
            import mediapipe as mp
            seg = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1)

            def con_mediapipe(img):
                m = seg.process(np.asarray(img.convert("RGB"))).segmentation_mask
                return Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8), "L")
            return con_mediapipe
        except Exception as e:  # sin paquete, sin modelo o API distinta: se prueba el siguiente
            errores.append(f"mediapipe: {type(e).__name__}")
    if modo in ("auto", "rembg"):
        try:
            from rembg import new_session, remove
            sesion = new_session(c["modelo_rembg"])

            def con_rembg(img):
                return remove(img.convert("RGB"), session=sesion, only_mask=True)
            return con_rembg
        except Exception as e:
            errores.append(f"rembg: {type(e).__name__}")
    print("AVISO: no hay segmentador local (pip install rembg, o mediapipe) — " + "; ".join(errores)
          + ")")
    return None


def tramos_de_intervalo(tramos, ini, fin):
    """Los tramos del crudo que caen en [ini, fin] del editado y el segundo del editado donde empieza el primero."""
    if not tramos:
        return None, 0.0
    sub, desde, acum = [], None, 0.0
    for a, b in tramos:
        e0, e1 = acum, acum + (b - a)
        if e1 > ini and e0 < fin:
            sub.append((a, b))
            desde = e0 if desde is None else desde
        acum = e1
    return sub, desde or 0.0


def preparar_boceto(bocetos, est, video, tramos, carpeta, hdr=False):
    """Para cada {ini, fin} del editado: saca esos cuadros del crudo (mismo encuadre y cortes que el render), les
    pone el fondo en boceto y los guarda en un .mp4 de pantalla completa que se superpone como una toma de apoyo.
    Devuelve [{archivo, ini, fin}] ([] si no hay segmentador)."""
    import time
    from render import _encuadre, expresion_seleccion
    if not bocetos:
        return []
    for b in bocetos:
        _validar_tiempos(b, "boceto")
    seg = cargar_segmentador(est)
    if seg is None:
        print(f"AVISO: sin segmentador se saltan {len(bocetos)} tramo(s) de fondo en boceto; el resto del render sigue")
        return []
    c = est["boceto"]
    s = est["salida"]
    W, H, fps = s["ancho"], s["alto"], s["fps"]
    sw = min(W, int(c["ancho_segmentacion"]))
    sh = max(2, int(round(H * sw / W)))
    salida = []
    for i, b in enumerate(bocetos):
        ini, fin = float(b["ini"]), float(b["fin"])
        sub, desde = tramos_de_intervalo(tramos, ini, fin)
        f = _encuadre("[0:v]", W, H, fps, hdr)
        if sub:
            f += [f"select='{expresion_seleccion(sub, fps)}'", f"setpts=N/{fps}/TB"]
        f += [f"trim=start={ini - desde:.4f}:end={fin - desde:.4f}", "setpts=PTS-STARTPTS", "format=rgb24"]
        lee = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-filter_complex", ",".join(f) + "[v]",
                                "-map", "[v]", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        ruta = os.path.join(carpeta, f"boceto{i}.mp4")
        escribe = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                                    f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "ultrafast",
                                    "-crf", "14", "-pix_fmt", "yuv420p", ruta], stdin=subprocess.PIPE)
        t0, n, tam = time.time(), 0, W * H * 3
        try:
            while True:
                datos = lee.stdout.read(tam)
                if len(datos) < tam:
                    break
                img = Image.frombytes("RGB", (W, H), datos)
                m = seg(img.resize((sw, sh), Image.BILINEAR))
                escribe.stdin.write(boceto_cuadro(img, m, est, mezcla_boceto(n / fps, fin - ini, c)).tobytes())
                n += 1
        finally:
            lee.stdout.close()
            lee.wait()
            escribe.stdin.close()
            if escribe.wait() != 0:
                raise RuntimeError(f"ffmpeg no pudo escribir {ruta}")
        if n == 0:
            raise ValueError(f"boceto: no hay cuadros en {ini}-{fin} s del editado")
        print(f"boceto {i}: {n} cuadros en {time.time() - t0:.1f} s")
        salida.append({"archivo": ruta, "ini": ini, "fin": ini + n / fps})
    return salida


# ---------------------------------------------------------------- partículas

def _estrellas(p, c, R):
    import random
    rnd = random.Random(p.get("semilla", 0))
    ab = math.radians(c["abanico"])
    t0, t1 = c["tamano"]
    cols = [_rgb(x) for x in c["colores"]]
    out = []
    for i in range(int(p.get("cantidad", c["cantidad"]))):
        out.append({"ang": -math.pi / 2 + rnd.uniform(-ab / 2, ab / 2),
                    "dist": R * rnd.uniform(0.45, 0.92),
                    "tam": rnd.uniform(t0, t1),
                    "color": cols[i % len(cols)],
                    "giro0": rnd.uniform(0, 2 * math.pi),
                    "giro": rnd.uniform(-3, 3),
                    "retraso": rnd.uniform(0, 0.12)})
    return out


def _componer(im, capa, x, y):
    """alpha_composite de capa en (x, y), recortando lo que se sale del lienzo."""
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(im.width, x + capa.width), min(im.height, y + capa.height)
    if x1 > x0 and y1 > y0:
        im.alpha_composite(capa.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def cuadros_particulas(p, est, fps):
    """Cuadros RGBA (lienzo cuadrado de 2*radio centrado en el punto) de una ráfaga de estrellas pastel: salen del
    punto en abanico hacia arriba, frenan, caen un poco, giran y se apagan. Determinista con `semilla`."""
    c = est["particulas"]
    k = est["salida"]["ancho"] / 1080
    R = round(c["radio"] * k)
    dur = float(p.get("dur", c["dur"]))
    estrellas = _estrellas(p, c, R * SS)
    lado = 2 * R * SS
    for n in range(int(round(dur * fps))):
        u0 = n / fps / dur
        im = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for e in estrellas:
            u = (u0 - e["retraso"]) / (1 - e["retraso"])
            if u <= 0:
                continue
            avance = 1 - (1 - u) ** 2.2
            x = lado / 2 + math.cos(e["ang"]) * e["dist"] * avance
            y = lado / 2 + math.sin(e["ang"]) * e["dist"] * avance + c["gravedad"] * R * SS * u * u
            esc = min(1.0, u / 0.12) * (1 - 0.4 * u)
            alfa = 1.0 if u < 0.55 else max(0.0, (1 - u) / 0.45)
            if alfa <= 0 or esc <= 0:
                continue
            r = e["tam"] * k * SS * esc
            lado_c = int(math.ceil(2 * r)) + 4
            capa = Image.new("RGBA", (lado_c, lado_c), (0, 0, 0, 0))
            _estrella(ImageDraw.Draw(capa), lado_c / 2, lado_c / 2, r, e["color"] + (255,),
                      puntas=c["puntas"], interior=0.45, giro=e["giro0"] + e["giro"] * u)
            if alfa < 1:
                capa.putalpha(capa.getchannel("A").point(lambda v, a=alfa: int(v * a)))
            _componer(im, capa, int(round(x - lado_c / 2)), int(round(y - lado_c / 2)))
        yield _reducir(im)


def preparar_particulas(particulas, est, carpeta):
    """[{x, y, t}] (punto en fracciones y segundo del editado). Devuelve sprites [{archivo, x, y, ini, fin}]."""
    c = est["particulas"]
    for p in particulas:
        if "t" not in p:
            raise ValueError(f"particulas: cada ráfaga lleva t (segundo del video editado), x, y: {p}")
    W, H, fps = est["salida"]["ancho"], est["salida"]["alto"], est["salida"]["fps"]
    R = round(c["radio"] * W / 1080)
    sprites = []
    for i, p in enumerate(particulas):
        ruta = os.path.join(carpeta, f"particulas{i}.mov")
        escribir_sprite(cuadros_particulas(dict(p, semilla=p.get("semilla", i)), est, fps), ruta, fps)
        t = float(p["t"])
        sprites.append({"archivo": ruta, "x": round(W * float(p.get("x", 0.5))) - R,
                        "y": round(H * float(p.get("y", 0.6))) - R, "ini": t,
                        "fin": t + float(p.get("dur", c["dur"]))})
    return sprites
