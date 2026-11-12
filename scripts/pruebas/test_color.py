import shutil
import subprocess

import pytest

from color import ajuste_color, medir_color

OBJ = {"luma": 128, "saturacion": 50, "negro": 12, "blanco": 222, "calidez": 20}


def _valores(f):
    out = {}
    for parte in f.split(","):
        for kv in parte.split("=", 1)[1].split(":") if "=" in parte else []:
            if "=" in kv:
                k, v = kv.split("=")
                out[parte.split("=")[0] + "." + k] = float(v)
    return out


def test_video_oscuro_y_saturado_se_aclara_y_se_desatura():
    f = ajuste_color({"luma": 80, "saturacion": 110, "negro": 5, "blanco": 250, "calidez": 20}, OBJ)
    v = _valores(f)
    assert v["eq.gamma"] > 1.0 and v["eq.saturation"] < 1.0
    # los blancos se bajan a ~222: la salida máxima queda debajo de 1
    assert v["colorlevels.romax"] == pytest.approx(222 / 255, abs=0.01)


def test_video_ya_parecido_casi_no_cambia():
    f = ajuste_color(dict(OBJ), OBJ)
    v = _valores(f)
    assert v["eq.gamma"] == pytest.approx(1.0, abs=0.03)
    assert v["eq.saturation"] == pytest.approx(1.0, abs=0.03)


def test_los_ajustes_tienen_tope():
    v = _valores(ajuste_color({"luma": 10, "saturacion": 2, "negro": 0, "blanco": 30, "calidez": -60}, OBJ))
    assert 0.75 <= v["eq.gamma"] <= 1.35 and 0.6 <= v["eq.saturation"] <= 1.4
    assert abs(v["colorbalance.rm"]) <= 0.12


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="requiere ffmpeg")
def test_medir_color_de_un_video_gris(tmp_path):
    v = tmp_path / "gris.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x808080:size=160x284:rate=10:d=2",
                    "-pix_fmt", "yuv420p", str(v)], check=True)
    m = medir_color(str(v), muestras=3)
    assert 120 < m["luma"] < 136 and m["saturacion"] < 5
