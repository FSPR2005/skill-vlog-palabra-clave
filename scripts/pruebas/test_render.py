import json
import shutil
import subprocess

import pytest

from estilo import cargar_estilo
from render import expresion_seleccion, filtro_video, filtro_audio

HAY_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def test_expresion_seleccion_usa_indices_de_cuadro():
    e = expresion_seleccion([(1.0, 2.0), (3.5, 4.0)], fps=30)
    assert e == "between(n,30,59)+between(n,105,119)"


def test_filtro_video_lleva_encuadre_cortes_color_y_texto():
    est = cargar_estilo(None)
    est["color"]["modo"] = "fijo"
    f = filtro_video(est, [(0.0, 1.0), (2.0, 3.0)], "textos.ass", "fuentes")
    for pieza in ("fps=30", "crop=1080:1920", "select=", "setpts=N/30/TB", "eq=", "ass=textos.ass", "fontsdir=fuentes"):
        assert pieza in f, pieza


def test_filtro_video_usa_el_color_automatico_si_se_lo_dan():
    est = cargar_estilo(None)
    f = filtro_video(est, None, None, None, color_filtro="colorlevels=rimin=0.1,eq=gamma=1.1")
    assert "colorlevels=rimin=0.1,eq=gamma=1.1" in f and "brightness" not in f


def test_filtro_video_sin_cortes_ni_color():
    est = cargar_estilo(None)
    est["color"]["activar"] = False
    f = filtro_video(est, None, None, None)
    assert "select=" not in f and "eq=" not in f and "ass=" not in f


def test_filtro_audio_con_y_sin_musica():
    est = cargar_estilo(None)
    sin = filtro_audio(est, [(0.0, 1.0)], hay_musica=False)
    assert "asetnsamples=n=1600:p=0" in sin
    assert "aselect=" in sin and "loudnorm" in sin and "[aout]" in sin and "sidechaincompress" not in sin
    con = filtro_audio(est, [(0.0, 1.0)], hay_musica=True)
    assert "[1:a]" in con and "sidechaincompress" in con and "amix" in con


@pytest.mark.skipif(not HAY_FFMPEG, reason="requiere ffmpeg")
def test_render_completo_con_video_sintetico(tmp_path):
    from editar import main
    crudo = tmp_path / "crudo.mp4"
    # 6 s: voz (tono) de 0.5 a 1.5 y de 4.0 a 5.0, silencio en medio
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30:duration=6",
                    "-f", "lavfi", "-i",
                    "aevalsrc='if(between(t,0.5,1.5)+between(t,4,5),0.3*sin(2*PI*440*t),0)':s=48000:d=6",
                    "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(crudo)], check=True)
    pal = [{"p": "hola", "ini": 0.5, "fin": 1.0}, {"p": "todos", "ini": 1.05, "fin": 1.5},
           {"p": "adiós", "ini": 4.0, "fin": 5.0}]
    (tmp_path / "palabras.json").write_text(json.dumps(pal), encoding="utf-8")
    (tmp_path / "mini.json").write_text(json.dumps({"salida": {"ancho": 270, "alto": 480, "preset": "ultrafast"}}),
                                        encoding="utf-8")
    (tmp_path / "textos.json").write_text(json.dumps(
        {"titulos": [{"chico": "prueba de", "grande": "estilo", "ini": 0, "fin": 1}],
         "notas": [{"texto": "hola :)", "ini": 0, "fin": 0.8}]}), encoding="utf-8")
    sal = tmp_path / "editado.mp4"
    rc = main(["render", str(crudo), "--salida", str(sal), "--trabajo", str(tmp_path / "trabajo"),
               "--palabras", str(tmp_path / "palabras.json"), "--estilo", str(tmp_path / "mini.json"),
               "--textos", str(tmp_path / "textos.json")])
    assert rc == 0 and sal.exists()
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_type",
                                      "-of", "json", str(sal)], capture_output=True, text=True).stdout)
    dur = float(info["format"]["duration"])
    # se quedan ~0.45-1.62 y ~3.95-5.12 => ~2.33 s de 6
    assert 2.1 < dur < 2.6, dur
    v = [s for s in info["streams"] if s["codec_type"] == "video"][0]
    assert (v["width"], v["height"]) == (270, 480)
    assert any(s["codec_type"] == "audio" for s in info["streams"])
    assert (tmp_path / "trabajo" / "guion.txt").exists()


def test_filtro_video_con_tomas_de_apoyo_encima():
    est = cargar_estilo(None)
    f = filtro_video(est, [(0.0, 5.0)], "textos.ass", "fuentes", apoyos=[(2, 1.0, 1.8), (3, 3.0, 3.6)])
    assert f.count("overlay=") == 2
    assert "[2:v]" in f and "[3:v]" in f
    assert "setpts=PTS-STARTPTS+1.0000/TB" in f
    # el texto va encima de las tomas de apoyo: ass después del último overlay
    assert f.index("ass=") > f.rindex("overlay=")


@pytest.mark.skipif(not HAY_FFMPEG, reason="requiere ffmpeg")
def test_render_con_toma_de_apoyo_y_musica(tmp_path):
    from editar import main
    crudo, apoyo, mus = tmp_path / "crudo.mp4", tmp_path / "apoyo.mp4", tmp_path / "mus.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:size=360x640:rate=30:d=4",
                    "-f", "lavfi", "-i", "sine=f=300:d=4", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(crudo)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:size=640x360:rate=30:d=3",
                    "-c:v", "libx264", "-preset", "ultrafast", str(apoyo)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=800:d=1", str(mus)], check=True)
    (tmp_path / "mini.json").write_text(json.dumps({"salida": {"ancho": 270, "alto": 480, "preset": "ultrafast"},
                                                    "color": {"activar": False}}), encoding="utf-8")
    (tmp_path / "textos.json").write_text(json.dumps({"apoyos": [{"archivo": "apoyo.mp4", "ini": 1.0, "fin": 2.0}]}),
                                          encoding="utf-8")
    (tmp_path / "vacio.json").write_text("[]", encoding="utf-8")
    sal = tmp_path / "ed.mp4"
    rc = main(["render", str(crudo), "--salida", str(sal), "--trabajo", str(tmp_path / "tr"), "--palabras",
               str(tmp_path / "vacio.json"), "--estilo", str(tmp_path / "mini.json"),
               "--textos", str(tmp_path / "textos.json"), "--musica", str(mus)])
    assert rc == 0

    def color_en(t):
        px = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(sal), "-frames:v", "1", "-vf",
                             "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        return tuple(px[:3])
    r, g, b = color_en(1.5)
    assert r > 150 and b < 100, (r, g, b)          # durante el apoyo se ve el rojo
    r, g, b = color_en(3.0)
    assert b > 150 and r < 100, (r, g, b)          # después vuelve el crudo azul
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(sal)], capture_output=True, text=True).stdout)
    assert 3.8 < dur < 4.2, dur


@pytest.mark.skipif(not HAY_FFMPEG, reason="requiere ffmpeg")
def test_cuarenta_cortes_no_desfasan_audio_y_video(tmp_path):
    from editar import main
    crudo = tmp_path / "crudo.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=180x320:rate=30:duration=40",
                    "-f", "lavfi", "-i", "sine=f=440:d=40", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(crudo)], check=True)
    # 40 palabras de 0.5 s separadas por 0.5 s de silencio => 40 tramos
    pal = [{"p": f"p{i}", "ini": i + 0.07, "fin": i + 0.53} for i in range(40)]
    (tmp_path / "p.json").write_text(json.dumps(pal), encoding="utf-8")
    (tmp_path / "mini.json").write_text(json.dumps({"salida": {"ancho": 180, "alto": 320, "preset": "ultrafast"},
                                                    "color": {"activar": False},
                                                    "subtitulos": {"activar": False}}), encoding="utf-8")
    sal = tmp_path / "ed.mp4"
    assert main(["render", str(crudo), "--salida", str(sal), "--trabajo", str(tmp_path / "tr"), "--palabras",
                 str(tmp_path / "p.json"), "--estilo", str(tmp_path / "mini.json")]) == 0
    esperado = json.loads((tmp_path / "tr" / "tramos.json").read_text(encoding="utf-8"))["duracion_editada"]
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration",
                                      "-of", "json", str(sal)], capture_output=True, text=True).stdout)
    d = {s["codec_type"]: float(s["duration"]) for s in info["streams"]}
    assert abs(d["video"] - esperado) <= 1 / 30 + 1e-3, (d, esperado)
    assert abs(d["audio"] - d["video"]) <= 1 / 30 + 0.03, d


def test_hdr_se_lleva_a_bt709():
    est = cargar_estilo(None)
    f = filtro_video(est, None, None, None, hdr=True)
    assert "tonemap" in f and f.index("tonemap") < f.index("crop=")


@pytest.mark.skipif(not HAY_FFMPEG, reason="requiere ffmpeg")
def test_toma_de_apoyo_relativa_a_la_carpeta_actual(tmp_path, monkeypatch):
    from editar import main
    clips = tmp_path / "clips"
    clips.mkdir()
    crudo, apoyo = tmp_path / "crudo.mp4", clips / "apoyo.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:size=180x320:rate=30:d=3",
                    "-f", "lavfi", "-i", "sine=d=3", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    str(crudo)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:size=180x320:rate=30:d=2",
                    "-c:v", "libx264", "-preset", "ultrafast", str(apoyo)], check=True)
    otra = tmp_path / "otra"
    otra.mkdir()
    (otra / "textos.json").write_text(json.dumps({"apoyos": [{"archivo": "apoyo.mp4", "ini": 1, "fin": 2}]}),
                                      encoding="utf-8")
    (otra / "mini.json").write_text(json.dumps({"salida": {"ancho": 180, "alto": 320, "preset": "ultrafast"},
                                                "color": {"activar": False}}), encoding="utf-8")
    (otra / "p.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(clips)
    assert main(["render", str(crudo), "--salida", str(tmp_path / "ed.mp4"), "--trabajo", str(tmp_path / "tr"),
                 "--palabras", str(otra / "p.json"), "--estilo", str(otra / "mini.json"),
                 "--textos", str(otra / "textos.json")]) == 0


def test_fps_que_no_divide_48000_da_mensaje_claro():
    from render import muestras_por_cuadro
    with pytest.raises(ValueError, match="48000"):
        muestras_por_cuadro(29.97)
