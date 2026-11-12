import json

import pytest

from estilo import cargar_estilo, ESTILO_BASE


def test_sin_archivo_usa_el_estilo_del_repo():
    e = cargar_estilo(None)
    assert e["salida"]["ancho"] == 1080 and e["salida"]["alto"] == 1920
    assert e["subtitulos"]["modo"] in ("frases", "palabra")


def test_archivo_parcial_se_mezcla_con_la_base(tmp_path):
    f = tmp_path / "mio.json"
    f.write_text(json.dumps({"subtitulos": {"frases": {"color": "#FFEE00"}}}), encoding="utf-8")
    e = cargar_estilo(str(f))
    assert e["subtitulos"]["frases"]["color"] == "#FFEE00"
    base = json.load(open(ESTILO_BASE, encoding="utf-8"))
    assert e["subtitulos"]["frases"]["fuente"] == base["subtitulos"]["frases"]["fuente"]


def test_clave_desconocida_se_rechaza(tmp_path):
    f = tmp_path / "mal.json"
    f.write_text(json.dumps({"subtitulos": {"colr": "#fff"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="colr"):
        cargar_estilo(str(f))
