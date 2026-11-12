# Discretizando el Tiempo Continuo 🎮

Juego interactivo desarrollado en Python y Django con renderizado de laberinto mediante OpenCV y NumPy.

---

## 🚀 Cómo iniciar en cualquier dispositivo

Solo necesitas tener clonado o descargado este repositorio. Elige la forma que prefieras:

### Opción 1: En Windows (Sin Docker - 1 Solo Clic)
1. Haz **doble clic** en [`iniciar.bat`](iniciar.bat) (o abre una terminal y ejecuta `python run.py`).
2. El script configurará automáticamente el entorno virtual, instalará dependencias, creará la base de datos, poblará los personajes y abrirá tu navegador.

---

### Opción 2: En Linux o macOS (Sin Docker)
Abre la terminal en la carpeta del proyecto y ejecuta:
```bash
chmod +x iniciar.sh
./iniciar.sh
```
*(O directamente `python3 run.py`)*

---

### Opción 3: Con Docker (Windows, Mac o Linux con Docker instalado)
Si tienes Docker Desktop o Docker instalado, simplemente ejecuta:
```bash
docker compose up --build
```
> **Nota:** Ya no necesitas ejecutar comandos manuales (`migrate`, `poblar_personajes`, etc.). Todo se ejecuta e inicializa automáticamente dentro del contenedor.

---

### Opción 4: Jugar desde Celular o Tablet (En la misma red Wi-Fi)
1. Inicia el servidor en tu computadora usando cualquiera de las opciones anteriores.
2. La consola te indicará la dirección de red local (ejemplo: `http://192.168.1.50:8000/`).
3. Abre esa dirección en el navegador de tu celular o tablet (conectado a la misma red Wi-Fi).
4. El juego incluye controles táctiles adaptados para pantallas móviles.

---

## 🕹️ URLs del Proyecto

| URL | Descripción |
|---|---|
| `http://localhost:8000/` o `/tablero` | Tablero del juego principal. |
| `http://localhost:8000/api/seleccion-personaje` | Selección de personaje. |
| `http://localhost:8000/admin/` | Panel de administración de Django. |

- **Usuario Admin:** `alumno`
- **Contraseña Admin:** `usm1234`

---

## 🎮 Controles del Juego

- **Moverse:** Teclas `W`, `A`, `S`, `D` (o la cruceta táctil en pantallas móviles).
- **Disparar:** Clic izquierdo con el ratón hacia donde apuntes (o toca la pantalla en móviles).
- **Reiniciar Nivel 1:** Tecla `R` o botón *Reiniciar*.
