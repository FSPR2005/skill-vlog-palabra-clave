import json
import shutil
import subprocess

import pytest

from revisar import resumen_tramos, hoja_de_cuadros


def test_resumen_tramos_da_cortes_por_minuto_y_mediana():
    r = resumen_tramos({"duracion_cruda": 20.0, "duracion_editada": 12.0,
                        "tramos": [[0, 2], [3, 6], [7, 9], [10, 15]]})
    assert r["cortes"] == 3
    assert r["cortes_por_minuto"] == pytest.approx(3 / 12 * 60)
    assert r["mediana_entre_cortes"] == pytest.approx(2.5)
    assert r["recorte"] == pytest.approx(0.4)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="requiere ffmpeg")
def test_hoja_de_cuadros_sale(tmp_path):
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=180x320:rate=30:d=3",
                    "-pix_fmt", "yuv420p", str(v)], check=True)
    sal = tmp_path / "hoja.jpg"
    hoja_de_cuadros(str(v), str(sal), cada=1.0)
    assert sal.exists() and sal.stat().st_size > 1000
