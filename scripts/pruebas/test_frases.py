from estilo import cargar_estilo
from frases import agrupar_frases, elegir_clave, maquetar_frase, eventos_frases


def P(*items):
    return [{"p": p, "ini": a, "fin": b} for p, a, b in items]


def test_agrupar_corta_en_pausa_en_puntuacion_y_en_maximo():
    pal = P(("si", 0, .1), ("tu", .1, .2), ("sueño", .2, .5), ("es", .5, .6),
            ("ser", 1.2, 1.3), ("influencer.", 1.3, 1.8), ("Hola", 1.85, 2.0))
    fr = agrupar_frases(pal, max_palabras=4, pausa=0.35)
    assert [[w["p"] for w in f] for f in fr] == [["si", "tu", "sueño", "es"], ["ser", "influencer."], ["Hola"]]


def test_elegir_clave_respeta_lista_y_si_no_la_mas_larga_que_no_es_muletilla():
    fr = P(("si", 0, .1), ("tu", .1, .2), ("sueño", .2, .5), ("es", .5, .6))
    assert elegir_clave(fr, claves=None) == 2
    assert elegir_clave(fr, claves={"tu"}) == 1
    assert elegir_clave(P(("y", 0, .1), ("de", .1, .2)), claves=None) is None


def test_maquetar_clave_va_en_su_propia_linea_y_mas_grande():
    est = cargar_estilo(None)
    fr = P(("si", 0, .1), ("tu", .1, .2), ("sueño", .2, .5), ("es", .5, .6))
    m = maquetar_frase(fr, 2, est, variante=0, x0=100, y0=500)
    assert [x["texto"] for x in m] == ["si", "tu", "sueño", "es"]
    assert m[0]["y"] == m[1]["y"] and m[1]["x"] > m[0]["x"]          # misma línea
    assert m[2]["y"] > m[1]["y"] and m[2]["estilo"].startswith("Clave")  # clave abajo
    assert m[3]["y"] > m[2]["y"]                                       # sigue abajo
    assert all(x["x"] >= 0 and x["x"] < 1080 for x in m)


def test_eventos_aparecen_palabra_por_palabra_y_se_van_juntos():
    est = cargar_estilo(None)
    pal = P(("si", 0, .1), ("tu", .1, .2), ("sueño", .2, .5), ("ser", 1.2, 1.3))
    ev = eventos_frases(pal, est, claves=None)
    primera = [e for e in ev if e["fin"] <= 1.2 + 1e-6]
    assert [round(e["ini"], 2) for e in primera] == [0.0, 0.1, 0.2]
    assert len({e["fin"] for e in primera}) == 1
