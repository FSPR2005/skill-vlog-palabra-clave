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


def filtro_video(est, tramos, ass, fuentes, apoyos=(), color_filtro=None, hdr=False, apoyos_hdr=()):
    """apoyos: [(índice de entrada ffmpeg, ini, fin)] en segundos del video editado; tapan la imagen, no la voz."""
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
    if ass:
        f.append(f"ass={ass}" + (f":fontsdir={fuentes}" if fuentes else ""))
    f.append("format=yuv420p[vout]")
    return ";".join(cadenas + [",".join(f)])


def filtro_audio(est, tramos, hay_musica=False):
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
              f"[1:a]aresample=48000,volume={a['musica_db']}dB[mus0]"]
    if a["ducking"]:
        partes.append("[mus0][llave]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=350[mus]")
    else:
        partes.append("[llave]anullsink;[mus0]anull[mus]")
    partes.append("[voz][mus]amix=inputs=2:duration=first:normalize=0[aout]")
    return ";".join(partes)
