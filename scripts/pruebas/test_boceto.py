import json
import shutil
import subprocess
import sys

import pytest
from PIL import Image, ImageDraw

from estilo import cargar_estilo

HAY_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _cuadro():
    im = Image.new("RGB", (200, 300), (40, 40, 40))
    d = ImageDraw.Draw(im)
    d.rectangle([100, 0, 199, 299], fill=(200, 200, 200))     # una orilla vertical en x=100
    d.rectangle([60, 150, 140, 280], fill=(220, 30, 30))      # «la persona»
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rectangle([60, 150, 140, 280], fill=255)
    return im, m


def test_fondo_se_vuelve_dibujo_de_lineas_y_la_persona_queda_encima():
    from graficos import boceto_cuadro
    im, m = _cuadro()
    out = boceto_cuadro(im, m, cargar_estilo(None))
    assert out.size == im.size and out.mode == "RGB"
    assert min(out.getpixel((20, 20))) > 200                  # fondo liso -> papel claro
    assert min(out.getpixel((180, 20))) > 200
    linea = min(sum(out.getpixel((x, 20))) / 3 for x in range(95, 106))
    assert linea < 120, linea                                  # la orilla del fondo -> línea oscura
    r, g, b = out.getpixel((100, 215))
    assert r > 180 and g < 80                                  # la persona, tal cual


def test_mezcla_cero_deja_el_cuadro_original():
    from graficos import boceto_cuadro
    im, m = _cuadro()
    assert boceto_cuadro(im, m, cargar_estilo(None), mezcla=0).tobytes() == im.tobytes()


def test_mezcla_entra_y_sale_suave():
    from graficos import mezcla_boceto
    c = cargar_estilo(None)["boceto"]
    tr = c["transicion_ms"] / 1000
    assert mezcla_boceto(0, 3.0, c) == 0
    assert mezcla_boceto(tr / 2, 3.0, c) == pytest.approx(0.5)
    assert mezcla_boceto(1.5, 3.0, c) == 1
    assert mezcla_boceto(3.0, 3.0, c) == 0


def test_sin_mediapipe_ni_rembg_avisa_y_no_hay_segmentador(monkeypatch, capsys):
    import graficos
    monkeypatch.setitem(sys.modules, "mediapipe", None)
    monkeypatch.setitem(sys.modules, "rembg", None)
    assert graficos.cargar_segmentador(cargar_estilo(None)) is None
    assert "AVISO" in capsys.readouterr().out


def test_tramos_del_boceto_solo_los_que_toca():
    from graficos import tramos_de_intervalo
    tramos = [(0.0, 1.0), (2.0, 3.0), (5.0, 6.0), (8.0, 9.0)]     # en el editado: 0-1, 1-2, 2-3, 3-4
    sub, desde = tramos_de_intervalo(tramos, 1.5, 2.5)
    assert sub == [(2.0, 3.0), (5.0, 6.0)] and desde == pytest.approx(1.0)
    assert tramos_de_intervalo(None, 1.5, 2.5) == (None, 0.0)


def _crudo(tmp_path):
    crudo = tmp_path / "crudo.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=blue:size=270x480:rate=30:d=4,drawbox=x=0:y=0:w=135:h=480:color=yellow:t=fill",
                    "-f", "lavfi", "-i", "sine=f=300:d=4", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(crudo)], check=True)
    (tmp_path / "mini.json").write_text(json.dumps({"salida": {"ancho": 270, "alto": 480, "preset": "ultrafast"},
                                                    "color": {"activar": False}}), encoding="utf-8")
    (tmp_path / "textos.json").write_text(json.dumps({"boceto": [{"ini": 1.0, "fin": 3.0}]}), encoding="utf-8")
    (tmp_path / "p.json").write_text("[]", encoding="utf-8")
    return crudo


def _render(tmp_path, crudo, sal):
    from editar import main
    return main(["render", str(crudo), "--salida", str(sal), "--trabajo", str(tmp_path / "tr"), "--palabras",
                 str(tmp_path / "p.json"), "--estilo", str(tmp_path / "mini.json"),
                 "--textos", str(tmp_path / "textos.json")])


def _color_en(video, t, x, y):
    px = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-vf",
                         f"crop=2:2:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return tuple(px[:3])


@pytest.mark.skipif(not HAY_FFMPEG, reason="requiere ffmpeg")
def test_render_con_boceto_y_segmentador_de_prueba(tmp_path, monkeypatch):
    import graficos

    def falso(img):        # «la persona»: un rectángulo al centro
        m = Image.new("L", img.size, 0)
        w, h = img.size
        ImageDraw.Draw(m).rectangle([int(w * 0.55), int(h * 0.3), int(w * 0.8), int(h * 0.7)], fill=255)
        return m
    monkeypatch.setattr(graficos, "cargar_segmentador", lambda est: falso)
    crudo = _crudo(tmp_path)
    sal = tmp_path / "ed.mp4"
    assert _render(tmp_path, crudo, sal) == 0
    r, g, b = _color_en(sal, 0.5, 40, 70)
    assert b < 100 and r > 150, (r, g, b)                      # antes: fondo amarillo
    r, g, b = _color_en(sal, 2.0, 40, 70)
    assert min(r, g, b) > 190, (r, g, b)                       # boceto: papel claro
    r, g, b = _color_en(sal, 2.0, 180, 240)
    assert b > 150 and r < 100, (r, g, b)                      # la persona sigue igual (azul)
    r, g, b = _color_en(sal, 3.6, 40, 70)
    assert b < 100 and r > 150, (r, g, b)                      # después: vuelve el fondo real
    assert json.loads((tmp_path / "tr" / "apoyos.json").read_text(encoding="utf-8")) == []   # no cuenta como corte


@pytest.mark.skipif(not HAY_FFMPEG, reason="requiere ffmpeg")
def test_render_sin_segmentador_se_salta_el_boceto(tmp_path, monkeypatch, capsys):
    import graficos
    monkeypatch.setattr(graficos, "cargar_segmentador", lambda est: None)
    crudo = _crudo(tmp_path)
    sal = tmp_path / "ed.mp4"
    assert _render(tmp_path, crudo, sal) == 0
    assert "AVISO" in capsys.readouterr().out
    r, g, b = _color_en(sal, 2.0, 40, 70)
    assert b < 100 and r > 150, (r, g, b)                      # sin boceto: el fondo real
