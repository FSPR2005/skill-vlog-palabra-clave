import json
import shutil
import subprocess

import pytest

from estilo import cargar_estilo
from render import filtro_video, filtro_audio
from antes_despues import (capas_con_material, tiempos_capas, inicios_por_tipo, recortar_ass, con_enable,
                           cortes_editados, intervalos_zoom, geometria, marco_ass)

HAY_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _capas():
    return cargar_estilo(None)["antes_despues"]["capas"]


def test_estilo_trae_las_cinco_capas_del_antes_despues():
    nombres = [c["nombre"] for c in _capas()]
    assert nombres[0] == "Original" and len(nombres) == 5
    tipos = {t for c in _capas() for t in c["tipos"]}
    assert {"subtitulos", "zoom", "graficos", "musica"} <= tipos


def test_capa_sin_material_se_quita_y_se_avisa():
    capas, fuera = capas_con_material(_capas(), {"subtitulos", "color", "zoom"})
    assert [c["nombre"] for c in capas][0] == "Original"            # la capa sin tipos siempre se queda
    assert not any("musica" in c["tipos"] for c in capas)
    assert not any("graficos" in c["tipos"] for c in capas)
    assert len(fuera) == 2


def test_tiempos_reparten_parejo_si_no_traen_ini():
    t = tiempos_capas(_capas(), 10.0)
    assert [c["ini"] for c in t] == [0.0, 2.0, 4.0, 6.0, 8.0]
    assert [c["fin"] for c in t] == [2.0, 4.0, 6.0, 8.0, 10.0]


def test_tiempos_respetan_ini_explicito_y_validan():
    capas = [dict(c, ini=x) for c, x in zip(_capas(), [0, 1, 3, 6, 7])]
    t = tiempos_capas(capas, 9.0)
    assert [c["ini"] for c in t] == [0, 1, 3, 6, 7] and t[-1]["fin"] == 9.0
    with pytest.raises(ValueError):
        tiempos_capas([dict(capas[0], ini=0), _capas()[1]], 9.0)          # mezcla: unas con ini y otras sin
    with pytest.raises(ValueError):
        tiempos_capas([dict(capas[0], ini=0), dict(capas[1], ini=0)], 9.0)  # no crecen


def test_inicios_por_tipo():
    ini = inicios_por_tipo(tiempos_capas(_capas(), 10.0))
    assert ini["subtitulos"] == 2.0 and ini["color"] == 2.0 and ini["zoom"] == 4.0
    assert ini["graficos"] == 6.0 and ini["musica"] == 8.0


ASS = "\n".join([
    "[Events]",
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    "Dialogue: 1,0:00:00.50,0:00:01.20,Palabra,,0,0,0,,{\\pos(540,576)}hola",
    "Dialogue: 1,0:00:01.50,0:00:03.00,Frase,,0,0,0,,{\\pos(1,2)}mundo",
    "Dialogue: 0,0:00:02.50,0:00:04.00,Clave0,,0,0,0,,{\\pos(1,2)}clave",
    "Dialogue: 2,0:00:00.00,0:00:02.40,TituloGrande,,0,0,0,,{\\pos(1,2)}titulo",
    "Dialogue: 3,0:00:05.00,0:00:06.00,Nota,,0,0,0,,{\\pos(1,2)}nota",
])


def test_recortar_ass_por_capa():
    r = recortar_ass(ASS, {"subtitulos": 1.0, "graficos": 5.5})
    d = [l for l in r.splitlines() if l.startswith("Dialogue:")]
    assert len(d) == 4                                         # el título (acaba en 2.4) se va
    assert "0:00:01.00,0:00:01.20,Palabra" in d[0]             # empezaba antes: se recorta a su capa
    assert "0:00:01.50,0:00:03.00,Frase" in d[1]               # empieza después: igual
    assert "0:00:02.50,0:00:04.00,Clave0" in d[2]
    assert "0:00:05.50,0:00:06.00,Nota" in d[3]
    assert "[Events]" in r and "Format:" in r


def test_recortar_ass_sin_capa_quita_el_tipo():
    r = recortar_ass(ASS, {"graficos": 0.0})
    d = [l for l in r.splitlines() if l.startswith("Dialogue:")]
    assert all(",Titulo" in l or ",Nota," in l for l in d) and len(d) == 2


def test_con_enable_prende_cada_filtro_desde_un_segundo():
    f = con_enable("colorlevels=rimin=0.1:rimax=0.9,eq=gamma=1.1,colorbalance=rm=0.02", 2.5)
    assert f.count(":enable='gte(t,2.5000)'") == 3
    assert f.startswith("colorlevels=rimin=0.1:rimax=0.9:enable=") and f.endswith("colorbalance=rm=0.02:enable='gte(t,2.5000)'")


def test_cortes_editados_son_las_fronteras_de_los_tramos():
    assert cortes_editados([(1.0, 2.0), (3.0, 5.0), (6.0, 6.5)]) == [1.0, 3.0]


def test_zoom_alterna_entre_cortes_desde_su_capa():
    assert intervalos_zoom([2.0, 4.0, 6.0], 8.0, periodo=2.5) == [(2.0, 4.0), (6.0, 8.0)]
    assert intervalos_zoom([2.0, 4.0, 6.0], 8.0, periodo=2.5, desde=3.0) == [(3.0, 4.0), (6.0, 8.0)]


def test_zoom_sin_cortes_alterna_por_periodo():
    z = intervalos_zoom([], 10.0, periodo=2.5)
    assert z == [(2.5, 5.0), (7.5, 10.0)]


def test_geometria_de_la_tarjeta_es_par_y_centrada():
    est = cargar_estilo(None)
    g = geometria(est)
    assert g["w"] % 2 == 0 and g["h"] % 2 == 0
    assert abs(g["x"] * 2 + g["w"] - 1080) <= 1
    assert abs(g["h"] / g["w"] - 1920 / 1080) < 0.01


def test_marco_ass_tiene_titulo_bloques_que_se_mueven_y_cabezal():
    est = cargar_estilo(None)
    capas = tiempos_capas(_capas(), 10.0)
    ass = marco_ass(est, capas, 10.0)
    assert "PlayResX: 1080" in ass and "Original vs Editado" in ass
    d = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    for c in capas:
        assert any(c["nombre"] in l and "\\move(" in l for l in d), c["nombre"]
    # cada capa se ve tenue antes de su segundo y llena desde su segundo
    bloques = [l for l in d if ",Bloque," in l and "\\p1" in l]
    assert any(l.split(",")[1] == "0:00:02.00" for l in bloques)
    assert any("\\1a&H" in l and l.split(",")[2] == "0:00:02.00" for l in bloques)
    assert sum(",Cabezal," in l for l in d) == 1
    assert sum(",Esquina," in l for l in d) == 4


def test_filtro_video_con_zoom_y_marco():
    est = cargar_estilo(None)
    f = filtro_video(est, None, "textos.ass", "fuentes", zoom={"factor": 1.12, "intervalos": [(2.0, 4.0)]},
                     marco={"ass": "marco.ass", "x": 254, "y": 298, "w": 572, "h": 1016, "fondo": "#EEEEEB",
                            "dur": 10.0})
    assert "split" in f and "crop=1080:1920" in f
    assert "overlay=0:0:enable='between(t,2.0000,4.0000)'" in f
    assert "scale=572:1016" in f and "color=c=0xEEEEEB:s=1080x1920" in f
    assert "ass=marco.ass" in f and f.index("ass=textos.ass") < f.index("ass=marco.ass")
    assert f.endswith("[vout]")


def test_filtro_audio_silencia_la_musica_antes_de_su_capa():
    est = cargar_estilo(None)
    a = filtro_audio(est, None, hay_musica=True, musica_desde=8.0)
    assert "volume=0:enable='lt(t,8.0000)'" in a


@pytest.mark.skipif(not HAY_FFMPEG, reason="requiere ffmpeg")
def test_render_antes_despues_llena_la_barra(tmp_path):
    from editar import main
    crudo, mus = tmp_path / "crudo.mp4", tmp_path / "mus.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:size=360x640:rate=30:d=5",
                    "-f", "lavfi", "-i", "sine=f=300:d=5", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(crudo)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=800:d=1", str(mus)], check=True)
    pal = [{"p": "hola", "ini": 0.2, "fin": 0.6}, {"p": "mundo", "ini": 2.2, "fin": 2.8}]
    (tmp_path / "p.json").write_text(json.dumps(pal), encoding="utf-8")
    (tmp_path / "mini.json").write_text(json.dumps({"salida": {"ancho": 270, "alto": 480, "preset": "ultrafast"}}),
                                        encoding="utf-8")
    (tmp_path / "textos.json").write_text(json.dumps(
        {"titulos": [{"chico": "prueba de", "grande": "capas", "ini": 0, "fin": 5}]}), encoding="utf-8")
    sal = tmp_path / "ad.mp4"
    rc = main(["antes-despues", str(crudo), "--salida", str(sal), "--trabajo", str(tmp_path / "tr"),
               "--palabras", str(tmp_path / "p.json"), "--estilo", str(tmp_path / "mini.json"),
               "--textos", str(tmp_path / "textos.json"), "--musica", str(mus), "--sin-cortes"])
    assert rc == 0 and sal.exists()
    est = cargar_estilo(str(tmp_path / "mini.json"))
    ad = est["antes_despues"]
    k = 270 / 1080
    xb = int((540 + 14) * k)
    yb = int((1920 * ad["barra_y"] + ad["bloque_alto"] / 2) * k)

    def px(t, x, y):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(sal), "-frames:v", "1",
                              "-vf", f"format=rgb24,crop=1:1:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True).stdout
        return tuple(raw[:3])
    r, g, b = px(0.3, xb, yb)
    assert r > 170 and g < 90 and b < 90, (r, g, b)             # bajo el cabezal: Original (rojo)
    r, g, b = px(4.6, xb, yb)
    assert g > 170 and r < 120 and b < 120, (r, g, b)           # al final: Música y SFX (verde)
    r, g, b = px(0.3, 10, 10)
    assert min(r, g, b) > 220, (r, g, b)                         # fondo claro fuera de la tarjeta
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(sal)], capture_output=True, text=True).stdout)
    assert 4.8 < dur < 5.2, dur
