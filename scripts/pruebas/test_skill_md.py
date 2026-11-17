import os
import re

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _skill():
    with open(os.path.join(RAIZ, "SKILL.md"), encoding="utf-8") as f:
        return f.read()


def _regla_gancho():
    m = re.search(r"^- \*\*Gancho con cifra[^\n]*(?:\n  [^\n]*)*", _skill(), re.M)
    assert m, "falta la regla «Gancho con cifra» en el paso 3 de SKILL.md"
    return m.group(0)


def test_regla_de_gancho_pide_pregunta_y_cifra_antes_de_8_s():
    r = _regla_gancho().lower()
    assert "pregunta" in r and "cifra" in r and "8 s" in r


def test_regla_de_gancho_exige_cifra_verdadera_y_verificable():
    r = _regla_gancho().lower()
    assert "verdadera" in r and "verificable" in r
    assert "no la inventes" in r or "nada inventado" in r
    assert "fuente" in r                     # de dónde sale la cifra


def test_skill_documenta_los_modos_nuevos():
    s = _skill()
    assert "antes-despues" in s and "antes_despues" in s
    assert '"resaltar"' in s


def _readme():
    with open(os.path.join(RAIZ, "README.md"), encoding="utf-8") as f:
        return f.read()


def test_skill_documenta_las_mejoras_v2_y_su_medida():
    s = _skill()
    for clave in ('"tarjetas"', '"flotantes"', '"boceto"', '"particulas"'):
        assert clave in s, clave
    assert re.search(r"una tarjeta cada 5-8 s", s, re.I)
    assert "rembg" in s and "mediapipe" in s


def test_readme_tabla_y_limites_de_las_mejoras_v2():
    r = _readme()
    que_hace = r[r.index("## Qué hace"):r.index("## Requisitos")]
    for palabra in ("Tarjetas", "flotantes", "boceto", "estrellas"):
        assert palabra.lower() in que_hace.lower(), palabra
    limites = r[r.index("## Límites"):r.index("## Licencias")]
    assert "segmenta" in limites.lower() and "RAM" in r
