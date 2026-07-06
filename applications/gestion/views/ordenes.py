from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from django.contrib.auth.decorators import login_required
from ..models import *


# =============================================================================
# ÓRDENES GENERALES
# =============================================================================

@login_required
def detalle_orden(request, orden_id):
    orden = get_object_or_404(
        OrdenAutorizacion.objects.select_related(
            "preingreso",
            "preingreso__paciente",
            "preingreso__obra_social",
            "preingreso__plan",
        ),
        pk=orden_id
    )

    detalles = (
        orden.detalles
        .select_related("prestacion", "medico")
        .all()
        .order_by("id")
    )

    return render(request, "gestion/orden/detalle_orden.html", {
        "orden": orden,
        "detalles": detalles,
    })

@login_required
def imprimir_orden(request, orden_id):
    imprimir_duplicado = request.GET.get("duplicado") == "1"
    
    orden = get_object_or_404(
        OrdenAutorizacion.objects.select_related(
            "preingreso",
            "preingreso__paciente",
            "preingreso__obra_social",
            "preingreso__plan",
            "preingreso__medico",
            "preingreso__servicio",
        ).prefetch_related(
            "detalles",
            "detalles__prestacion",
            "detalles__medico",
        ),
        id=orden_id
    )
    

    return render(request, "gestion/orden/imprimir_orden.html", {
        "orden": orden,
        "preingreso": orden.preingreso,
        "detalles": orden.detalles.all().order_by("id"),
        "fecha_impresion": timezone.now(),
        "duplicado": imprimir_duplicado,
    })


def redirigir_segun_origen(request, orden):
    es_preingreso = request.POST.get("preingreso") == "true"

    if es_preingreso:
        return redirect("gestion_app:detalle_preingreso", preingreso_id=orden.preingreso_id)

    return redirect("gestion_app:detalle_ingreso", preingreso_id=orden.preingreso_id)