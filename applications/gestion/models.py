from django.db import models 
from django.db import models
from django.contrib.auth.models import User
from applications.core.models import BaseAbstractWithUser


class Preingreso(BaseAbstractWithUser):

    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("en_gestion", "En gestión"),
        ("ingresado", "Ingresado"),
        ("cerrado", "Cerrado"),
        ("anulado", "Anulado"),
        ("vencido", "Vencido"),
    ]

    ORIGENES = [
        ("domicilio", "Domicilio"),
        ("guardia", "Guardia"),
        ("consultorio", "Consultorio"),
        ("derivacion", "Derivación"),
        ("otro", "Otro"),
    ]

    PRIORIDADES = [
        ("normal", "Normal"),
        ("urgente", "Urgente"),
        ("programado", "Programado"),
    ]

    paciente = models.ForeignKey(
        "entidades.Paciente",
        on_delete=models.PROTECT,
        related_name="preingresos"
    )

    obra_social = models.ForeignKey(
        "entidades.ObraSocial",
        on_delete=models.PROTECT,
        related_name="preingresos"
    )

    plan = models.ForeignKey(
        "entidades.Plan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preingresos"
    )

    numero_afiliado = models.CharField(
        max_length=80,
        blank=True,
        null=True
    )

    medico = models.ForeignKey(
        "entidades.Medico",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preingresos"
    )

    servicio = models.ForeignKey(
        "entidades.Servicio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preingresos"
    )

    numero = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True
    )
    
    episodio = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True
    )

    fecha_probable_ingreso = models.DateField(
        blank=True,
        null=True
    )

    fecha_ingreso = models.DateField(
        blank=True,
        null=True
    )

    fecha_egreso = models.DateField(
        blank=True,
        null=True
    )

    diagnostico = models.TextField(
        blank=True,
        null=True
    )

    origen_paciente = models.CharField(
        max_length=30,
        choices=ORIGENES,
        default="domicilio"
    )

    prioridad = models.CharField(
        max_length=20,
        choices=PRIORIDADES,
        default="normal"
    )

    contacto_nombre = models.CharField(
        max_length=160,
        blank=True,
        null=True
    )

    contacto_dni = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    contacto_telefono = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    contacto_parentesco = models.CharField(
        max_length=80,
        blank=True,
        null=True
    )

    estado = models.CharField(
        max_length=30,
        choices=ESTADOS,
        default="pendiente"
    )

    fecha_anulacion = models.DateTimeField(
        blank=True,
        null=True
    )

    motivo_anulacion = models.TextField(
        blank=True,
        null=True
    )

    es_preingreso = models.BooleanField(
        blank=True,
        null=True,
        default=True
    )
    fecha_pasaje_internacion = models.DateTimeField(
        blank=True,
        null=True
    )
    user_pasaje_internacion = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True, 
        related_name="%(class)s_user_pasaje_internacion"
    )
    observaciones = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.numero or self.id} - {self.paciente}"




class Numerador(models.Model):
    nombre = models.CharField(
        max_length=50,
        unique=True
    )

    ultimo = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Numerador"
        verbose_name_plural = "Numeradores"

    def __str__(self):
        return f"{self.nombre}: {self.ultimo}"







class OrdenAutorizacion(BaseAbstractWithUser):
    TIPOS = [
        ("analisis", "Analisis"),
        ("consulta", "Consulta"),
        ("internacion","Internacion"),
        ("practica","Practica"), 
        ("otra", "Otra"),
    ]
    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("autorizada", "Autorizada"),
        ("anulada", "Anulada"),
    ]

    # lo que ya tenés...

    estado = models.CharField(
        max_length=30,
        choices=ESTADOS,
        default="pendiente"
    )


    preingreso = models.ForeignKey(
        "Preingreso",
        on_delete=models.CASCADE,
        related_name="ordenes"
    )
    medico = models.ForeignKey("entidades.Medico",on_delete=models.SET_NULL,null=True,blank=True,related_name="ordenes_autorizacion")
    
    medico_tenencia= models.ForeignKey("entidades.Medico",on_delete=models.SET_NULL,null=True,blank=True, related_name="ordenes_tenencia")

    tipo = models.CharField(max_length=50, choices=TIPOS) 
 
    fecha = models.DateField(blank=True,null=True)

    numero_cupon = models.TextField(blank=True,null=True,max_length=120)

    observaciones = models.TextField(blank=True, null=True)

    autorizada = models.BooleanField(default=False, null=True, blank=True)



    user_anulacion = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True, 
        related_name="%(class)s_user_anuled"
    )
    user_autorizacion= models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True, 
        related_name="%(class)s_user_autorized"
    )
    user_tenencia= models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True, 
        related_name="%(class)s_user_tenencia"
    )

    user_entrega= models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True, 
        related_name="%(class)s_user_entrega"
    )

    esta_entregada = models.BooleanField(
        blank=True,
        null=True,
        default=False
    )

    fecha_autorizacion = models.DateField(blank=True,null=True)
    fecha_anulacion = models.DateField(blank=True,null=True)
    fecha_tenencia = models.DateField(blank=True,null=True)
    fecha_entrega = models.DateField(blank=True,null=True)
    


    def __str__(self):
        return f"Orden {self.id} - {self.get_tipo_display()}"


class DetalleOrden(BaseAbstractWithUser):
    HONORARIOS_GASTOS = [
        ("honorarios", "Honorarios"),
        ("gastos", "Gastos"),
        ("todo", "Todo"),
    ]

    TIPOS_HONORARIO = [
        ("anestesista", "Anestesista"),  
        ("ayudante1", "Ayudante 1"),
        ("ayudante2", "Ayudante 2"),    
        ("ayudante3", "Ayudante 3"),         
        ("especialista", "Especialista"),
    ]

    orden = models.ForeignKey(
        "OrdenAutorizacion",
        on_delete=models.CASCADE,
        related_name="detalles"
    )

    prestacion = models.ForeignKey(
        "entidades.Prestacion",
        on_delete=models.PROTECT,
        related_name="detalles_orden"
    )

    autorizada = models.BooleanField(default=False)
    
    medico = models.ForeignKey(
        "entidades.Medico",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detalles_orden"
    )

    cantidad = models.IntegerField(default=1)

    honorarios_gastos = models.CharField(
        max_length=30,
        choices=HONORARIOS_GASTOS,
        blank=True,
        null=True
    )

    tipo_honorario = models.CharField(
        max_length=40,
        choices=TIPOS_HONORARIO,
        blank=True,
        null=True
    )
 

    fecha_desde = models.DateField(blank=True, null=True)
    fecha_hasta = models.DateField(blank=True, null=True)

    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.prestacion.codigo} - {self.prestacion.nombre}"
    


class PlanillaEntrega(BaseAbstractWithUser):
    medico = models.ForeignKey(
        "entidades.Medico",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="planilla_entrega"
    )
    observaciones = models.CharField(
        null=True,
        blank=True,
        max_length=500,
    )

class DetallePlanillaEntrega(BaseAbstractWithUser):
    planilla_entrega = models.ForeignKey(
        PlanillaEntrega,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    orden = models.ForeignKey(
        OrdenAutorizacion,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )



class PlanillaEntrega(BaseAbstractWithUser):
    medico = models.ForeignKey(
        "entidades.Medico",
        on_delete=models.PROTECT,
        related_name="planillas_entrega"
    )
    entregada = models.BooleanField(default=False)
    fecha_entrega = models.DateField(blank=True,null=True)
    observaciones = models.CharField(max_length=500, blank=True, null=True)
    anulada = models.BooleanField(default=False)
    fecha_anulacion = models.DateTimeField(blank=True, null=True)


class DetallePlanillaEntrega(BaseAbstractWithUser):
    planilla_entrega = models.ForeignKey(
        PlanillaEntrega,
        on_delete=models.CASCADE,
        related_name="detalles"
    )
    orden = models.ForeignKey(
        OrdenAutorizacion,
        on_delete=models.PROTECT,
        related_name="detalles_entrega"
    )