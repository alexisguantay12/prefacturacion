from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from django.contrib.auth.decorators import login_required
from ..models import *
 
from django.http import JsonResponse 
from django.views.decorators.http import require_GET 

# =============================================================================
# ÓRDENES GENERALES
# =============================================================================



@login_required
@require_GET
def detalle_orden_ajax(request, orden_id):
    """Datos de solo lectura para el modal de detalle de ingreso."""
    orden = get_object_or_404(
        OrdenAutorizacion.objects.select_related(
            "medico", "preingreso", "preingreso__paciente",
            "preingreso__obra_social", "preingreso__plan",
        ), pk=orden_id,
    )
    ingreso = orden.preingreso
    if ingreso.estado == "pendiente":
        return JsonResponse({"ok": False, "error": "La orden no pertenece a un ingreso."}, status=409)

    def texto(valor):
        return str(valor) if valor is not None and str(valor).strip() else "-"

    def fecha(valor):
        return valor.strftime("%d/%m/%Y") if valor else "-"

    detalles = orden.detalles.select_related("prestacion", "medico").order_by("id")
    anulada = orden.estado == "anulada"
    entregada = bool(orden.esta_entregada)
    autorizada = bool(orden.autorizada)
    estado = "Anulada" if anulada else "Autorizada y entregada" if entregada else "Autorizada" if autorizada else "Pendiente"
    return JsonResponse({
        "ok": True,
        "orden": {
            "id": orden.pk,
            "paciente": f"{ingreso.paciente.apellido}, {ingreso.paciente.nombre}",
            "dni": texto(ingreso.paciente.dni),
            "episodio": texto(ingreso.episodio),
            "numero_ingreso": texto(ingreso.numero or ingreso.pk),
            "cobertura": texto(ingreso.obra_social),
            "plan": texto(ingreso.plan),
            "fecha": fecha(orden.fecha),
            "medico": texto(orden.medico),
            "cupon": texto(orden.numero_cupon),
            "fecha_ejecucion": fecha(getattr(orden, "fecha_ejecucion", None)),
            "observaciones": orden.observaciones or "",
            "estado": estado,
            "anulada": anulada,
            "entregada": entregada,
            "autorizada": autorizada,
        },
        "detalles": [
            {
                "prestacion": texto(detalle.prestacion.nombre if detalle.prestacion else None),
                "codigo": texto(detalle.prestacion.codigo if detalle.prestacion else None),
                "medico": texto(detalle.medico),
                "cantidad": detalle.cantidad,
                "concepto": texto(detalle.get_honorarios_gastos_display()),
                "nivel": texto(detalle.get_tipo_honorario_display()),
                "desde": fecha(detalle.fecha_desde),
                "hasta": fecha(detalle.fecha_hasta),
            }
            for detalle in detalles
        ],
    })



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
    usar_medico_orden = request.GET.get("firma_medico_orden") == "1"

    orden = get_object_or_404(
        OrdenAutorizacion.objects.select_related(
            "medico",
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

    # Por defecto se utiliza el médico de cabecera del ingreso.
    medico_firma = orden.preingreso.medico

    # Si el usuario seleccionó la opción, se usa el médico de la orden.
    if usar_medico_orden and orden.medico:
        medico_firma = orden.medico 
    return render(request, "gestion/orden/imprimir_orden.html", {
        "orden": orden,
        "preingreso": orden.preingreso,
        "detalles": orden.detalles.all().order_by("id"),
        "fecha_impresion": timezone.now(),
        "duplicado": imprimir_duplicado,
        "medico_firma": medico_firma,
        "usar_medico_orden": usar_medico_orden,
    })


def redirigir_segun_origen(request, orden):
    es_preingreso = request.POST.get("preingreso") == "true"

    if es_preingreso:
        return redirect("gestion_app:detalle_preingreso", preingreso_id=orden.preingreso_id)

    return redirect("gestion_app:detalle_ingreso", preingreso_id=orden.preingreso_id)