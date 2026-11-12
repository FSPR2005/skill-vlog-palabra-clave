from textos import bloques_de_palabras, limpiar_palabra, tiempo_ass, generar_ass, color_ass
from estilo import cargar_estilo


def P(*items):
    return [{"p": p, "ini": a, "fin": b} for p, a, b in items]


def test_limpiar_palabra_quita_puntuacion_y_baja():
    assert limpiar_palabra("¿Hola,", minusculas=True) == "hola"
    assert limpiar_palabra("¡ESO!", minusculas=False) == "ESO"
    assert limpiar_palabra("...", minusculas=True) == ""


def test_bloques_de_una_palabra_duran_hasta_la_siguiente():
    b = bloques_de_palabras(P(("hola", 0.0, 0.3), ("a", 0.35, 0.4), ("todos", 0.5, 0.9)), 1, hueco_max=0.4)
    assert [x["texto"] for x in b] == ["hola", "a", "todos"]
    assert b[0]["fin"] == 0.35  # se queda en pantalla hasta que entra la siguiente
    assert b[-1]["fin"] == 0.9


def test_bloques_no_tapan_silencios_largos():
    b = bloques_de_palabras(P(("uno", 0.0, 0.3), ("dos", 2.0, 2.3)), 1, hueco_max=0.4)
    assert b[0]["fin"] == 0.3 + 0.4


def test_bloques_de_dos():
    b = bloques_de_palabras(P(("si", 0, .2), ("tu", .2, .4), ("sueño", .4, .9)), 2, hueco_max=0.4)
    assert [x["texto"] for x in b] == ["si tu", "sueño"]


def test_tiempo_y_color_ass():
    assert tiempo_ass(3661.239) == "1:01:01.24"
    assert color_ass("#F4F0A8") == "&H00A8F0F4"


def test_generar_ass_tiene_estilos_palabras_y_titulo():
    est = cargar_estilo(None)
    est["subtitulos"]["modo"] = "frases"
    ass = generar_ass(P(("hola", 0.5, 0.8), ("mundo", 0.9, 1.2)), est,
                      titulos=[{"chico": "abrimos los", "grande": "regalos", "ini": 0.0, "fin": 2.5}],
                      notas=[{"texto": "hola :)", "ini": 0.0, "fin": 1.0}])
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    for st in ("Palabra", "Frase", "Clave0", "Clave1", "TituloChico", "TituloGrande", "Nota"):
        assert f"Style: {st}," in ass, st
    assert ",Frase,," in ass and ",Clave0,," in ass and "hola" in ass and "mundo" in ass
    assert "regalos" in ass and "abrimos los" in ass and "hola :)" in ass
    # mientras está el título, las palabras siguen saliendo (son capas distintas)
    assert ass.count("Dialogue:") == 5


def test_tramo_de_palabra_suelta_usa_el_otro_modo():
    est = cargar_estilo(None)
    est["subtitulos"]["modo"] = "frases"
    pal = P(("hola", 0.5, 0.8), ("mundo", 0.9, 1.2), ("otra", 3.0, 3.3), ("cosa", 3.4, 3.8))
    ass = generar_ass(pal, est, palabra_suelta=[[2.5, 5.0]])
    lineas = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert sum(",Palabra,," in l for l in lineas) == 2
    assert sum(",Palabra,," not in l for l in lineas) == 2


def test_modo_palabra_pinta_las_claves_con_su_estilo_y_brillo():
    est = cargar_estilo(None)
    est["subtitulos"]["modo"] = "palabra"
    pal = P(("buscando", 0.5, 0.9), ("una", 1.0, 1.1), ("marca", 1.2, 1.6))
    ass = generar_ass(pal, est, claves=["buscando"])
    lineas = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert ",Clave0,," in lineas[0] and "\\blur" in lineas[0]
    assert all(",Palabra,," in l for l in lineas[1:])


def test_posiciones_tambien_mueven_la_palabra_suelta():
    est = cargar_estilo(None)
    est["subtitulos"]["modo"] = "palabra"
    pal = P(("arriba", 0.5, 0.9), ("abajo", 3.0, 3.4))
    ass = generar_ass(pal, est, posiciones=[{"ini": 2.0, "fin": 5.0, "x": 0.5, "y": 0.85}])
    lineas = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert "\pos(540,576)" in lineas[0]
    assert "\pos(540,1632)" in lineas[1]
