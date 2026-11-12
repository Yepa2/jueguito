import cv2
import numpy as np
import os
import django

# 1. Configura la variable de entorno apuntando al settings de tu proyecto
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'juego.settings')

# 2. Inicializa Django
django.setup()

PATH = os.getcwd()

from backend.models import PersonajeSeleccionado
from backend.generar_imagen.Personaje import Personaje

p = PersonajeSeleccionado.objects.first()
mi_personaje = Personaje(p.seleccionado)

W = 1000
H = 500


personaje = cv2.imread(PATH + p.imagen.url)
personaje = cv2.resize(personaje, (50,50))

# Inicio personaje
x,y = p.x, p.y

tesoro = cv2.imread("tesoro.jpg")
tesoro = cv2.resize(tesoro, (100,100))

# Inicio tesoro
tx, ty = 600, 250

while True:
    img = np.full((H, W, 3), 255, dtype=np.uint8)
    # Personaje a la imagen
    cv2.line(img, (300,227), (300, 400), (100,200,100), 5)
    img[y:y+personaje.shape[0], x:x+personaje.shape[1]] = personaje
    
    img[ty:ty+tesoro.shape[0], tx:tx+tesoro.shape[1]] = tesoro

    key = cv2.waitKey(2000) & 0xFF
    if key == ord("q"):
        break

    if hay_colision(x,y, personaje.shape[0], personaje.shape[1], tx,ty, tesoro.shape[0], tesoro.shape[1]):
        print("Colision con tesoro")
        continue
    if hay_colision(x,y, personaje.shape[0], personaje.shape[1], 300, 227, 5, 200):
        print("Colision con la linea")
        continue

    x, y = mi_personaje.movimiento_personaje(key)
    p.x = x
    p.y = y
    p.save()
    