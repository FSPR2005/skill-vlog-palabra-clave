import json
import shutil
import subprocess

import pytest

from estilo import cargar_estilo

HAY_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _est(ancho=1080, alto=1920):
    est = cargar_estilo(None)
    est["salida"]["ancho"], est["salida"]["alto"] = ancho, alto
    return est


def test_pop_arranca_chico_rebota_y_queda_en_1():
    from graficos import escala_pop
    an = {"pop_ms": 300, "pop_desde": 0.6, "salida_ms": 200}
    assert escala_pop(0, an) == pytest.approx(0.6)
    assert max(escala_pop(t / 1000, an) for t in range(0, 300, 5)) > 1.02   # rebote
    assert escala_pop(0.3, an) == pytest.approx(1.0)
    assert escala_pop(2.0, an) == 1.0


def test_alfa_entra_rapido_y_se_desvanece_al_salir():
    from graficos import alfa_anim
    an = {"pop_ms": 300, "pop_desde": 0.6, "salida_ms": 200}
    assert alfa_anim(0, 3.0, an) == 0
    assert alfa_anim(1.5, 3.0, an) == 1
    assert alfa_anim(2.9, 3.0, an) == pytest.approx(0.5, abs=0.02)
    assert alfa_anim(3.0, 3.0, an) == 0


def test_partes_dibuja_destello_y_flecha_y_quita_otros_emojis(capsys):
    from graficos import partes_texto
    assert partes_texto("✨ 100 % hecho con IA") == [("icono", "✨"), ("texto", " 100 % hecho con IA")]
    assert partes_texto("Comenta PROMPT ▶")[-1] == ("icono", "▶")
    assert partes_texto("hola 😀 ya") == [("texto", "hola  ya")]
    assert "AVISO" in capsys.readouterr().out


def test_tarjeta_tiene_esquinas_redondeadas_y_sombra_suave():
    from graficos import dibujar_tarjeta
    est = _est()
    estados, caja = dibujar_tarjeta({"tipo": "lista", "titulo": "todo hecho con IA",
                                     "renglones": ["Subtítulos", "Títulos", "Gráficos"]}, est)
    im = estados[0]
    x0, y0, x1, y1 = caja                      # la tarjeta dentro del lienzo (el resto es sombra y margen)
    assert im.getpixel(((x0 + x1) // 2, (y0 + y1) // 2))[3] > 230          # opaca al centro
    assert im.getpixel((x0 + 2, y0 + 2))[3] < 120                           # esquina redondeada: casi transparente
    a_sombra = im.getpixel(((x0 + x1) // 2, y1 + 8))[3]
    assert 0 < a_sombra < 120                                               # sombra suave debajo
    r, g, b, _ = im.getpixel((x0 + (x1 - x0) // 2, y0 + 6))
    assert min(r, g, b) > 230                                               # blanca


def test_lista_palomea_los_renglones_uno_por_uno():
    from graficos import dibujar_tarjeta, tiempos_palomeo
    est = _est()
    estados, _ = dibujar_tarjeta({"tipo": "lista", "titulo": "x", "renglones": ["a", "b", "c"]}, est)
    assert len(estados) == 4
    assert all(estados[i].tobytes() != estados[i + 1].tobytes() for i in range(3))
    an = est["tarjetas"]
    ts = tiempos_palomeo(3, 4.0, an)
    assert len(ts) == 3 and all(a < b for a, b in zip(ts, ts[1:]))
    assert ts[0] >= an["pop_ms"] / 1000 and ts[-1] <= 4.0 - an["salida_ms"] / 1000


@pytest.mark.parametrize("t", [
    {"tipo": "insignia", "texto": "✨ 100 % hecho con IA"},
    {"tipo": "mensaje", "iniciales": "AB", "titulo": "PROMPT", "texto": "edita mi reel con mi estilo ✨"},
    {"tipo": "comentario", "palabra": "PROMPT", "iniciales": "AB"},
])
def test_los_otros_tres_tipos_se_dibujan(t):
    from graficos import dibujar_tarjeta
    estados, (x0, y0, x1, y1) = dibujar_tarjeta(t, _est())
    assert len(estados) == 1 and x1 - x0 > 200 and y1 > y0


def test_insignia_es_pildora():
    from graficos import dibujar_tarjeta
    est = _est()
    est["tarjetas"]["insignia"]["fondo"] = "#FFFFFF"
    (im,), (x0, y0, x1, y1) = dibujar_tarjeta({"tipo": "insignia", "texto": "hola"}, est)
    h = y1 - y0
    # en una píldora, a h/4 de la orilla izquierda y a la altura de la orilla de arriba no hay tarjeta
    assert im.getpixel((x0 + h // 4, y0 + 2))[3] < 100
    assert im.getpixel((x0 + h // 2 + 4, y0 + 2))[3] > 150


def test_comentario_trae_flecha_hacia_abajo_que_se_mueve():
    from graficos import cuadros_tarjeta
    est = _est(540, 960)
    t = {"tipo": "comentario", "palabra": "PROMPT", "ini": 0, "fin": 2.0}
    cs = list(cuadros_tarjeta(t, est, 30))
    assert len(cs) == 60
    assert cs[20].tobytes() != cs[35].tobytes()          # la flecha sube y baja aunque la tarjeta esté quieta


def test_tipo_desconocido_o_sin_tiempos_da_error_claro():
    from graficos import preparar_tarjetas
    with pytest.raises(ValueError, match="tipo"):
        preparar_tarjetas([{"tipo": "burbuja", "ini": 0, "fin": 1}], _est(), ".")
    with pytest.raises(ValueError, match="ini"):
        preparar_tarjetas([{"tipo": "insignia", "texto": "x"}], _est(), ".")


def test_tarjeta_se_aleja_de_la_cara_y_del_subtitulo(capsys):
    from graficos import posicion_tarjeta
    est = _est()
    zona = est["tarjetas"]["zona_y"]
    x, y = posicion_tarjeta({"tipo": "insignia", "y": 0.4}, (0, 0, 600, 120), est)
    assert y >= zona[0] * 1920 - 1                       # la orilla de arriba queda dentro de la zona libre
    assert "AVISO" in capsys.readouterr().out
    x, y = posicion_tarjeta({"tipo": "insignia", "y": 0.99}, (0, 0, 600, 120), est)
    assert y + 120 <= zona[1] * 1920 + 1


def test_avisa_si_hay_tarjetas_muy_seguidas(capsys):
    from graficos import avisos_ritmo
    avisos_ritmo([{"ini": 1}, {"ini": 3}, {"ini": 12}])
    out = capsys.readouterr().out
    assert "AVISO" in out and "5" in out


def test_filtro_video_superpone_sprites_antes_del_texto():
    from render import filtro_video
    est = cargar_estilo(None)
    f = filtro_video(est, [(0.0, 5.0)], "textos.ass", "fuentes", sprites=[(1, 100, -20, 1.0, 3.0), (2, 5, 6, 2.5, 4)])
    assert "[1:v]setpts=PTS-STARTPTS+1.0000/TB" in f and "[2:v]" in f
    assert "overlay=x=100:y=-20:eof_action=pass:enable='between(t,1.0000,3.0000)'" in f
    assert f.index("ass=") > f.rindex("overlay=")


def _color_en(video, t, x, y):
    px = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-vf",
                         f"crop=2:2:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return tuple(px[:3])


@pytest.mark.skipif(not HAY_FFMPEG, reason="requiere ffmpeg")
def test_render_con_tarjeta_animada(tmp_path):
    from editar import main
    crudo = tmp_path / "crudo.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:size=270x480:rate=30:d=4",
                    "-f", "lavfi", "-i", "sine=f=300:d=4", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(crudo)], check=True)
    (tmp_path / "mini.json").write_text(json.dumps({"salida": {"ancho": 270, "alto": 480, "preset": "ultrafast"},
                                                    "color": {"activar": False}}), encoding="utf-8")
    (tmp_path / "textos.json").write_text(json.dumps({"tarjetas": [
        {"tipo": "lista", "titulo": "todo", "renglones": ["uno", "dos"], "ini": 1.0, "fin": 3.0, "y": 0.75}]}),
        encoding="utf-8")
    (tmp_path / "p.json").write_text("[]", encoding="utf-8")
    sal = tmp_path / "ed.mp4"
    assert main(["render", str(crudo), "--salida", str(sal), "--trabajo", str(tmp_path / "tr"), "--palabras",
                 str(tmp_path / "p.json"), "--estilo", str(tmp_path / "mini.json"),
                 "--textos", str(tmp_path / "textos.json")]) == 0
    cx, cy = 135, int(0.75 * 480)
    r, g, b = _color_en(sal, 0.5, cx, cy)
    assert b > 150 and r < 80, (r, g, b)                     # antes: el crudo azul
    r, g, b = _color_en(sal, 2.0, cx + 75, cy)                # a la derecha de los renglones cortos
    assert min(r, g, b) > 180, (r, g, b)                     # durante: tarjeta blanca
    r, g, b = _color_en(sal, 3.6, cx, cy)
    assert b > 150 and r < 80, (r, g, b)                     # después: se fue
    assert (tmp_path / "tr" / "graficos").is_dir()
