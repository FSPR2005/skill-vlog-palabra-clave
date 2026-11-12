# El estilo, medido

Cómo se obtuvo: se analizaron 6 videos públicos verticales de vlogs de estilo de vida de una misma cuenta, de menos de
1 min a varios minutos. Ningún video, cuadro, audio ni texto de esa cuenta se incluye aquí: solo las medidas. Por video: detección de cortes
con ffmpeg (`scene` por cuadro a 30 cuadros/s; un corte es un pico 6 veces mayor que la mediana de los 15 cuadros
vecinos o mayor que 0.3), hojas a 1 cuadro/s y tiras a 10 y 30 cuadros/s alrededor de los textos, transcripción con
faster-whisper `small`, recortes a resolución completa para medir letras, y métricas de color sobre 1 cuadro de cada 2 s.

Los números de abajo son los que usa `estilo.json`. "Medido" es lo que salió; "en la skill" es cómo se reproduce.

## 1. Formato

- Medido: 1080x1920, 60 cuadros/s en 5 de 6 (uno a 30). Los cortos más vistos duran menos de 1 min.
- En la skill: 1080x1920 a 30 cuadros/s (el material de teléfono rara vez trae 60 reales; súbelo en `salida.fps`).

## 2. Cortes y ritmo

| Video | Tipo | Cortes/min | Mediana entre cortes | p25-p75 |
|---|---|---|---|---|
| A | a cámara + apoyo | 30.7 | 1.6 s | 0.7-2.9 s |
| B | dos tomas de la misma persona | 39.5 | 0.7 s | 0.6-2.0 s |
| C | voz en off sobre tomas de apoyo | 69.7 | 0.7 s | 0.57-1.03 s |
| D | vlog caminando con el teléfono | 49.2 | 1.13 s | 0.77-1.5 s |
| E | a cámara en un auto + apoyo | 39.4 | 1.23 s | 0.73-1.97 s |
| F | largo (abrir paquetes), 2 ventanas de 150 y 65 s | 51-56 | 0.93-1.0 s | 0.63-1.57 s |

La detección por picos se queda corta en los cortes en salto con el mismo fondo (se ven en las tiras a 10 cuadros/s y no
siempre dan pico): las cifras son un piso.

- Todos los cortes son secos: sin fundidos, sin barridos. Una sola transición de bloques con falla digital en 6 videos.
- Hablando a cámara: corte en salto cada 1.5-3 s, en las pausas. Tomas de apoyo: cada 0.6-1.0 s, encadenadas.
- Un "empujón" de cámara (acercamiento de ~0.6 s antes de un corte) aparece en uno; no se incluye por omisión.
- En la skill: `cortes.silencio_max` 0.35 s, `margen_antes` 0.05 s, `margen_despues` 0.12 s; tomas de apoyo
  de 0.6-1.0 s vía `textos.json` → `apoyos`.

## 3. Subtítulo de una palabra

- Medido: una palabra a la vez, minúsculas, sin puntuación, sans geométrica seminegrita blanca, sin contorno y con
  sombra muy suave. Alto de minúscula 22-40 px en 1080 de ancho. Aparece de golpe (de un cuadro al siguiente, sin
  fundido ni rebote) cuando se dice la palabra y se queda hasta la siguiente.
- Posición: centrada a lo ancho, en el hueco sobre la cabeza (25-35 % desde arriba) cuando se habla a cámara; a media
  pantalla (~50 %) sobre tomas de apoyo; abajo (85-92 %) en planos cerrados de manos o mesa.
- En la skill: Poppins SemiBold (OFL) tamaño ASS 58, `posicion_y` 0.30; `palabra_suelta` → 0.5; `posiciones` por tramo.

## 4. Palabra clave

- Medido: 1 cada 5-8 s. La misma sans 2.5-3 veces más grande en azul pastel (#BDE6F4) o amarillo pálido (#F4F0A8) con
  un halo claro; o una caligráfica enorme (ancho ~80 % de la pantalla) en el mismo pastel; a veces un número grande con
  2-3 palabras chicas apiladas a su lado.
- En la skill: `claves` en `textos.json`; estilo `Clave0` (sans 150) con `\bord6\blur6` de halo; `Clave1` caligráfica.

## 5. Título del gancho

- Medido: en pantalla desde el cuadro 0 o antes de 1 s; dura 1.5-3 s, o hasta ~8 s si lleva un número que va
  subiendo (un contador que cambia con cada corte). Dos letras: una línea chica en caligráfica fina color
  amarillo pálido arriba a la izquierda y, debajo, el tema en sans muy negrita, blanca, a veces con textura de sello;
  tercio superior (20-23 % desde arriba). Variante: la frase se arma palabra por palabra en escalera
  (cada renglón empieza más a la derecha) con la clave en pastel.
- En la skill: `titulos` (Great Vibes + Poppins ExtraBold, `posicion_y` 0.22) y `subtitulos.modo = "frases"` para la escalera.

## 6. Notas a mano

- Medido: en 3 de 6 videos, 1-4 por video: un saludo, una medida o un botón con flecha, una reacción. Blancas, manuscritas,
  inclinadas ~8° subiendo a la derecha, junto a la cabeza o al objeto.
- En la skill: `notas` (Gochi Hand, `rotacion` -8, que sube a la derecha).

## 7. Color

| Métrica (0-255) | Mediana de los 6 videos = `color.objetivo` | Rango |
|---|---|---|
| Luma media | 122 | 114-132 |
| Saturación media (HSV) | 57 | 39-89 |
| Negro (percentil 2) | 13 | 8-23 |
| Blanco (percentil 98) | 222 | 206-225 |
| Calidez (R - B) | 19 | 4-34 |

- Luz natural, interiores claros, blancos que no queman (nunca llegan a 255), poca saturación salvo en la ropa.
- En la skill: `color.modo = "auto"` mide 8 cuadros de TU video y calcula `colorlevels` (negro y blanco), `eq` (gamma y
  saturación) y `colorbalance` (calidez) hacia esas medianas, con topes para no destrozar un video muy distinto.

## 8. Audio

- Voz casi continua: 132-200 palabras por minuto (mediana ~183) y voz presente el 63-89 % del tiempo. La primera
  palabra está en el segundo 0.0 en los 6: no hay silencio ni logo de entrada.
- Gancho hablado (0-3 s), siempre una de tres formas: una pregunta o un "si tú..." que interpela ("si tu sueño es...");
  un contraste ("ves X, pero no ves Y"); o leer en voz alta el comentario de alguien y responderlo.
- Cierre: una llamada a la acción corta y hablada: "aquí te dejo el link", "escríbeme tus dudas", una pregunta para los
  comentarios ("¿cuál va más contigo?"), "parte dos" o un "adiós" sin más.
- Fondo: en los huecos de la voz el nivel queda entre 0 y 8 dB por debajo de la voz (en los vlogs largos, casi igual):
  hay una cama de sonido que no se apaga, música o ambiente. SUPUESTO que sea música en todos: la medida no distingue
  música de ambiente, y la pista figura como "sonido original".
- Efectos de sonido y si la música sigue el ritmo de los cortes: [NO MEDIDO] (no hay método fiable sin escuchar; no se
  incluyen).
- En la skill: voz normalizada a -14 LUFS (`audio.voz_lufs`), música del usuario a -24 dB (`audio.musica_db`) con
  *ducking* (`sidechaincompress` umbral 0.03, razón 6, ataque 20 ms, liberación 350 ms) para que suba en los huecos.

## 9. Lo que no se replica

- Efectos de cara de la app (ojos grandes, deformación) en 2 de 6 videos, stickers con imágenes o emojis, burbujas,
  destellos de luz de color entre tomas (1 video) y recortes de otra persona insertados como meme.
- Burbujas de "responder comentario" de la app.
- Las tomas de apoyo y la música: dependen del material que tenga el usuario.
