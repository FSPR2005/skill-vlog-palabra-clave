"""Gráficos dibujados con Pillow que ffmpeg superpone al video (textos.json):

- tarjetas: interfaz animada (lista que se palomea, insignia tipo píldora, mensaje con avatar, barra de comentario
  con flecha hacia abajo). Bordes muy redondeados, sombra suave, entrada con escala (pop), salida con desvanecido.

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
                                     Image.LANCZOS).convert("RGBA")


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
    bw, bh = base.size
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
