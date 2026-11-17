import json
import re
import shutil
import subprocess

import pytest
from PIL import Image

from estilo import cargar_estilo

HAY_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _est(ancho=1080, alto=1920):
    est = cargar_estilo(None)
    est["salida"]["ancho"], est["salida"]["alto"] = ancho, alto
    return est


def test_mascara_redondeada_transparente_en_las_esquinas():
    from graficos import mascara_redondeada
    m = mascara_redondeada(200, 300, 40)
    assert m.size == (200, 300)
    assert m.getpixel((1, 1)) < 30 and m.getpixel((198, 298)) < 30
    assert m.getpixel((100, 150)) == 255 and m.getpixel((100, 1)) > 200


def _choca(caja, cara, W, H):
    x0, y0, x1, y1 = caja
    return not (x1 <= cara["x"][0] * W or x0 >= cara["x"][1] * W or y1 <= cara["y"][0] * H or y0 >= cara["y"][1] * H)


def test_lugares_por_omision_rodean_a_la_persona_sin_taparle_la_cara():
    from graficos import cajas_flotantes
    est = _est()
    fl = [{"archivo": "x.mp4", "ini": 1, "fin": 3} for _ in range(4)]
    cajas = cajas_flotantes(fl, est)
    cara = est["flotantes"]["cara"]
    assert len({c[:2] for c in cajas}) == 4
    for c in cajas:
        assert 0 <= c[0] and c[2] <= 1080 and 0 <= c[1] and c[3] <= 1920
        assert not _choca(c, cara, 1080, 1920), c


def test_mas_de_cuatro_flotantes_da_error():
    from graficos import preparar_flotantes
    with pytest.raises(ValueError, match="4"):
        preparar_flotantes([{"archivo": "x.mp4", "ini": 1, "fin": 2}] * 5, _est(), ".")


def test_avisa_si_un_flotante_tapa_la_cara(capsys):
    from graficos import cajas_flotantes
    cajas_flotantes([{"archivo": "x.mp4", "ini": 1, "fin": 3, "x": 0.5, "y": 0.45}], _est())
    assert "AVISO" in capsys.readouterr().out


def test_los_que_entran_juntos_se_escalonan():
    from graficos import retrasos_flotantes
    est = _est()
    paso = est["flotantes"]["escalonado_ms"] / 1000
    fl = [{"ini": 2.0}, {"ini": 2.0}, {"ini": 5.0}, {"ini": 2.0}]
    assert retrasos_flotantes(fl, est) == pytest.approx([0, paso, 0, 2 * paso])


def test_cuadros_de_un_flotante_repiten_el_ultimo_si_el_clip_es_corto():
    from graficos import cuadros_flotante
    est = _est(540, 960)
    w, h = 140, 186
    clip = [Image.new("RGB", (w, h), (255, 0, 0)) for _ in range(10)]
    f = {"archivo": "x.mp4", "ini": 0, "fin": 1.0}
    cs = list(cuadros_flotante(f, est, 30, iter(clip), (w, h)))
    assert len(cs) == 30
    mid = cs[20]
    cx, cy = mid.width // 2, mid.height // 2
    r, g, b, a = mid.getpixel((cx, cy))
    assert r > 200 and g < 40 and a > 240                  # el clip, opaco, aunque ya se acabó (último cuadro)
    assert cs[0].getchannel("A").getextrema()[1] == 0       # el primer cuadro aún no se ve (entra con pop)


@pytest.mark.skipif(not HAY_FFMPEG, reason="requiere ffmpeg")
def test_render_con_flotante_y_la_voz_sigue(tmp_path):
    from editar import main
    crudo, clip = tmp_path / "crudo.mp4", tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:size=270x480:rate=30:d=4",
                    "-f", "lavfi", "-i", "sine=f=300:d=4", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(crudo)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:size=320x240:rate=30:d=1.5",
                    "-f", "lavfi", "-i", "sine=f=900:d=1.5", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(clip)], check=True)
    (tmp_path / "mini.json").write_text(json.dumps({"salida": {"ancho": 270, "alto": 480, "preset": "ultrafast"},
                                                    "color": {"activar": False}}), encoding="utf-8")
    (tmp_path / "textos.json").write_text(json.dumps({"flotantes": [
        {"archivo": "clip.mp4", "ini": 1.0, "fin": 3.0, "x": 0.2, "y": 0.7}]}), encoding="utf-8")
    (tmp_path / "p.json").write_text("[]", encoding="utf-8")
    sal = tmp_path / "ed.mp4"
    assert main(["render", str(crudo), "--salida", str(sal), "--trabajo", str(tmp_path / "tr"), "--palabras",
                 str(tmp_path / "p.json"), "--estilo", str(tmp_path / "mini.json"),
                 "--textos", str(tmp_path / "textos.json")]) == 0

    def color_en(t, x, y):
        px = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(sal), "-frames:v", "1", "-vf",
                             f"crop=2:2:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            capture_output=True).stdout
        return tuple(px[:3])
    cx, cy = int(0.2 * 270), int(0.7 * 480)
    assert color_en(0.5, cx, cy)[2] > 150                   # antes: azul
    r, g, b = color_en(2.5, cx, cy)
    assert r > 150 and b < 100, (r, g, b)                    # durante: el clip (rojo), ya en su último cuadro
    assert color_en(3.6, cx, cy)[2] > 150                   # después: azul otra vez
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration",
                                      "-of", "json", str(sal)], capture_output=True, text=True).stdout)
    d = {s["codec_type"]: float(s["duration"]) for s in info["streams"]}
    assert 3.8 < d["audio"] < 4.2, d                         # la voz no se corta
    vol = subprocess.run(["ffmpeg", "-v", "info", "-ss", "1.2", "-t", "1.5", "-i", str(sal), "-af", "volumedetect",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    media = float(re.search(r"mean_volume: (-?[\d.]+) dB", vol).group(1))
    assert media > -40, media                                 # mientras flota, se sigue oyendo la voz
