from django.db import models 
from django.db import models 
from applications.core.models import BaseAbstractWithUser


class Servicio(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre


class Paciente(BaseAbstractWithUser):
    GENEROS = [
        ("Masculino", "Masculino"),
        ("Femenino", "Femenino"),
    ]

    nombre = models.CharField(max_length=120)
    apellido = models.CharField(max_length=120)
    dni = models.CharField(max_length=20, unique=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    genero = models.CharField(max_length=30, choices=GENEROS, blank=True, null=True)

    telefono = models.CharField(max_length=50, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    nacionalidad = models.CharField(max_length=100, blank=True, null=True)
    provincia = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.apellido}, {self.nombre} - DNI {self.dni}"


class Medico(BaseAbstractWithUser):
    nombre = models.CharField(max_length=120)
    apellido = models.CharField(max_length=120)
    numero_documento = models.CharField(max_length=20, blank=True, null=True)
    firma_nombre = models.CharField(max_length=50, blank=True, null=True)
    matricula = models.CharField(max_length=50)
    servicio = models.ForeignKey(
        "Servicio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medicos"
    )

    def __str__(self):
        return f"Dr/a. {self.apellido}, {self.nombre} - MP {self.matricula}"


class ObraSocial(models.Model):
    nombre = models.CharField(max_length=160, unique=True)
    sigla = models.CharField(max_length=50, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.sigla or self.nombre


class Prestacion(BaseAbstractWithUser):
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Plan(BaseAbstractWithUser):
    nombre = models.CharField(max_length=250,blank=True,null=True)
    obra_social = models.ForeignKey(
        "ObraSocial",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="obras_sociales"
    )

    def __str__(self):
        return f"{self.nombre}"

