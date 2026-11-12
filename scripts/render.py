"""Arma los filtros de ffmpeg: encuadre 9:16, cortes en salto, tomas de apoyo, color, texto ASS y audio.

Una sola pasada de ffmpeg, sin ramas trim por tramo (esas guardan cuadros en memoria): select/aselect con una
expresión por tramo y la línea de tiempo se rehace con setpts/asetpts.
"""


def expresion_seleccion(tramos, fps):
    # medio cuadro de holgura al final para que no entre el cuadro del borde
    m = 0.5 / fps
    return "+".join(f"between(t,{a:.4f},{b - m:.4f})" for a, b in tramos)


def _encuadre(entrada, W, H, fps):
    return [f"{entrada}fps={fps}", f"scale={W}:{H}:force_original_aspect_ratio=increase", f"crop={W}:{H}", "setsar=1"]


def filtro_video(est, tramos, ass, fuentes, apoyos=(), color_filtro=None):
    """apoyos: [(índice de entrada ffmpeg, ini, fin)] en segundos del video editado; tapan la imagen, no la voz."""
    s = est["salida"]
    W, H, fps = s["ancho"], s["alto"], s["fps"]
    f = _encuadre("[0:v]", W, H, fps)
    if tramos:
        f += [f"select='{expresion_seleccion(tramos, fps)}'", f"setpts=N/{fps}/TB"]
    cadenas = []
    if apoyos:
        cadenas.append(",".join(f) + "[base0]")
        for k, (idx, ini, fin) in enumerate(apoyos):
            cadenas.append(",".join(_encuadre(f"[{idx}:v]", W, H, fps)) + f",setpts=PTS-STARTPTS+{ini:.4f}/TB[ap{k}]")
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
    voz = ["[0:a]aresample=48000"]
    if tramos:
        voz += [f"aselect='{expresion_seleccion(tramos, est['salida']['fps'])}'", "asetpts=N/SR/TB"]
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
