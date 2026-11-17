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
- En la skill: Poppins SemiBold (OFL) tamaño ASS 52 (las palabras medidas piden entre 41 y 61 de tamaño ASS para igualar su ancho en px; 52 es el medio), `posicion_y` 0.30; `palabra_suelta` → 0.5; `posiciones` por tramo.

## 4. Palabra clave

- Medido: 1 cada 5-8 s. La misma sans 2.5-3 veces más grande en azul pastel (#BDE6F4) o amarillo pálido (#F4F0A8) con
  un halo claro; o una caligráfica enorme (ancho ~80 % de la pantalla) en el mismo pastel; a veces un número grande con
  2-3 palabras chicas apiladas a su lado.
- En la skill: `claves` en `textos.json`; estilo `Clave0` (sans 138, el ancho medido) con un halo difuso debajo
  y la letra nítida encima; `Clave1` caligráfica (300). Si no cabe, se encoge.

## 5. Título del gancho

- Medido: en pantalla desde el cuadro 0 o antes de 1 s; dura 1.5-3 s, o hasta ~8 s si lleva un número que va
  subiendo (un contador que cambia con cada corte). Dos tipos de letra: una línea chica en caligráfica fina color
  amarillo pálido arriba a la izquierda y, debajo, el tema en sans muy negrita, blanca, a veces con textura de sello;
  tercio superior (20-23 % desde arriba). Variante: la frase se arma palabra por palabra en escalera
  (cada renglón empieza más a la derecha) con la clave en pastel.
- En la skill: `titulos` (Great Vibes 104 + Poppins ExtraBold 141, que igualan los anchos medidos; `posicion_y` 0.22) y `subtitulos.modo = "frases"` para la escalera.

## 6. Notas a mano

- Medido: en 3 de 6 videos, 1-4 por video: un saludo, una medida o un botón con flecha, una reacción. Blancas, manuscritas,
  inclinadas ~8° subiendo a la derecha, junto a la cabeza o al objeto.
- En la skill: `notas` (Gochi Hand 104, `rotacion` -8, que sube a la derecha).

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
  *ducking* (`sidechaincompress` umbral 0.03, razón 6, ataque 20 ms, liberación 350 ms): baja la música mientras se
  habla y la deja volver en los huecos. -24 dB es una ganancia sobre la pista tal como viene y queda más baja que lo
  medido, a propósito, para que la voz se entienda; para una cama como la del estilo, sube `musica_db` a -14 / -18.

## 9. Lo que no se replica

- Efectos de cara de la app (ojos grandes, deformación) en 2 de 6 videos, stickers con imágenes o emojis, burbujas,
  destellos de luz de color entre tomas (1 video) y recortes de otra persona insertados como meme.
- Burbujas de "responder comentario" de la app.
- Las tomas de apoyo y la música: dependen del material que tenga el usuario.

## 10. Antes y después por capas (otra referencia)

Cómo se obtuvo: un reel público vertical de una agencia de contenido (14.75 s, 1080x1920, 60 cuadros/s), visto en 10
cuadros cada 1.5 s. No se incluye nada de él: ni cuadros, ni voz, ni música, ni marca.

- Medido: fondo gris claro casi blanco; título de dos palabras con "vs" en sans negrita gris oscuro, centrado al ~12 %
  desde arriba; el video en una tarjeta de ~53 % del ancho (de 16 % a 68 % del alto) con esquinas redondeadas; debajo,
  al ~72-78 % del alto, una fila de bloques de colores saturados con esquinas redondeadas y un brillo suave, con su
  nombre abajo en sans chica oscura: rojo (original), amarillo (subtítulos), cian (zoom), naranja (gráficos) y verde
  (música y efectos). La fila corre a la izquierda bajo una raya vertical fija al centro; el video empieza crudo y gana
  color y subtítulos hacia los 3 s, gráficos hacia los 7 s.
- En la skill: `editar.py antes-despues` con `antes_despues` de `estilo.json` (fondo #EEEEEB, `tarjeta_ancho` 0.53,
  `barra_y` 0.722, bloques de 230x112 px); las capas se reparten parejo en la duración salvo que lleven `ini`, y los
  bloques que aún no llegan se ven tenues (`opacidad_pendiente` 0.45; con 1.0 se ven todos llenos, como en el reel).
- Diferencias: los gráficos del reel son interfaces de una app; aquí la capa de gráficos son tus títulos, notas y tomas
  de apoyo. Los efectos de sonido no se generan. El zoom del reel no se midió cuadro a cuadro; aquí es en salto
  (`zoom.factor` 1.12, un tramo sí y otro no).

## 11. Palabras resaltadas y gancho con cifra (otra referencia)

Cómo se obtuvo: un reel público vertical de captación (47 s, 1080x1920, 30 cuadros/s): tira de 5 cuadros entre 0.4 y
2.4 s y la transcripción de los primeros 8 s. Tampoco se incluye nada de él.

- Medido (0-2.4 s): la frase completa del gancho, en tres renglones centrados a media pantalla; el renglón del tema en
  mayúsculas, sans muy negrita, amarillo con un halo amarillo suave; el resto en sans normal blanca con sombra.
- Medido (0-8 s): una pregunta de 1 frase (0-3 s) y, antes de los 8 s, el resultado con dos cifras (vistas y
  seguidores) en pantalla. Las cifras son dichos de quien habla: no se comprobaron.
- En la skill: `resaltar` en `textos.json` (Poppins ExtraBold 104, mayúsculas, #F5F02A con halo; o caja con
  `resaltado.modo = "fondo"`), y la regla "Gancho con cifra" del paso 3 de SKILL.md, que exige que la cifra sea
  verdadera y verificable.

## 12. Tarjetas de interfaz, ventanas flotantes, fondo en boceto y estrellas (otra referencia)

Cómo se obtuvo: un reel público vertical de una creadora (48 s, 1080x1920, 30 cuadros/s) que dice estar editado con IA
en un servicio de pago en la nube. Se vieron 10 cuadros (a 540 px de ancho) en los segundos donde sale cada gráfico y
su análisis escrito. Aquí todo se hace local y gratis con ffmpeg, Python y Pillow. No se incluye nada de él: ni
cuadros, ni voz, ni música, ni sus marcas, logos o fuentes. Las posiciones son ±2 % (medidas a ojo sobre esos cuadros).

- Medido: subtítulo de una palabra al ~22 % del alto; la cara de un plano medio entre ~32 y ~58 % (de la coronilla a la
  barbilla) y ~30-70 % del ancho. Todos los gráficos de interfaz van DEBAJO de la barbilla, centrados a lo ancho, entre
  el 64 y el 80 % del alto: nunca tapan la cara ni la palabra.
- Medido, tarjetas: blancas un poco translúcidas, esquinas muy redondeadas, sombra suave. Una lista de ~64 % del ancho
  (centro al ~72 %) con título (una palabra en caligráfica + el resto en sans negrita) y 3 renglones que se palomean de
  uno en uno con un círculo de color; el que falta, gris. Una insignia tipo píldora oscura de ~52 % del ancho (al ~68 %)
  con un destello y el dato del gancho. Una caja de mensaje de ~78 % del ancho (al ~68 %) con avatar redondo de
  iniciales y una etiqueta chica de color. Una barra de comentario de ~78 % (al ~67 %) con avatar, texto y botón de
  enviar, y una flecha que apunta hacia abajo. Entran con un pequeño rebote de escala y se van desvaneciendo. Hay 6
  tarjetas en 48 s, separadas de 3 a 20 s (mediana ~6 s).
- Medido, flotantes: 4 ventanas de video con esquinas redondeadas y un borde claro, a los lados de la persona (la
  primera arriba a la izquierda, al ~40 % del alto), que aparecen juntas unos 4 s.
- Medido, boceto: unos 3 s en que el fondo se vuelve líneas negras sobre blanco (con una cuadrícula tenue) y la
  persona queda igual encima.
- Medido, estrellas: al despedirse, 4-6 estrellas de 5 puntas en rosa, morado y amarillo pastel salen de la mano.
- En la skill: `tarjetas` (lista, insignia, mensaje, comentario; `zona_y` 0.60-0.90, `pop_ms` 280 desde 0.6,
  `salida_ms` 220; colores propios: acento lila #C86DD7, insignia ciruela #5E2750), `flotantes` (`ancho` 0.26,
  proporción 3:4, borde blanco de 6 px, lugares a los lados a 42 y 70 % del alto, `cara` 30-70 % del ancho y 32-60 %
  del alto, escalonadas 150 ms), `boceto` (bordes de Pillow sobre papel #FAFAF7 con cuadrícula de 60 px y la persona
  recortada con rembg o mediapipe) y `particulas` (18 estrellas de 5 puntas en 1.2 s, rosa, lila, amarillo y azul pastel).
- Diferencias: los gráficos son dibujos propios, no la interfaz de ninguna app; el texto de cada tarjeta lo escribe el
  agente con lo que dice la persona. La segmentación es un modelo chico local, menos fino que el del servicio de pago.
  Una tarjeta cada 5-8 s como mucho (la referencia, mediana ~6 s).
