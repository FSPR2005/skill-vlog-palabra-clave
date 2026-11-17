import json
import math
import shutil
import subprocess

import pytest

from estilo import cargar_estilo

HAY_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _est(ancho=540, alto=960):
    est = cargar_estilo(None)
    est["salida"]["ancho"], est["salida"]["alto"] = ancho, alto
    return est


def _dispersion(im):
    """Distancia media al centro, pesada por alfa, y alfa total."""
    a = im.getchannel("A")
    w, h = a.size
    datos = a.load()
    tot = dist = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            v = datos[x, y]
            if v:
                tot += v
                dist += v * math.hypot(x - w / 2, y - h / 2)
    return (dist / tot if tot else 0), tot


def test_rafaga_sale_del_punto_se_abre_y_se_apaga():
    from graficos import cuadros_particulas
    est = _est()
    p = {"x": 0.5, "y": 0.6, "t": 2.0, "semilla": 3}
    cs = list(cuadros_particulas(p, est, 30))
    c = est["particulas"]
    assert len(cs) == round(c["dur"] * 30)
    lado = 2 * round(c["radio"] * 540 / 1080)
    assert cs[0].size == (lado, lado)
    d_ini, a_ini = _dispersion(cs[4])
    d_mid, a_mid = _dispersion(cs[len(cs) // 2])
    _, a_fin = _dispersion(cs[-1])
    assert a_ini > 0 and a_mid > 0
    assert d_mid > d_ini * 1.5                       # se alejan del punto
    assert a_fin < a_mid * 0.1                       # y se apagan al final


def test_misma_semilla_mismo_resultado():
    from graficos import cuadros_particulas
    est = _est()
    a = list(cuadros_particulas({"x": 0.5, "y": 0.5, "t": 0, "semilla": 1}, est, 30))[10].tobytes()
    b = list(cuadros_particulas({"x": 0.5, "y": 0.5, "t": 0, "semilla": 1}, est, 30))[10].tobytes()
    c = list(cuadros_particulas({"x": 0.5, "y": 0.5, "t": 0, "semilla": 2}, est, 30))[10].tobytes()
    assert a == b and a != c


def test_colores_pastel_de_la_paleta():
    from graficos import cuadros_particulas
    est = _est()
    im = list(cuadros_particulas({"x": 0.5, "y": 0.5, "t": 0, "semilla": 5}, est, 30))[8]
    pal = [tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) for h in est["particulas"]["colores"]]
    b = im.tobytes()
    opacos = [tuple(b[i:i + 3]) for i in range(0, len(b), 4) if b[i + 3] > 250]
    assert len(opacos) > 50
    cerca = sum(1 for px in opacos if min(sum(abs(a - b) for a, b in zip(px, q)) for q in pal) < 30)
    assert cerca / len(opacos) > 0.9


def test_sprite_centrado_en_el_punto_y_valida_el_segundo(tmp_path):
    from graficos import preparar_particulas
    est = _est()
    sp = preparar_particulas([{"x": 0.5, "y": 0.6, "t": 2.0}], est, str(tmp_path))[0]
    r = round(est["particulas"]["radio"] * 540 / 1080)
    assert (sp["x"], sp["y"]) == (270 - r, round(0.6 * 960) - r)
    assert sp["ini"] == 2.0 and sp["fin"] == pytest.approx(2.0 + est["particulas"]["dur"])
    with pytest.raises(ValueError, match="t"):
        preparar_particulas([{"x": 0.5, "y": 0.6}], est, str(tmp_path))


@pytest.mark.skipif(not HAY_FFMPEG, reason="requiere ffmpeg")
def test_render_con_particulas(tmp_path):
    from editar import main
    crudo = tmp_path / "crudo.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x202020:size=270x480:rate=30:d=3",
                    "-f", "lavfi", "-i", "sine=f=300:d=3", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(crudo)], check=True)
    (tmp_path / "mini.json").write_text(json.dumps({"salida": {"ancho": 270, "alto": 480, "preset": "ultrafast"},
                                                    "color": {"activar": False}}), encoding="utf-8")
    (tmp_path / "textos.json").write_text(json.dumps({"particulas": [{"x": 0.5, "y": 0.5, "t": 1.0}]}),
                                          encoding="utf-8")
    (tmp_path / "p.json").write_text("[]", encoding="utf-8")
    sal = tmp_path / "ed.mp4"
    assert main(["render", str(crudo), "--salida", str(sal), "--trabajo", str(tmp_path / "tr"), "--palabras",
                 str(tmp_path / "p.json"), "--estilo", str(tmp_path / "mini.json"),
                 "--textos", str(tmp_path / "textos.json")]) == 0

    def claros(t):
        px = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(sal), "-frames:v", "1", "-vf",
                             "crop=160:160:55:160", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            capture_output=True).stdout
        return sum(1 for i in range(0, len(px), 3) if max(px[i:i + 3]) > 120)
    assert claros(0.5) == 0
    assert claros(1.4) > 30                                   # estrellas de colores
    assert claros(2.6) == 0                                   # ya se fueron
