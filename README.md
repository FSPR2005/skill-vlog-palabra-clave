# vlog-palabra-clave

Skill para [Claude Code](https://docs.claude.com/en/docs/claude-code) que edita un video crudo con el estilo de los
vlogs de estilo de vida de TikTok y Reels: le subes tu video y el agente te lo devuelve cortado, rotulado y con color,
listo para subir. Todo corre en tu computadora (tras bajar una vez el modelo de whisper) y es gratis: ffmpeg,
faster-whisper y Python.

> English summary at the end.

## Qué hace

| Efecto | Cómo lo hace |
|---|---|
| Cortes en salto: quita las pausas al hablar | tiempos por palabra de faster-whisper; corta silencios de más de 0.35 s (`cortes.silencio_max`) |
| Subtítulo de **una palabra**, chico y blanco, en el hueco sobre la cabeza | subtítulos ASS quemados con ffmpeg (libass) |
| **Palabras clave** grandes en color pastel con brillo suave | el agente las escoge del guion (una cada 5-8 s) |
| **Título de gancho** en dos tipos de letra: caligráfica chica + sans negrita grande | el agente lo escribe; sale desde el cuadro 0 |
| **Notas a mano** ("hola :)") giradas junto a la cabeza | fuente manuscrita libre |
| **Tomas de apoyo** de 0.6-1.0 s encima de la voz | si le das clips, se encadenan sin cortar el audio |
| Color luminoso, blancos suaves (~222/255), poca saturación, un poco cálido | mide TU video y lo lleva a esas métricas (no es un LUT ajeno) |
| Voz normalizada a -14 LUFS y tu música (si tienes derechos) debajo, con *ducking* | ffmpeg `loudnorm` + `sidechaincompress` |

Las medidas del estilo (ritmo de cortes, tamaños, posiciones, colores) y cómo se obtuvieron están en
[`recetas/ESTILO.md`](recetas/ESTILO.md). Todos los valores se cambian en [`estilo.json`](estilo.json).

## Requisitos

- Python 3.9 o más nuevo.
- ffmpeg con libass: Windows `winget install Gyan.FFmpeg`, Mac `brew install ffmpeg`, Linux `sudo apt install ffmpeg`.
  `python scripts/editar.py comprobar` dice si a tu ffmpeg le falta libass; en ese caso instala una compilación completa.
- `pip install -r requirements.txt` (faster-whisper, numpy, pillow; pytest solo para las pruebas).
- La primera transcripción descarga el modelo `small` de whisper (~480 MB) desde Hugging Face, una sola vez.
- Corre solo en CPU (no usa la GPU). Medido en una laptop: transcribir 35 s de video tomó 49 s (~0.7 GB de RAM) y
  renderizar 28 s a 1080x1920 con `--hilos 2`, ~90 s (~0.8 GB).

## Instalación en Claude Code

```bash
# para tu usuario (todas tus carpetas)
git clone https://github.com/<tu-usuario>/skill-vlog-palabra-clave ~/.claude/skills/vlog-palabra-clave
# o solo para un proyecto
git clone https://github.com/<tu-usuario>/skill-vlog-palabra-clave .claude/skills/vlog-palabra-clave

pip install -r ~/.claude/skills/vlog-palabra-clave/requirements.txt
python ~/.claude/skills/vlog-palabra-clave/scripts/editar.py comprobar
```

Si `python` o `pip` no existen, usa `python3` / `pip3` (Mac y Linux) o `py` (Windows).

Cambia `<tu-usuario>` por la cuenta donde esté publicado el repositorio. En Windows, `~` es `%USERPROFILE%`. Reinicia Claude Code y escribe, por ejemplo:
*"edita este video estilo vlog: <ruta de tu video>"*.

## Uso sin el agente (a mano)

```bash
python scripts/editar.py preparar crudo.mp4 --trabajo edicion          # transcribe y escribe edicion/guion.txt
# escribe edicion/textos.json (título, claves, notas, tomas de apoyo): ver SKILL.md, paso 3
python scripts/editar.py render crudo.mp4 --trabajo edicion --textos edicion/textos.json --salida editado.mp4
python scripts/revisar.py editado.mp4 --trabajo edicion               # hoja de cuadros y ritmo de cortes
```

Opciones útiles: `--estilo mio.json` (solo las claves que cambias), `--musica pista.mp3`, `--sin-cortes`, `--hasta 15`
(vista previa), `--modelo base` (máquinas lentas), `--hilos 2` (poca RAM).

## Pruebas

```bash
python -m pytest scripts/pruebas -q
```
Incluyen renders completos con videos sintéticos (necesitan ffmpeg).

## Límites

- No hace efectos de cara (ojos grandes), stickers animados, burbujas, destellos ni transiciones de la app.
- No inventa tomas de apoyo ni música. Sin tomas de apoyo, el ritmo depende de tus pausas (en la prueba, una voz de
  corrido: 17 cortes por minuto); el estilo completo, con tomas de apoyo, va de 30 a 70.
- whisper se equivoca con nombres propios: corrígelos en `palabras.json` antes del render final.
- Un video horizontal se recorta al centro para 9:16.
- Copiar un estilo no garantiza alcance; lo que miden las plataformas es que el video se vea completo.

## Licencias

Código: MIT ([LICENSE](LICENSE)). Fuentes en `fuentes/`: Poppins, Great Vibes y Gochi Hand, todas bajo la SIL Open Font
License 1.1 (textos en `fuentes/OFL-*.txt`). Este repositorio no incluye videos, cuadros, audio ni marcas de terceros:
las recetas describen técnicas medidas, no material de nadie.

---

## English summary

**vlog-palabra-clave** is a Claude Code skill that edits a raw talking video into the bright lifestyle-vlog look common
on TikTok/Reels: jump cuts that remove pauses (faster-whisper word timings), one small white word on screen at a time
above the head, big pastel keywords with a soft glow, a two-font hook title (script + bold sans) from frame 0,
handwritten notes, optional B-roll inserts of 0.6-1.0 s over the voice, and an automatic color match toward soft highlights
and low saturation. Everything runs locally and for free (ffmpeg + faster-whisper + Python) on Windows, macOS and Linux;
all parameters live in `estilo.json`.

Install: clone into `~/.claude/skills/vlog-palabra-clave`, `pip install -r requirements.txt`, install ffmpeg, then run
`python scripts/editar.py comprobar`. Ask Claude Code to "edit this video in vlog style". Manual use: `editar.py preparar`,
write `textos.json`, `editar.py render`, `revisar.py`. Limits: no face effects, stickers or app transitions; it does not
invent B-roll or music. Code under MIT; bundled fonts under SIL OFL 1.1.
