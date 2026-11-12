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


def test_resumen_suma_los_cortes_de_las_tomas_de_apoyo():
    t = {"duracion_cruda": 60.0, "duracion_editada": 60.0, "tramos": [[0, 60]]}
    apoyos = [{"ini": 10, "fin": 10.7}, {"ini": 10.7, "fin": 11.5}, {"ini": 30, "fin": 31}]
    r = resumen_tramos(t, apoyos)
    # entra 10, cambia 10.7, sale 11.5, entra 30, sale 31 => 5 cortes
    assert r["cortes"] == 5
