---
name: vlog-palabra-clave
description: Edita un video crudo (vertical u horizontal) con el estilo de vlog de estilo de vida que se ve en TikTok y Reels - cortes en salto que quitan las pausas, subtítulo de UNA palabra chica y blanca en el hueco sobre la cabeza, palabras clave grandes en color pastel con brillo suave, título de gancho en dos tipos de letra (caligráfica chica + sans negrita grande), notas escritas a mano, tomas de apoyo de 0.6-1.0 s y color luminoso con blancos suaves. Todo local y gratis (ffmpeg + faster-whisper), en Windows, Mac o Linux, con los parámetros en estilo.json. Úsala cuando el usuario diga "edita este video", "edítalo estilo vlog", "ponle subtítulos palabra por palabra", "quita las pausas y ponle textos", "edítalo como TikTok de lifestyle", "edita mi unboxing / haul / vlog / reseña", "déjalo listo para Reels", o suba un video crudo pidiendo editarlo con ese estilo.
---

# Vlog con palabra clave

Tú (el agente) haces lo que pide criterio: leer el guion, escoger las palabras clave, escribir el título del gancho y
revisar los cuadros. Los scripts hacen lo mecánico: transcribir, cortar, rotular, dar color y renderizar en UNA pasada de
ffmpeg. Las medidas del estilo y de dónde salen están en `recetas/ESTILO.md`; los valores, en `estilo.json`.

Rutas: `<skill>` es la carpeta de esta skill. Trabaja en una carpeta junto al video del usuario, nunca dentro de `<skill>`.

## 0. Antes de empezar (máximo 2 preguntas, en una sola vez, y solo si no lo dijo)

1. ¿Tienes tomas de apoyo (clips del producto, del lugar) o música propia o con licencia? Si no, se edita solo con el crudo.
2. ¿En qué idioma habla? (si no lo dice, whisper lo detecta).

## 1. Requisitos

`python <skill>/scripts/editar.py comprobar` → dice qué falta (ffmpeg con libass, faster-whisper, fuentes).
Instalar: `pip install -r <skill>/requirements.txt` y ffmpeg (Windows: `winget install Gyan.FFmpeg`; Mac: `brew install ffmpeg`;
Linux: `sudo apt install ffmpeg`). Si `comprobar` dice que a tu ffmpeg le falta libass, instala una compilación completa.
La primera transcripción baja el modelo `small` de whisper (~480 MB) una sola vez.

## 2. Preparar: transcribir y calcular cortes

```
python <skill>/scripts/editar.py preparar crudo.mp4 --trabajo edicion
```
Deja en `edicion/`: `palabras.json` (tiempos por palabra del crudo; con `--desde`/`--hasta`, `palabras_<desde>-<hasta>.json`), `tramos.json` (lo que se queda), `guion.txt` (frases con su
segundo YA en el video editado). Lee `guion.txt` completo antes del paso 3.
Si el video es largo (más de 3 min) o la máquina tiene poca RAM, trabaja por partes con `--desde`/`--hasta`
(transcribe y corta solo ese tramo) y `--hilos 2`.

## 3. Escribir `edicion/textos.json` (tu trabajo, con los tiempos de `guion.txt`)

```json
{
  "titulos": [{"chico": "abrimos los", "grande": "regalos sorpresa", "ini": 0.0, "fin": 2.4}],
  "notas": [{"texto": "hola :)", "ini": 0.0, "fin": 1.2, "posicion_x": 0.35, "posicion_y": 0.3}],
  "claves": ["sorpresa", "veinte", "favorito"],
  "palabra_suelta": [[6.2, 8.0]],
  "posiciones": [{"ini": 12.0, "fin": 15.5, "x": 0.5, "y": 0.85}],
  "apoyos": [{"archivo": "apoyo1.mp4", "desde": 0.0, "ini": 6.2, "fin": 6.9},
             {"archivo": "apoyo2.mp4", "desde": 3.0, "ini": 6.9, "fin": 8.0}]
}
```

Todos los tiempos (`ini`, `fin`, rangos `[ini, fin]`) son segundos del video YA editado, como en `guion.txt`.
`apoyos.desde` es el segundo dentro del clip de apoyo; `archivo` es relativo a la carpeta actual o, si no está ahí,
a la carpeta de `textos.json`. Todo es opcional: un `{}` deja solo cortes, subtítulos y color.

Reglas (salen de medir el estilo, ver `recetas/ESTILO.md`):

- **Gancho, 0 a 3 s**: el estilo habla desde el segundo 0 con una pregunta, un "si tú..." o un contraste ("ves X, pero
  no ves Y"); si el crudo arranca con silencio, los cortes lo quitan. El texto está en pantalla desde el cuadro 0. Un título de 2 líneas que diga el tema: `chico` (2-3
  palabras de entrada, en caligráfica) + `grande` (2-3 palabras, el tema). Dura 1.5-3 s. Si la persona saluda, una `nota`
  a mano de 1 s ("hola :)") cerca de la cabeza. El primer corte cae antes de los 3 s (los scripts lo hacen si hay pausa).
- **Claves**: UNA palabra cada 5-8 s, la que carga el sentido (sustantivo, número, adjetivo fuerte). Nunca muletillas,
  marcas de terceros ni nombres de personas. Salen grandes, en pastel y con brillo, en el lugar del subtítulo.
- **Notas a mano**: 1 o 2 en todo el video, para un aparte o una reacción ("nooo..", "mido 1.50"). Cerca del sujeto.
- **Tomas de apoyo** (solo si el usuario las dio): cuando la voz describe algo, tapa la imagen con un clip de 0.6-1.0 s y
  encadena varios seguidos. Pon esos mismos rangos en `palabra_suelta`: ahí la palabra va a media pantalla (50 %).
- **Posiciones**: la palabra va en el hueco SOBRE la cabeza (por omisión 30 % desde arriba:
  `subtitulos.palabra.posicion_y` en `estilo.json`). Si en un tramo la cabeza está
  más arriba o es un plano cerrado, agrega a `posiciones` `{"ini", "fin", "x": 0.5, "y": 0.85}` para moverla en ese tramo.
- **Cierre**: en los últimos 2-3 s, una clave o una nota con la llamada a la acción que diga la persona ("link",
  "escríbeme", una pregunta para los comentarios, "parte dos"); no la inventes.

## 4. Vista previa, revisión y render

```
python <skill>/scripts/editar.py render crudo.mp4 --trabajo edicion --textos edicion/textos.json --salida edicion/previa.mp4 --hasta 15
python <skill>/scripts/revisar.py edicion/previa.mp4 --trabajo edicion --cada 0.5
```
**Abre `edicion/revision.jpg` y míralo.** Corrige antes del render completo: palabra encima de la cara (baja o sube
`posicion_y`), título tapando los ojos, textos chicos para un video horizontal recortado, color raro (mira `edicion/color.json`).
Luego el render completo (sin `--hasta`, `--salida edicion/editado.mp4`), con `--musica pista.mp3` si el usuario la dio,
y vuelve a revisar: `python <skill>/scripts/revisar.py edicion/editado.mp4 --trabajo edicion`.

Opciones: `--estilo mio.json` (solo las claves que cambian de `estilo.json`; p. ej. `{"cortes": {"silencio_max": 0.5}}`
para cortar menos, o `{"subtitulos": {"palabra": {"posicion_y": 0.25}}}` para subir la palabra en todo el video),
`--sin-cortes` (respeta las pausas), `--palabras p.json` (usa una lista `[{"p", "ini", "fin"}]` ya hecha y no transcribe),
`--modelo base` (máquinas lentas), `--hilos 2` (poca RAM).
`edicion/color.json` guarda lo medido en el crudo (`medido`), la meta del estilo (`objetivo`) y el filtro aplicado; si el
color no convence, cambia `color.objetivo` con `--estilo` o pon `{"color": {"modo": "fijo"}}`.

## 5. Entregar

El `.mp4` (H.264 + AAC, `+faststart`, listo para subir), la hoja `revision.jpg` y, en el chat, el ritmo que imprimió
`revisar.py` (cortes por minuto, contando los de las tomas de apoyo, y mediana de los tramos de voz). Si algo del
estilo no se pudo, dilo (ver límites).

## Límites (dilo, no lo simules)

- No hay efectos de cara (ojos grandes, deformaciones), stickers animados, burbujas ni destellos: son efectos de la app.
- No inventa tomas de apoyo: si no hay, el ritmo de cortes depende de las pausas del crudo (~8-25 cortes/min hablando
  a cámara, contra 30-70 del estilo con tomas de apoyo).
- No pone música: solo mezcla la que el usuario tenga derecho a usar (`--musica`), bajo la voz.
- Los subtítulos salen de whisper: revisa nombres propios y palabras raras en `edicion/palabras.json`, corrígelos ahí y
  vuelve a correr `render` (reutiliza ese archivo y recalcula cortes y textos).
- Los tramos sin voz se cortan enteros (una demostración en silencio desaparece): usa `--sin-cortes` o trabaja ese
  tramo aparte con `--desde`/`--hasta`.
- Video HDR (iPhone): se convierte a SDR si tu ffmpeg trae `zscale`; si no, avisa y puede salir lavado.
- Un video horizontal se recorta al centro para 9:16; si la persona no está al centro, queda fuera.
- Copiar un estilo no garantiza alcance: lo que sí pesa es que el video se vea completo. Si importa, haz un A/B.
