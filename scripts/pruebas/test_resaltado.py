import json
import shutil
import subprocess

import pytest

from estilo import cargar_estilo
from frases import indices_resaltados, maquetar_frase, eventos_frases
from textos import generar_ass, color_ass

HAY_FFMPEG = shutil.which("ffmpeg") is not None


def P(*items):
    return [{"p": p, "ini": a, "fin": b} for p, a, b in items]


GANCHO = P(("¿Qué", 0.0, 0.2), ("pasa", 0.2, 0.4), ("si", 0.4, 0.5), ("le", 0.5, 0.6), ("pides", 0.6, 0.9),
           ("a", 0.9, 1.0), ("Chat", 1.0, 1.2), ("GPT", 1.2, 1.5), ("que", 1.5, 1.6), ("te", 1.6, 1.7),
           ("haga", 1.7, 1.9), ("viral?", 1.9, 2.4))


def test_resaltar_una_secuencia_de_palabras():
    assert indices_resaltados(GANCHO, ["pides a chat gpt"]) == {4, 5, 6, 7}
    assert indices_resaltados(GANCHO, ["¡Viral!"]) == {11}


def test_palabra_chica_solo_se_resalta_dentro_de_su_secuencia():
    assert indices_resaltados(GANCHO, ["chat gpt"]) == {6, 7}
    assert 5 not in indices_resaltados(GANCHO, ["chat gpt", "viral"])


def test_resaltar_con_ventana_de_tiempo():
    assert indices_resaltados(GANCHO, [{"texto": "pasa", "ini": 5, "fin": 9}]) == set()
    assert indices_resaltados(GANCHO, [{"texto": "pasa", "ini": 0, "fin": 1}]) == {1}


def test_secuencia_repetida_se_resalta_las_dos_veces():
    pal = P(("hola", 0, .2), ("mundo", .2, .4), ("y", .4, .5), ("hola", .5, .7))
    assert indices_resaltados(pal, ["hola"]) == {0, 3}


def test_maquetar_deja_la_palabra_resaltada_en_su_renglon():
    est = cargar_estilo(None)
    fr = P(("qué", 0, .2), ("pasa", .2, .4), ("si", .4, .5))
    m = maquetar_frase(fr, None, est, x0=100, y0=500, resaltadas={1})
    assert [x["estilo"] for x in m] == ["Frase", "Resaltado", "Frase"]
    assert m[1]["texto"] == "PASA"                                  # mayúsculas por omisión
    assert abs(m[1]["y"] - m[0]["y"]) < 15 and abs(m[2]["y"] - m[0]["y"]) < 15   # mismo renglón
    assert m[0]["x"] < m[1]["x"] < m[2]["x"]


def test_resaltado_ancho_no_se_sale():
    est = cargar_estilo(None)
    fr = P(("pides", 0, .2), ("a", .2, .3), ("chat", .3, .5), ("gpt", .5, .7))
    m = maquetar_frase(fr, None, est, x0=100, y0=500, resaltadas={0, 1, 2, 3})
    margen = int(1080 * (1 - est["subtitulos"]["frases"]["ancho_max"]) / 2)
    assert all(margen <= x["x"] < 1080 - margen for x in m)


def test_frase_con_resaltado_no_lleva_clave_pastel():
    est = cargar_estilo(None)
    ev = eventos_frases(GANCHO[:4], est, claves=None, resaltar=["pasa"])
    assert not any(e["estilo"].startswith("Clave") for e in ev)
    assert sum(e["estilo"] == "Resaltado" for e in ev) == 1


def test_secuencia_resaltada_no_se_parte_entre_dos_frases():
    est = cargar_estilo(None)
    # 4 palabras por frase: «tu» sería la 4.ª y «predial» abriría la siguiente
    pal = P(("si", 0, .2), ("de", .2, .3), ("la", .3, .4), ("tu", .4, .5), ("predial", .5, .9), ("hoy", .9, 1.1))
    ev = eventos_frases(pal, est, claves=None, resaltar=["tu predial"])
    res = [e for e in ev if e["estilo"] == "Resaltado"]
    assert [e["texto"] for e in res] == ["TU", "PREDIAL"]
    assert res[0]["fin"] == res[1]["fin"]                    # salen juntas: misma frase


def test_ass_en_modo_frases_pinta_el_resaltado_con_halo():
    est = cargar_estilo(None)
    est["subtitulos"]["modo"] = "frases"
    ass = generar_ass(GANCHO, est, resaltar=["pides a chat gpt"])
    assert "Style: Resaltado," in ass
    res = [l for l in ass.splitlines() if ",Resaltado,," in l]
    assert any(l.endswith("}PIDES") for l in res) and any(l.endswith("}GPT") for l in res)
    assert any(l.startswith("Dialogue: 0,") and "\\blur" in l for l in res)        # halo debajo
    # la frase resaltada («pides a chat gpt», 0.6-1.5 s) no lleva clave pastel; las otras sí pueden
    inicios_clave = {l.split(",")[1] for l in ass.splitlines() if l.startswith("Dialogue:") and ",Clave" in l}
    assert not inicios_clave & {"0:00:00.60", "0:00:00.90", "0:00:01.00", "0:00:01.20"}


def test_modo_fondo_usa_caja_de_color():
    est = cargar_estilo(None)
    est["subtitulos"]["modo"] = "frases"
    r = est["subtitulos"]["resaltado"]
    r["modo"] = "fondo"
    ass = generar_ass(GANCHO, est, resaltar=["viral"])
    st = [l for l in ass.splitlines() if l.startswith("Style: Resaltado,")][0].split(",")
    assert st[3] == color_ass(r["color_letra_fondo"]) and st[5] == color_ass(r["color_fondo"])
    assert st[15] == "3" and st[16] == str(r["relleno"])                         # BorderStyle 3 = caja
    res = [l for l in ass.splitlines() if ",Resaltado,," in l]
    assert len(res) == 1 and "\\blur" not in res[0]


def test_modo_palabra_tambien_resalta():
    est = cargar_estilo(None)
    est["subtitulos"]["modo"] = "palabra"
    ass = generar_ass(GANCHO[:3], est, claves=["pasa"], resaltar=["pasa"])
    d = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert any(",Resaltado,," in l and l.endswith("PASA") for l in d)
    assert not any(",Clave0,," in l for l in d)                                  # el resaltado manda


@pytest.mark.skipif(not HAY_FFMPEG, reason="requiere ffmpeg")
def test_render_con_resaltado(tmp_path):
    from editar import main
    crudo = tmp_path / "crudo.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:size=180x320:rate=30:d=3",
                    "-f", "lavfi", "-i", "sine=d=3", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(crudo)], check=True)
    (tmp_path / "p.json").write_text(json.dumps(GANCHO), encoding="utf-8")
    (tmp_path / "mini.json").write_text(json.dumps({"salida": {"ancho": 180, "alto": 320, "preset": "ultrafast"},
                                                    "color": {"activar": False},
                                                    "subtitulos": {"modo": "frases"}}), encoding="utf-8")
    (tmp_path / "t.json").write_text(json.dumps({"resaltar": ["pides a chat gpt"]}), encoding="utf-8")
    assert main(["render", str(crudo), "--salida", str(tmp_path / "ed.mp4"), "--trabajo", str(tmp_path / "tr"),
                 "--palabras", str(tmp_path / "p.json"), "--estilo", str(tmp_path / "mini.json"),
                 "--textos", str(tmp_path / "t.json"), "--sin-cortes"]) == 0
    assert ",Resaltado,," in (tmp_path / "tr" / "textos.ass").read_text(encoding="utf-8")
