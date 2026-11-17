"""Arma los filtros de ffmpeg: encuadre 9:16, cortes en salto, tomas de apoyo, color, texto ASS y audio.

Una sola pasada de ffmpeg, sin ramas trim por tramo (esas guardan cuadros en memoria): select/aselect con una
expresión por tramo y la línea de tiempo se rehace con setpts/asetpts.

Audio y video se cortan por ÍNDICE de cuadro, no por segundo: el video ya va a fps fijos y el audio se parte en
paquetes de exactamente 48000/fps muestras (un paquete por cuadro). Así cada tramo dura lo mismo en los dos y no se
acumula desfase por muchos cortes.
"""

SR = 48000


def expresion_seleccion(tramos, fps):
    """Tramos en segundos (ya en la rejilla de cuadros) -> between(n,ka,kb-1) sobre el índice de cuadro."""
    partes = []
    for a, b in tramos:
        ka, kb = int(round(a * fps)), int(round(b * fps))
        if kb > ka:
            partes.append(f"between(n,{ka},{kb - 1})")
    return "+".join(partes)


def muestras_por_cuadro(fps):
    n = SR / fps
    if abs(n - round(n)) > 1e-9:
        raise ValueError(f"fps={fps} no divide 48000: usa 24, 25, 30, 48, 50 o 60")
    return int(round(n))


TONEMAP = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
           "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def _encuadre(entrada, W, H, fps, hdr=False):
    previo = [TONEMAP] if hdr else []
    return [f"{entrada}fps={fps}", *previo, f"scale={W}:{H}:force_original_aspect_ratio=increase", f"crop={W}:{H}",
            "setsar=1"]


def filtro_video(est, tramos, ass, fuentes, apoyos=(), color_filtro=None, hdr=False, apoyos_hdr=(), zoom=None,
                 marco=None, sprites=()):
    """apoyos: [(índice de entrada ffmpeg, ini, fin)] en segundos del video editado; tapan la imagen, no la voz.

    sprites: [(índice de entrada, x, y, ini, fin)]: gráficos con alfa (graficos.py) encima del color y del zoom y
    debajo del texto; x, y es la esquina en px de la salida.

    zoom: {"factor", "intervalos": [(ini, fin)]}: en esos tramos la imagen va acercada (zoom en salto), bajo el texto.
    marco: {"ass", "x", "y", "w", "h", "fondo", "dur"}: modo antes-despues; el video editado se encoge a una tarjeta
    sobre un fondo liso y encima se quema el .ass del marco (título, barra de capas).
    """
    s = est["salida"]
    W, H, fps = s["ancho"], s["alto"], s["fps"]
    f = _encuadre("[0:v]", W, H, fps, hdr)
    if tramos:
        f += [f"select='{expresion_seleccion(tramos, fps)}'", f"setpts=N/{fps}/TB"]
    cadenas = []
    if apoyos:
        cadenas.append(",".join(f) + "[base0]")
        for k, (idx, ini, fin) in enumerate(apoyos):
            hdr_k = k < len(apoyos_hdr) and apoyos_hdr[k]
            cadenas.append(",".join(_encuadre(f"[{idx}:v]", W, H, fps, hdr_k)) +
                           f",setpts=PTS-STARTPTS+{ini:.4f}/TB[ap{k}]")
            cadenas.append(f"[base{k}][ap{k}]overlay=eof_action=pass:enable='between(t,{ini:.4f},{fin:.4f})'"
                           f"[base{k + 1}]")
        f = [f"[base{len(apoyos)}]null"]
    c = est["color"]
    if color_filtro:
        f.append(color_filtro)
    elif c["activar"] and c["modo"] == "fijo":
        f.append(f"eq=brightness={c['brillo']}:contrast={c['contraste']}:saturation={c['saturacion']}:gamma={c['gamma']}")
    if zoom and zoom.get("intervalos"):
        Wz, Hz = 2 * int(round(W * zoom["factor"] / 2)), 2 * int(round(H * zoom["factor"] / 2))
        expr = "+".join(f"between(t,{a:.4f},{b:.4f})" for a, b in zoom["intervalos"])
        cadenas += [",".join(f) + ",split[za][zb]", f"[zb]scale={Wz}:{Hz},crop={W}:{H}[zc]",
                    f"[za][zc]overlay=0:0:enable='{expr}'[zoomed]"]
        f = ["[zoomed]null"]
    if sprites:
        cadenas.append(",".join(f) + "[gr0]")
        for k, (idx, x, y, ini, fin) in enumerate(sprites):
            cadenas.append(f"[{idx}:v]setpts=PTS-STARTPTS+{ini:.4f}/TB[sp{k}]")
            cadenas.append(f"[gr{k}][sp{k}]overlay=x={int(x)}:y={int(y)}:eof_action=pass:"
                           f"enable='between(t,{ini:.4f},{fin:.4f})'[gr{k + 1}]")
        f = [f"[gr{len(sprites)}]null"]
    if ass:
        f.append(f"ass={ass}" + (f":fontsdir={fuentes}" if fuentes else ""))
    if marco:
        m = marco
        cadenas.append(",".join(f + [f"scale={m['w']}:{m['h']}", "setsar=1"]) + "[tarjeta]")
        cadenas.append(f"color=c=0x{m['fondo'].lstrip('#')}:s={W}x{H}:r={fps}:d={m['dur']:.3f}[fondo]")
        f = [f"[fondo][tarjeta]overlay={m['x']}:{m['y']}:shortest=1",
             f"ass={m['ass']}" + (f":fontsdir={fuentes}" if fuentes else "")]
    f.append("format=yuv420p[vout]")
    return ";".join(cadenas + [",".join(f)])


def filtro_audio(est, tramos, hay_musica=False, musica_desde=None):
    """musica_desde: segundo en que entra la música (antes va en silencio); None = desde el principio."""
    a = est["audio"]
    fps = est["salida"]["fps"]
    # async + first_pts=0: respeta un audio que no empieza en 0 (rellena) antes de partirlo en paquetes por cuadro
    voz = ["[0:a]aresample=48000:async=1:first_pts=0"]
    if tramos:
        voz += [f"asetnsamples=n={muestras_por_cuadro(fps)}:p=0",
                f"aselect='{expresion_seleccion(tramos, fps)}'", "asetpts=N/SR/TB"]
    voz.append(f"loudnorm=I={a['voz_lufs']}:TP=-1.5:LRA=11,aresample=48000")
    if not hay_musica:
        return ",".join(voz) + "[aout]"
    partes = [",".join(voz) + ",asplit=2[voz][llave]",
              f"[1:a]aresample=48000,volume={a['musica_db']}dB{compuerta_musica(musica_desde)}[mus0]"]
    if a["ducking"]:
        partes.append("[mus0][llave]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=350[mus]")
    else:
        partes.append("[llave]anullsink;[mus0]anull[mus]")
    partes.append("[voz][mus]amix=inputs=2:duration=first:normalize=0[aout]")
    return ";".join(partes)


def compuerta_musica(desde):
    """Silencia la música antes de `desde` (filtro con timeline); "" si entra desde el principio."""
    return f",volume=0:enable='lt(t,{desde:.4f})'" if desde else ""
