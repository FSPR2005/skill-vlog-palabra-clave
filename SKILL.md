---
name: vlog-palabra-clave
description: Edita un video crudo (vertical u horizontal) con el estilo de vlog de estilo de vida que se ve en TikTok y Reels - cortes en salto que quitan las pausas, subtítulo de UNA palabra chica y blanca en el hueco sobre la cabeza, palabras clave grandes en color pastel con brillo suave, título de gancho en dos tipos de letra (caligráfica chica + sans negrita grande), notas escritas a mano, tomas de apoyo de 0.6-1.0 s y color luminoso con blancos suaves. Todo local y gratis (ffmpeg + faster-whisper), en Windows, Mac o Linux, con los parámetros en estilo.json. También resalta palabras dentro de la frase, hace un antes y después por capas (el crudo que se va editando, con una barra de capas de colores) y agrega gráficos de interfaz animados (lista que se palomea, insignia, mensaje con avatar, barra de «comenta PALABRA» con flecha), ventanas de video flotantes alrededor de la persona, un tramo con el fondo en boceto de líneas y una ráfaga de estrellas pastel. Úsala cuando el usuario diga "edita este video", "edítalo estilo vlog", "ponle subtítulos palabra por palabra", "quita las pausas y ponle textos", "edítalo como TikTok de lifestyle", "edita mi unboxing / haul / vlog / reseña", "déjalo listo para Reels", "muéstrame el antes y después de la edición", "ponle tarjetas / una checklist / el comenta PALABRA", "pon videos flotando alrededor de mí", "vuelve el fondo un dibujo", o suba un video crudo pidiendo editarlo con ese estilo.
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
Si `python` no existe, usa `python3` (Mac/Linux) o `py` (Windows); lo mismo con `pip` / `pip3`.
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
             {"archivo": "apoyo2.mp4", "desde": 3.0, "ini": 6.9, "fin": 8.0}],
  "resaltar": ["regalos sorpresa", {"texto": "veinte", "ini": 9.0, "fin": 12.0}],
  "tarjetas": [{"tipo": "insignia", "texto": "✨ 100 % hecho en casa", "ini": 0.3, "fin": 2.6},
               {"tipo": "lista", "titulo_chico": "todo", "titulo": "en una tarde",
                "renglones": ["Guion", "Grabación", "Edición"], "ini": 5.5, "fin": 9.0},
               {"tipo": "mensaje", "iniciales": "AB", "titulo": "PROMPT", "texto": "edita mi reel", "ini": 11.0, "fin": 13.5},
               {"tipo": "comentario", "palabra": "GUIA", "iniciales": "AB", "ini": 17.0, "fin": 19.5}],
  "flotantes": [{"archivo": "clip1.mp4", "desde": 0.0, "ini": 14.0, "fin": 16.5},
                {"archivo": "clip2.mp4", "desde": 2.0, "ini": 14.0, "fin": 16.5}],
  "boceto": [{"ini": 9.2, "fin": 11.0}],
  "particulas": [{"x": 0.62, "y": 0.6, "t": 19.6}]
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
- **Gancho con cifra, 0 a 8 s** (cuando la persona cuenta un resultado propio): en los primeros 3 s, una pregunta
  ("¿qué pasa si...?") **o** una afirmación ("lo probé un mes y pasó esto"), y la cifra del resultado antes de los 8 s
  ("de X a Y"). Ninguna de las dos aperturas es mejor por regla: en algunas cuentas abrir con pregunta retiene menos a
  los 3 s. Si la persona tiene datos de sus videos, se prueban las dos (A/B) y se queda la que retenga más. La cifra tiene que ser
  verdadera y verificable: la dice la persona en el crudo y tiene una fuente que ella puede mostrar (captura de sus
  estadísticas, reporte, factura). No la inventes, no la redondees hacia arriba ni la tomes de otro video; si no hay
  cifra comprobable, el gancho va sin cifra (pregunta o contraste) y se lo dices. En pantalla, la cifra va en
  `resaltar` o en un `titulos`, con las mismas palabras que dijo.
- **Claves**: UNA palabra cada 5-8 s, la que carga el sentido (sustantivo, número, adjetivo fuerte). Nunca muletillas,
  marcas de terceros ni nombres de personas. Salen grandes, en pastel y con brillo, en el lugar del subtítulo
  (su letra, tamaño y colores están en `subtitulos.frases.claves` de `estilo.json`: la `[0]` en modo palabra).
- **Modo de subtítulo**: `subtitulos.modo` es `"palabra"` (una palabra a la vez, el del estilo) o `"frases"` (la frase se
  arma palabra por palabra en escalera, para un gancho tipo lista); se cambia con `--estilo`.
- **Resaltar** (`resaltar`): 1 a 4 palabras seguidas dentro de la frase que se ve, para el tema del gancho o la cifra
  ("pides a chat gpt", "30 mil"). Escríbelas como salen en `guion.txt` (sin importar signos ni mayúsculas); una
  secuencia solo coincide completa, y `{"texto", "ini", "fin"}` la limita a un tramo. En modo `frases` la palabra se
  queda en su renglón, en mayúsculas y amarilla con halo, y esa frase no lleva clave pastel; en modo `palabra` sale la
  palabra sola resaltada. `subtitulos.resaltado.modo` = `"fondo"` la pone sobre una caja de color con letra oscura.
  Como mucho una frase resaltada cada 5-8 s, igual que las claves.
- **Notas a mano**: 1 o 2 en todo el video, para un aparte o una reacción ("nooo..", "mido 1.50"). Cerca del sujeto.
- **Tomas de apoyo** (solo si el usuario las dio): cuando la voz describe algo, tapa la imagen con un clip de 0.6-1.0 s y
  encadena varios seguidos. Pon esos mismos rangos en `palabra_suelta`: ahí la palabra va a media pantalla (50 %).
- **Tarjetas de interfaz** (`tarjetas`): refuerzan con una imagen lo que la persona DICE en ese momento; nunca dicen algo
  que ella no dijo ni inventan cifras. Como mucho **una tarjeta cada 5-8 s** (el script avisa si dos empiezan a menos de
  5 s) y de 2 a 4 s cada una. Tipos: `lista` (título y 2-4 `renglones` que se palomean uno por uno, parejos entre la
  entrada y la salida; un renglón `{"texto", "en"}` se palomea en ese segundo; `titulo_chico` va en caligráfica antes
  del título), `insignia` (píldora con `texto`, para el dato del gancho), `mensaje` (`iniciales` del avatar, `titulo`
  chico de color y `texto`, para un prompt o un mensaje) y `comentario` (`palabra` y, si quieres, `iniciales` y
  `texto` en lugar de «Comenta»; trae una flecha que apunta hacia abajo, para el cierre «comenta PALABRA»). ✨ y ▶ se
  dibujan; otros emojis se quitan con un aviso. Van centradas en `x`, `y` (fracciones; por omisión las de su tipo en
  `estilo.json`) y siempre dentro de la franja `tarjetas.zona_y` (60-90 % del alto), debajo de la cara y lejos del
  subtítulo: si la pides más arriba, se baja con un aviso. Si en ese tramo moviste la palabra abajo con `posiciones`,
  sube la palabra o no pongas tarjeta.
- **Ventanas flotantes** (`flotantes`, solo con clips del usuario): 2 a 4 ventanas que salen juntas cuando la persona
  habla de "mis videos", "lo que hice", etc., 2-3 s, máximo una vez por video. Sin `x`, `y` toman los lugares a los
  lados de la persona (`flotantes.lugares`); las que entran en el mismo segundo se escalonan solas. No llevan audio: la
  voz sigue. Si una tapa la cara (`flotantes.cara`), el script avisa: muévela.
- **Fondo en boceto** (`boceto`): 1 tramo de 1.5-3 s, cuando la persona habla del fondo, del lugar o de "cómo se hizo".
  El fondo se vuelve líneas negras sobre papel y la persona queda encima. Necesita un segmentador local: `rembg`
  (`pip install rembg`; la primera vez baja su modelo `u2netp`, ~4.7 MB) o `mediapipe`. Sin ninguno, el render sale
  sin boceto y con un aviso; díselo al usuario. Es lo más pesado de la skill (ver README, «Límites»).
- **Partículas** (`particulas`): una ráfaga de estrellas pastel de 1.2 s en un punto (`x`, `y`) y segundo (`t`): un
  beso, un "listo", la despedida. Una o dos en todo el video.
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
`posicion_y`), título tapando los ojos, tarjeta o ventana flotante sobre la cara o la mano que señala, textos chicos para
un video horizontal recortado, color raro (mira `edicion/color.json`). Los gráficos quedan en `edicion/graficos/`
(cada uno es un `.mov` con alfa; se rehacen en cada render).
Luego el render completo (sin `--hasta`, `--salida edicion/editado.mp4`), con `--musica pista.mp3` si el usuario la dio,
y vuelve a revisar: `python <skill>/scripts/revisar.py edicion/editado.mp4 --trabajo edicion`.

### 4c. Revisión final obligatoria
Ver y OÍR el `.mp4` completo, no solo `revision.jpg`. Cotejar cada subtítulo contra el audio, en especial cifras, negaciones («no», «nunca», «sin») y nombres propios. Cada cifra o cita se coteja contra su fuente abierta. Anotar cada hallazgo con marca de tiempo. Sin esta revisión no se entrega.

Opciones: `--estilo mio.json` (solo las claves que cambian de `estilo.json`; p. ej. `{"cortes": {"silencio_max": 0.5}}`
para cortar menos, o `{"subtitulos": {"palabra": {"posicion_y": 0.25}}}` para subir la palabra en todo el video),
`--sin-cortes` (respeta las pausas), `--palabras p.json` (usa una lista `[{"p", "ini", "fin"}]` ya hecha y no transcribe),
`--modelo base` (máquinas lentas), `--hilos 2` (poca RAM).
`edicion/color.json` guarda lo medido en el crudo (`medido`), la meta del estilo (`objetivo`) y el filtro aplicado; si el
color no convence, cambia `color.objetivo` con `--estilo` o pon `{"color": {"modo": "fijo"}}`.

## 4b. Antes y después por capas (opcional, para mostrar la edición)

```
python <skill>/scripts/editar.py antes-despues crudo.mp4 --trabajo edicion --textos edicion/textos.json --salida edicion/antes_despues.mp4 [--musica pista.mp3] --hasta 15
```
El mismo clip, en una tarjeta con esquinas redondeadas sobre fondo claro y con el título "Original vs Editado", empieza
crudo (sin color, sin texto) y se va editando por capas. Abajo corre una barra de bloques de colores bajo un cabezal
fijo: Original (rojo), Subtítulos (amarillo; trae también el color), Zoom in y out (cian), Gráficos (naranja: títulos,
notas, tomas de apoyo, tarjetas, flotantes, boceto y estrellas; los que empiezan antes de su bloque no salen) y Música y SFX (verde: la pista de `--musica`). Cada capa se prende cuando el cabezal entra en
su bloque; los bloques que faltan se ven tenues. Todo se cambia en `antes_despues` de `estilo.json` (título, colores,
tamaños, `capas` con `nombre`, `color`, `tipos` y, si quieres, `ini` en segundos). Por omisión las capas se reparten
parejo en la duración. Una capa sin material (p. ej. Música sin `--musica`) se quita de la barra con un aviso. El zoom
es en salto: un tramo sí y otro no entre cortes (`zoom.factor`, `zoom.periodo`); en el render normal se prende con
`{"zoom": {"activar": true}}`. Revisa la hoja con `revisar.py` como en el paso 4. Los SFX no se generan: si la pista de
`--musica` los trae, suenan; si no, cambia el nombre de la capa a "Música".

## 5. Entregar

El `.mp4` (H.264 + AAC, `+faststart`, listo para subir), la hoja `revision.jpg` y, en el chat, el ritmo que imprimió
`revisar.py` (cortes por minuto, contando los de las tomas de apoyo, y mediana de los tramos de voz). Si algo del
estilo no se pudo, dilo (ver límites).

## Límites (dilo, no lo simules)

- No hay efectos de cara (ojos grandes, deformaciones), stickers con imágenes ni burbujas de "responder comentario":
  son efectos de la app. Las tarjetas son dibujos propios (sin logos ni marcas de nadie); las estrellas, figuras.
- El fondo en boceto necesita `rembg` o `mediapipe` (opcionales): sin ellos se salta con un aviso. La máscara es de un
  modelo chico: en pelo suelto, manos que se mueven rápido o un fondo del mismo color que la ropa, la orilla se ve
  recortada; revisa ese tramo en el `.mp4`.
- No inventa tomas de apoyo: si no hay, el ritmo de cortes depende de las pausas del crudo (17 cortes/min en la prueba
  con una voz de corrido, contra 30-70 del estilo con tomas de apoyo).
- No pone música: solo mezcla la que el usuario tenga derecho a usar (`--musica`), bajo la voz.
- Los subtítulos salen de whisper: revisa nombres propios y palabras raras en `edicion/palabras.json`, corrígelos ahí y
  vuelve a correr `render` (sin `--palabras`: lee ese archivo solo, también con `--desde`/`--hasta`). Si cambiaste
  tiempos, los cortes se recalculan: vuelve a leer `guion.txt` y ajusta los tiempos de `textos.json`.
- Los tramos sin voz se cortan enteros (una demostración en silencio desaparece): usa `--sin-cortes` o trabaja ese
  tramo aparte con `--desde`/`--hasta`.
- Video HDR (iPhone): se convierte a SDR si tu ffmpeg trae `zscale`; si no, avisa y puede salir lavado.
- Un video horizontal se recorta al centro para 9:16; si la persona no está al centro, queda fuera.
- Copiar un estilo no garantiza alcance: lo que sí pesa es que el video se vea completo. Si importa, haz un A/B.
