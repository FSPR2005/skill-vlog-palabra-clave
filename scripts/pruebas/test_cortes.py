import pytest

from cortes import calcular_tramos, mapear_tiempo, duracion_total, ajustar_a_cuadros


def P(*pares):
    return [{"p": f"w{i}", "ini": a, "fin": b} for i, (a, b) in enumerate(pares)]


def test_sin_palabras_deja_todo():
    assert calcular_tramos([], 10.0, silencio_max=0.3, margen_antes=0.05, margen_despues=0.1) == [(0.0, 10.0)]


def test_quita_silencio_largo_entre_frases():
    pal = P((1.0, 1.4), (1.5, 2.0), (4.0, 4.5))
    t = calcular_tramos(pal, 6.0, silencio_max=0.3, margen_antes=0.05, margen_despues=0.1)
    assert t == [(0.95, 2.1), (3.95, 4.6)]


def test_une_tramos_que_se_enciman_por_margen():
    pal = P((1.0, 1.4), (1.75, 2.0))  # hueco 0.35 > 0.3, pero con márgenes se enciman
    t = calcular_tramos(pal, 5.0, silencio_max=0.3, margen_antes=0.2, margen_despues=0.2)
    assert t == [(0.8, 2.2)]


def test_recorta_a_los_bordes_del_video():
    pal = P((0.02, 0.5), (9.9, 9.99))
    t = calcular_tramos(pal, 10.0, silencio_max=0.3, margen_antes=0.1, margen_despues=0.1)
    assert t[0][0] == 0.0 and t[-1][1] == 10.0


def test_mapear_tiempo_dentro_y_en_hueco():
    tramos = [(1.0, 2.0), (4.0, 5.0)]
    assert mapear_tiempo(1.5, tramos) == pytest.approx(0.5)
    assert mapear_tiempo(4.25, tramos) == pytest.approx(1.25)
    # en un hueco se pega al inicio del siguiente tramo
    assert mapear_tiempo(3.0, tramos) == pytest.approx(1.0)
    # después del final, al final
    assert mapear_tiempo(9.0, tramos) == pytest.approx(2.0)
    assert duracion_total(tramos) == pytest.approx(2.0)


def test_ajustar_a_cuadros_cae_en_la_rejilla_y_no_encima():
    t = ajustar_a_cuadros([(0.95, 2.1), (2.11, 3.0)], fps=30)
    for a, b in t:
        assert round(a * 30, 6) == int(round(a * 30)) and round(b * 30, 6) == int(round(b * 30))
        assert b > a
    for (a, b), (c, d) in zip(t, t[1:]):
        assert c >= b
