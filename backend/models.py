from django.db import models

# Create your models here.
class Personaje(models.Model):
    nombre = models.CharField(max_length=50)
    x = models.IntegerField(default=50)
    y = models.IntegerField(default=50)
    velocidad = models.IntegerField(default=25)
    imagen = models.ImageField(upload_to='static') # En prod no hacer esto, usar un bucket
    
    def __str__(self):
        return self.nombre
    
class PersonajeSeleccionado(models.Model):
    seleccionado = models.ForeignKey('Personaje', on_delete=models.CASCADE)

class Pared(models.Model):
    x = models.IntegerField(default=50)
    y = models.IntegerField(default=50)
    ancho = models.IntegerField(default=50)
    alto = models.IntegerField(default=50)