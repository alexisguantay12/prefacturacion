from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from applications.entidades.models import *
from ..models import *
from .ordenes import redirigir_segun_origen


# =============================================================================
# ACCIONES SOBRE ÓRDENES
# =============================================================================

@require_POST

def autorizar_orden(request, orden_id):
    orden = get_object_or_404(OrdenAutorizacion, id=orden_id)

    if orden.estado == "anulada":
        messages.error(request, "No se puede autorizar una orden anulada.")
        return redirigir_segun_origen(request, orden)

    orden.autorizada = True
    orden.estado = "autorizada"
    orden.save()

    orden.fecha_autorizacion= timezone.now()
    orden.user_autorizacion= request.user
    orden.detalles.update(autorizada=True)

    messages.success(request, "Orden autorizada correctamente.")
    return redirigir_segun_origen(request, orden)


@require_POST
def anular_orden(request, orden_id):
    orden = get_object_or_404(OrdenAutorizacion, id=orden_id)

    orden.estado = "anulada"
    orden.autorizada = False
    orden.fecha_anulacion = timezone.now()
    orden.motivo_anulacion = request.POST.get("motivo_anulacion", "").strip()
    orden.save()

    orden.user_anulacion= request.user
    orden.fecha_anulacion=timezone.now()
    orden.detalles.update(autorizada=False)

    messages.success(request, "Orden anulada correctamente.")
    return redirigir_segun_origen(request, orden)


@require_POST
def cambiar_tenencia_orden(request, orden_id):
    orden = get_object_or_404(OrdenAutorizacion, id=orden_id)

    if orden.estado == "anulada":
        messages.error(request, "No se puede cambiar la tenencia de una orden anulada.")
        return redirigir_segun_origen(request, orden)

    if orden.estado != "autorizada" and not orden.autorizada:
        messages.error(request, "Solo se puede cambiar la tenencia de una orden autorizada.")
        return redirigir_segun_origen(request, orden)

    medico_id = request.POST.get("medico_id")
    medico = get_object_or_404(Medico, id=medico_id)

    orden.user_tenencia=request.user
    orden.fecha_tenencia=timezone.now()

    orden.medico_tenencia = medico
    orden.save()

    messages.success(request, "Tenencia actualizada correctamente.")
    return redirigir_segun_origen(request, orden)