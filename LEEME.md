# MangaScroll Pro - Manual de Usuario 📖

¡Bienvenido a **MangaScroll Pro**! Esta es una aplicación de escritorio moderna en Python diseñada específicamente para permitirte leer tus mangas y webtoons favoritos sin tener que tocar la pantalla, el ratón o el teclado.

---

## 🚀 Cómo Iniciar la Aplicación

Para ejecutar la aplicación, abre una terminal (PowerShell o CMD) en el directorio de la aplicación y ejecuta:

```powershell
.venv\Scripts\python.exe autoscroll.py
```

Esto abrirá una interfaz gráfica oscura, moderna y limpia.

---

## 🛠️ Modos de Funcionamiento

MangaScroll Pro tiene dos modos principales de funcionamiento:

### 1. Modo Estándar (Atajo de Teclado Global)
Este es el modo más robusto y rápido. Te permite alternar el desplazamiento automático con un solo botón en tu teclado, incluso mientras tienes la ventana del navegador web abierta (en primer plano).

- **Atajo por Defecto:** La tecla **`F9`**. Puedes cambiarla en el menú desplegable a otras teclas como `F9`, `F8`, `F10`, `Scroll_Lock`, `Pause` o `Caps_Lock`.
- **Cómo usarlo:**
  1. Abre tu navegador web en la página del manga que quieres leer.
  2. Coloca el cursor del ratón sobre la zona del manga (donde se realiza el scroll).
  3. Presiona **`F9`** (o tu tecla elegida). La página comenzará a deslizarse suavemente hacia abajo de forma automática.
  4. Presiona **`F9`** de nuevo cuando quieras pausar o detener el scroll para leer detalladamente un panel.

---

### 2. Modo Manos Libres por Cámara (Webcam Gesto Facial)
Este modo utiliza la inteligencia artificial de detección facial local a través de tu webcam para detectar la inclinación de tu cabeza.

- **Cómo usarlo:**
  1. Activa el interruptor **"Activar Control por Gesto Facial"**. Verás que se enciende tu webcam y aparece un recuadro verde alrededor de tu rostro con un punto rojo en el centro.
  2. Mira fijamente al centro de tu pantalla (en tu posición de lectura normal y cómoda) y presiona el botón **📍 Calibrar Centro**. Esto definirá tu postura neutral.
  3. **Para Desplazar Abajo:** Inclina la cabeza ligeramente hacia abajo (como si miraras hacia abajo). El sistema detectará que tu cabeza bajó e iniciará el scroll automáticamente.
  4. **Para Detener:** Vuelve a levantar la cabeza a tu posición normal de lectura. Al entrar en el rango neutral, el scroll se detendrá de inmediato.
  5. **Para Subir (Opcional):** Si lo configuras, inclinar la cabeza hacia arriba puede hacer que la página suba en lugar de detenerse.

---

## 🎨 Ajustes Personalizables

- **Velocidad de Scroll:** Controla el ritmo del deslizamiento usando la barra deslizante (de 1 a 50).
  - *Velocidad 1-10:* Lectura lenta y detallada.
  - *Velocidad 11-25:* Lectura continua muy cómoda.
  - *Velocidad 26-50:* Navegación rápida por capítulos.
- **Dirección:** Alterna entre "Bajar" (lectura normal) y "Subir" (releer).
- **Sensibilidad de la Cámara:** Si sientes que el scroll se activa con movimientos muy pequeños o que tienes que inclinar demasiado la cabeza, puedes ajustar este control deslizante para calibrarlo a tu gusto.
- **Ajustes Avanzados:** Abre este panel para afinar con milisegundos y píxeles exactos el comportamiento de cada paso de desplazamiento.

---

## 📦 Solución de Problemas

La aplicación está diseñada con un sistema tolerante a fallas. Si no tienes instalada la librería OpenCV (`opencv-python`), la aplicación funcionará perfectamente en el **Modo Estándar** y te ofrecerá un botón en pantalla para instalar las librerías necesarias con un solo clic.

Si decides instalarlas manualmente, ejecuta el siguiente comando en la consola:
```powershell
.venv\Scripts\pip install opencv-python pillow
```
Una vez instalado, reinicia la aplicación para desbloquear las funciones de la cámara.
