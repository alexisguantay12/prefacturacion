from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from applications.entidades.models import Medico, ObraSocial
from ..models import OrdenAutorizacion


@login_required
def gestion_ordenes(request):
    fecha_desde = request.GET.get("fecha_desde", "").strip()
    fecha_hasta = request.GET.get("fecha_hasta", "").strip()
    nombre = request.GET.get("nombre", "").strip()
    apellido = request.GET.get("apellido", "").strip()
    obra_social_id = request.GET.get("obra_social", "").strip()
    medico_tenencia_id = request.GET.get("medico_tenencia", "").strip()
    numero_orden = request.GET.get("numero_orden", "").strip()
    episodio = request.GET.get("episodio", "").strip()
    numero_preingreso = request.GET.get("numero_preingreso", "").strip()
    estado = request.GET.get("estado", "").strip()
    estado_entrega = request.GET.get("estado_entrega", "").strip()

    ordenes = (
        OrdenAutorizacion.objects
        .select_related(
            "preingreso",
            "preingreso__paciente",
            "preingreso__obra_social",
            "preingreso__plan",
            "medico",
            "medico_tenencia",
        )
        .annotate(
            cantidad_prestaciones=Count(
                "detalles",
                distinct=True,
            )
        )
        .order_by("-id")
    )

    if fecha_desde:
        try:
            fecha_desde_parseada = datetime.strptime(
                fecha_desde,
                "%Y-%m-%d",
            ).date()

            ordenes = ordenes.filter(
                fecha__gte=fecha_desde_parseada
            )
        except ValueError:
            pass

    if fecha_hasta:
        try:
            fecha_hasta_parseada = datetime.strptime(
                fecha_hasta,
                "%Y-%m-%d",
            ).date()

            ordenes = ordenes.filter(
                fecha__lte=fecha_hasta_parseada
            )
        except ValueError:
            pass

    if nombre:
        ordenes = ordenes.filter(
            preingreso__paciente__nombre__icontains=nombre
        )

    if apellido:
        ordenes = ordenes.filter(
            preingreso__paciente__apellido__icontains=apellido
        )

    if obra_social_id:
        ordenes = ordenes.filter(
            preingreso__obra_social_id=obra_social_id
        )

    if medico_tenencia_id == "sin_tenencia":
        ordenes = ordenes.filter(
            medico_tenencia__isnull=True
        )
    elif medico_tenencia_id:
        ordenes = ordenes.filter(
            medico_tenencia_id=medico_tenencia_id
        )

    if numero_orden:
        try:
            ordenes = ordenes.filter(
                id=int(numero_orden)
            )
        except (TypeError, ValueError):
            ordenes = ordenes.none()

    if episodio:
        ordenes = ordenes.filter(
            preingreso__episodio__icontains=episodio
        )

    if numero_preingreso:
        ordenes = ordenes.filter(
            preingreso__numero__icontains=numero_preingreso
        )

    if estado in ["pendiente", "autorizada", "anulada"]:
        ordenes = ordenes.filter(
            estado=estado
        )

    if estado_entrega == "entregadas":
        ordenes = ordenes.filter(
            esta_entregada=True
        )
    elif estado_entrega == "no_entregadas":
        ordenes = ordenes.filter(
            esta_entregada=False
        )

    paginator = Paginator(ordenes, 15)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    parametros = request.GET.copy()
    parametros.pop("page", None)

    context = {
        "page_obj": page_obj,
        "ordenes": page_obj.object_list,
        "medicos": (
            Medico.objects
            .all()
            .order_by("apellido", "nombre")
        ),
        "obras_sociales": (
            ObraSocial.objects
            .all()
            .order_by("nombre")
        ),
        "querystring": parametros.urlencode(),
    }

    return render(
        request,
        "gestion/orden/gestion_ordenes.html",
        context,
    )


@login_required
@require_GET
def detalle_orden_gestion_ajax(request, orden_id):
    orden = get_object_or_404(
        OrdenAutorizacion.objects
        .select_related(
            "preingreso",
            "preingreso__paciente",
            "preingreso__obra_social",
            "preingreso__plan",
            "preingreso__medico",
            "medico",
            "medico_tenencia",
            "user_autorizacion",
            "user_anulacion",
            "user_tenencia",
        )
        .prefetch_related(
            "detalles",
            "detalles__prestacion",
            "detalles__medico",
        ),
        id=orden_id,
    )

    preingreso = orden.preingreso
    paciente = preingreso.paciente

    detalles = []

    for detalle in orden.detalles.all().order_by("id"):
        detalles.append({
            "id": detalle.id,
            "codigo": detalle.prestacion.codigo or "",
            "prestacion": detalle.prestacion.nombre or "",
            "cantidad": detalle.cantidad or 0,
            "autorizada": detalle.autorizada,
            "medico": (
                str(detalle.medico)
                if detalle.medico
                else "No cargado"
            ),
            "honorarios_gastos": (
                detalle.get_honorarios_gastos_display()
                if detalle.honorarios_gastos
                else "-"
            ),
            "tipo_honorario": (
                detalle.get_tipo_honorario_display()
                if detalle.tipo_honorario
                else "-"
            ),
            "fecha_desde": (
                detalle.fecha_desde.strftime("%d/%m/%Y")
                if detalle.fecha_desde
                else "-"
            ),
            "fecha_hasta": (
                detalle.fecha_hasta.strftime("%d/%m/%Y")
                if detalle.fecha_hasta
                else "-"
            ),
            "observaciones": detalle.observaciones or "",
        })

    return JsonResponse({
        "ok": True,
        "orden": {
            "id": orden.id,
            "numero": f"{orden.id:06d}",
            "fecha": (
                orden.fecha.strftime("%d/%m/%Y")
                if orden.fecha
                else "-"
            ),
            "tipo": orden.get_tipo_display(),
            "estado": orden.estado,
            "estado_display": orden.get_estado_display(),
            "autorizada": bool(orden.autorizada),
            "esta_entregada": bool(orden.esta_entregada),
            "numero_cupon": orden.numero_cupon or "",
            "observaciones": orden.observaciones or "",
            "medico": (
                str(orden.medico)
                if orden.medico
                else "No cargado"
            ),
            "medico_tenencia": (
                str(orden.medico_tenencia)
                if orden.medico_tenencia
                else "Sin tenencia"
            ),
            "fecha_autorizacion": (
                orden.fecha_autorizacion.strftime("%d/%m/%Y")
                if orden.fecha_autorizacion
                else "-"
            ),
            "fecha_anulacion": (
                orden.fecha_anulacion.strftime("%d/%m/%Y")
                if orden.fecha_anulacion
                else "-"
            ),
            "fecha_tenencia": (
                orden.fecha_tenencia.strftime("%d/%m/%Y")
                if orden.fecha_tenencia
                else "-"
            ),
            "fecha_entrega": (
                orden.fecha_entrega.strftime("%d/%m/%Y")
                if orden.fecha_entrega
                else "-"
            ),
        },
        "paciente": {
            "nombre_completo": (
                f"{paciente.apellido}, {paciente.nombre}"
            ),
            "dni": paciente.dni or "-",
        },
        "preingreso": {
            "id": preingreso.id,
            "numero": preingreso.numero or "-",
            "episodio": preingreso.episodio or "-",
            "obra_social": str(preingreso.obra_social),
            "plan": (
                str(preingreso.plan)
                if preingreso.plan
                else "-"
            ),
            "numero_afiliado": (
                preingreso.numero_afiliado or "-"
            ),
            "fecha_ingreso": (
                preingreso.fecha_ingreso.strftime("%d/%m/%Y")
                if preingreso.fecha_ingreso
                else "-"
            ),
            "fecha_egreso": (
                preingreso.fecha_egreso.strftime("%d/%m/%Y")
                if preingreso.fecha_egreso
                else "-"
            ),
        },
        "detalles": detalles,
    })


@login_required
@require_POST
def autorizar_orden_gestion_ajax(request, orden_id):
    try:
        with transaction.atomic():
            orden = (
                OrdenAutorizacion.objects
                .select_for_update()
                .get(id=orden_id)
            )

            if orden.estado == "anulada":
                return JsonResponse({
                    "ok": False,
                    "mensaje": (
                        "No se puede autorizar una orden anulada."
                    ),
                }, status=400)

            if orden.estado == "autorizada":
                return JsonResponse({
                    "ok": False,
                    "mensaje": (
                        "La orden ya se encuentra autorizada."
                    ),
                }, status=400)

            fecha_actual = timezone.now()

            orden.estado = "autorizada"
            orden.autorizada = True
            orden.fecha_autorizacion = fecha_actual
            orden.user_autorizacion = request.user

            orden.save(
                update_fields=[
                    "estado",
                    "autorizada",
                    "fecha_autorizacion",
                    "user_autorizacion",
                ]
            )

            orden.detalles.update(
                autorizada=True
            )

    except OrdenAutorizacion.DoesNotExist:
        return JsonResponse({
            "ok": False,
            "mensaje": "La orden indicada no existe.",
        }, status=404)

    return JsonResponse({
        "ok": True,
        "mensaje": (
            f"La orden N.º {orden.id:06d} fue autorizada."
        ),
        "orden": {
            "id": orden.id,
            "estado": orden.estado,
            "estado_display": orden.get_estado_display(),
            "autorizada": True,
        },
    })


@login_required
@require_POST
def anular_orden_gestion_ajax(request, orden_id):
    motivo = request.POST.get(
        "motivo_anulacion",
        "",
    ).strip()

    if not motivo:
        return JsonResponse({
            "ok": False,
            "mensaje": (
                "Debe indicar el motivo de la anulación."
            ),
        }, status=400)

    try:
        with transaction.atomic():
            orden = (
                OrdenAutorizacion.objects
                .select_for_update()
                .get(id=orden_id)
            )

            if orden.estado == "anulada":
                return JsonResponse({
                    "ok": False,
                    "mensaje": (
                        "La orden ya se encuentra anulada."
                    ),
                }, status=400)

            if orden.esta_entregada:
                return JsonResponse({
                    "ok": False,
                    "mensaje": (
                        "No se puede anular una orden que ya fue entregada."
                    ),
                }, status=400)

            orden.estado = "anulada"
            orden.autorizada = False
            orden.fecha_anulacion = timezone.now()
            orden.user_anulacion = request.user
            orden.observaciones = (
                f"{orden.observaciones}\n"
                if orden.observaciones
                else ""
            ) + f"Motivo de anulación: {motivo}"

            orden.save(
                update_fields=[
                    "estado",
                    "autorizada",
                    "fecha_anulacion",
                    "user_anulacion",
                    "observaciones",
                ]
            )

            orden.detalles.update(
                autorizada=False
            )

    except OrdenAutorizacion.DoesNotExist:
        return JsonResponse({
            "ok": False,
            "mensaje": "La orden indicada no existe.",
        }, status=404)

    return JsonResponse({
        "ok": True,
        "mensaje": (
            f"La orden N.º {orden.id:06d} fue anulada."
        ),
        "orden": {
            "id": orden.id,
            "estado": orden.estado,
            "estado_display": orden.get_estado_display(),
            "autorizada": False,
        },
    })


@login_required
@require_POST
def cambiar_tenencia_gestion_ajax(request, orden_id):
    medico_id = request.POST.get(
        "medico_id",
        "",
    ).strip()
    

    if not medico_id:
        return JsonResponse({
            "ok": False,
            "mensaje": (
                "Debe seleccionar un médico para la tenencia."
            ),
        }, status=400)

    medico = get_object_or_404(
        Medico,
        id=medico_id,
    )

    try:
        with transaction.atomic():
            orden = (
                OrdenAutorizacion.objects
                .select_for_update()
                .get(id=orden_id)
            )

            if orden.estado == "anulada":
                return JsonResponse({
                    "ok": False,
                    "mensaje": (
                        "No se puede modificar la tenencia "
                        "de una orden anulada."
                    ),
                }, status=400)

            if orden.esta_entregada:
                return JsonResponse({
                    "ok": False,
                    "mensaje": (
                        "No se puede modificar la tenencia "
                        "de una orden que ya fue entregada."
                    ),
                }, status=400)

            orden.medico_tenencia = medico
            orden.fecha_tenencia = timezone.now()
            orden.user_tenencia = request.user

            orden.save(
                update_fields=[
                    "medico_tenencia",
                    "fecha_tenencia",
                    "user_tenencia",
                ]
            )

    except OrdenAutorizacion.DoesNotExist:
        return JsonResponse({
            "ok": False,
            "mensaje": "La orden indicada no existe.",
        }, status=404)

    return JsonResponse({
        "ok": True,
        "mensaje": (
            f"Se actualizó la tenencia de la orden "
            f"N.º {orden.id:06d}."
        ),
        "orden": {
            "id": orden.id,
            "medico_tenencia_id": medico.id,
            "medico_tenencia": str(medico),
        },
    })