from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from applications.gestion.models import PlanillaEntrega
from django.db import transaction

@login_required
def lista_planillas_entrega(request):
    query = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()

    planillas = (
        PlanillaEntrega.objects
        .select_related("medico")
        .annotate(total_ordenes=Count("detalles"))
        .filter(is_deleted=False)
        .order_by("-id")
    )

    if query:
        planillas = planillas.filter(
            Q(medico__apellido__icontains=query) |
            Q(medico__nombre__icontains=query) |
            Q(medico__matricula__icontains=query) |
            Q(observaciones__icontains=query) |
            Q(id__icontains=query)
        )

    if estado == "pendiente":
        planillas = planillas.filter(entregada=False, anulada=False)

    elif estado == "entregada":
        planillas = planillas.filter(entregada=True, anulada=False)

    elif estado == "anulada":
        planillas = planillas.filter(anulada=True)

    paginator = Paginator(planillas, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "planillas": page_obj.object_list,
        "page_obj": page_obj,
        "query": query,
        "estado": estado,
    }

    return render(request, "gestion/entregas/lista_planillas_entrega.html", context)


@login_required
@require_POST
@transaction.atomic
def anular_planilla_entrega(request, planilla_id):
    planilla = get_object_or_404(
        PlanillaEntrega.objects.select_for_update(),
        id=planilla_id,
        is_deleted=False
    )

    if planilla.anulada:
        return JsonResponse({
            "ok": False,
            "message": "La planilla ya se encuentra anulada."
        }, status=400)

    fecha_anulacion = timezone.now()

    # Obtener las órdenes asociadas a la planilla
    ordenes_ids = planilla.detalles.values_list(
        "orden_id",
        flat=True
    )

    # Bloquear las órdenes hasta finalizar la transacción
    ordenes = OrdenAutorizacion.objects.filter(
        id__in=ordenes_ids,
        deleted_at__isnull=True,
    )

    list(ordenes.select_for_update().values_list("id", flat=True))

    # Revertir los datos de entrega de todas las órdenes
    cantidad_ordenes = ordenes.update(
        esta_entregada=False,
        fecha_entrega=None,
        user_entrega=None 
    )

    # Anular la planilla
    planilla.anulada = True
    planilla.fecha_anulacion = fecha_anulacion
    planilla.user_anulacion = request.user
    planilla.user_updated = request.user

    planilla.save(update_fields=[
        "anulada",
        "fecha_anulacion",
        "user_anulacion",
        "user_updated",
    ])

    return JsonResponse({
        "ok": True,
        "message": (
            "La planilla fue anulada correctamente. "
            f"Se revirtieron {cantidad_ordenes} órdenes."
        )
    })

@login_required
@require_POST
@transaction.atomic
def entregar_planilla_entrega(request, planilla_id):
    planilla = get_object_or_404(
        PlanillaEntrega.objects.select_for_update(),
        id=planilla_id,
        is_deleted=False
    )

    if planilla.anulada:
        return JsonResponse({
            "ok": False,
            "message": "No se puede entregar una planilla anulada."
        }, status=400)

    if planilla.entregada:
        return JsonResponse({
            "ok": False,
            "message": "La planilla ya fue entregada."
        }, status=400)

    fecha_entrega = timezone.now()

    # Actualizar la planilla
    planilla.entregada = True
    planilla.fecha_entrega = planilla.fecha_entrega or fecha_entrega
    planilla.user_updated = request.user
    planilla.user_entrega = request.user

    planilla.save(update_fields=[
        "entregada",
        "fecha_entrega",
        "user_updated",
        "user_entrega",
    ])

    # Obtener los IDs de las órdenes incluidas en la planilla
    ordenes_ids = planilla.detalles.values_list(
        "orden_id",
        flat=True
    )

    # Actualizar todas las órdenes mediante una única consulta
    cantidad_ordenes = (
        OrdenAutorizacion.objects
        .filter(
            id__in=ordenes_ids,
            deleted_at__isnull=True,
        )
        .exclude(estado="anulada")
        .update(
            esta_entregada=True,
            fecha_entrega=fecha_entrega,
            user_entrega=request.user, 
        )
    )

    return JsonResponse({
        "ok": True,
        "message": (
            "La planilla fue marcada como entregada. "
            f"Se actualizaron {cantidad_ordenes} órdenes."
        ),
        "print_url": request.build_absolute_uri(
            redirect(
                "gestion_app:imprimir_planilla_entrega",
                planilla.id
            ).url
        )
    })

@login_required
def imprimir_planilla_entrega(request, planilla_id):
    planilla = get_object_or_404(
        PlanillaEntrega.objects.select_related("medico").prefetch_related(
            "detalles",
            "detalles__orden",
            "detalles__orden__preingreso",
            "detalles__orden__preingreso__paciente",
            "detalles__orden__preingreso__obra_social",
        ),
        id=planilla_id,
        is_deleted=False
    )

    context = {
        "planilla": planilla,
        "detalles": planilla.detalles.all(),
        "fecha_impresion": timezone.now(),
    }

    return render(request, "gestion/entregas/imprimir_planilla_entrega.html", context)






@login_required
def detalle_planilla_entrega(request, planilla_id):
    planilla = get_object_or_404(
        PlanillaEntrega.objects.select_related(
            "medico",
            "user_entrega",
            "user_anulacion",
        ),
        id=planilla_id,
        is_deleted=False,
    )

    detalles = (
        DetallePlanillaEntrega.objects
        .filter(
            planilla_entrega=planilla,
        )
        .select_related(
            "orden",
            "orden__preingreso",
            "orden__preingreso__paciente",
            "orden__medico",
            "orden__medico_tenencia",
            "user_made",
        )
        .prefetch_related(
            "orden__detalles__prestacion",
        )
        .order_by("orden__id")
    )

    context = {
        "planilla": planilla,
        "detalles": detalles,
        "total_ordenes": detalles.count(),
    }

    return render(
        request,
        "gestion/entregas/detalle_planilla_entrega.html",
        context,
    )




from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Exists, OuterRef
from applications.entidades.models import Medico
from applications.gestion.models import OrdenAutorizacion, PlanillaEntrega, DetallePlanillaEntrega
from datetime import date

@login_required
def confeccionar_planilla_entrega(request):
    medico_id = request.GET.get("medico") or request.POST.get("medico")
    medico = None
    ordenes = []

    ordenes_pendientes_de_entrega = OrdenAutorizacion.objects.filter(
        medico_tenencia_id=OuterRef("pk"),
        deleted_at__isnull=True,
        esta_entregada=False,
    ).exclude(
        estado="anulada"
    )

    medicos = (
        Medico.objects
        .filter(is_deleted=False)
        .annotate(
            tiene_ordenes_pendientes=Exists(
                ordenes_pendientes_de_entrega
            )
        )
        .filter(tiene_ordenes_pendientes=True)
        .order_by("apellido", "nombre")
    )

    if medico_id:
        medico = medicos.filter(id=medico_id).first()

        if medico:
            ordenes = (
                OrdenAutorizacion.objects
                .select_related(
                    "preingreso",
                    "preingreso__paciente",
                    "preingreso__obra_social",
                    "medico_tenencia",
                )
                .filter(
                    is_deleted=False,
                    esta_entregada=False,
                    medico_tenencia_id=medico_id,
                )
                .exclude(
                    estado="anulada"
                )
                .order_by("fecha", "id")
            )

    if request.method == "POST":
        accion = request.POST.get("accion")
        ordenes_ids = request.POST.getlist("ordenes")
        observaciones = request.POST.get(
            "observaciones",
            "",
        ).strip()
        fecha_entrega = request.POST.get("fecha_entrega") or None

        if not medico_id:
            messages.error(
                request,
                "Debe seleccionar un médico.",
            )
            return redirect(
                "gestion_app:confeccionar_planilla_entrega"
            )

        if not medico:
            messages.error(
                request,
                "El médico seleccionado no tiene órdenes pendientes de entrega.",
            )
            return redirect(
                "gestion_app:confeccionar_planilla_entrega"
            )

        if not ordenes_ids:
            messages.error(
                request,
                "Debe seleccionar al menos una orden autorizada.",
            )
            return redirect(
                f"{request.path}?medico={medico_id}"
            )

        if accion not in ["pendiente", "entregar"]:
            messages.error(
                request,
                "Acción inválida.",
            )
            return redirect(
                f"{request.path}?medico={medico_id}"
            )

        with transaction.atomic():
            ordenes_seleccionadas = (
                OrdenAutorizacion.objects
                .select_for_update()
                .filter(
                    id__in=ordenes_ids,
                    deleted_at__isnull=True,
                    medico_tenencia_id=medico_id,
                    esta_entregada=False,
                    autorizada=True,
                    estado="autorizada",
                )
            )

            if ordenes_seleccionadas.count() != len(ordenes_ids):
                messages.error(
                    request,
                    (
                        "Hay órdenes seleccionadas que no están "
                        "autorizadas o ya fueron incluidas en otra planilla."
                    ),
                )
                return redirect(
                    f"{request.path}?medico={medico_id}"
                )

            planilla = PlanillaEntrega.objects.create(
                medico_id=medico_id,
                fecha_entrega=(
                    fecha_entrega
                    if accion == "entregar"
                    else None
                ),
                user_entrega=(
                    request.user
                    if accion == "entregar"
                    else None
                ),                                
                observaciones=observaciones,
                entregada=accion == "entregar",
                anulada=False,
                user_made=request.user,
            )

            detalles = [
                DetallePlanillaEntrega(
                    planilla_entrega=planilla,
                    orden=orden,
                    user_made=request.user,
                )
                for orden in ordenes_seleccionadas
            ]

            DetallePlanillaEntrega.objects.bulk_create(detalles)

            OrdenAutorizacion.objects.filter(
                id__in=ordenes_seleccionadas.values_list(
                    "id",
                    flat=True,
                )
            ).update(
                esta_entregada=True,
                fecha_entrega=timezone.now(),
                user_entrega=request.user,
            )

        if accion == "entregar":
            return redirect(
                "gestion_app:imprimir_planilla_entrega",
                planilla.id,
            )

        messages.success(
            request,
            (
                "La planilla fue confeccionada y quedó "
                "pendiente de entrega física."
            ),
        )
        return redirect(
            "gestion_app:lista_planillas_entrega"
        )

    context = {
        "medicos": medicos,
        "medico": medico,
        "medico_id": medico_id,
        "ordenes": ordenes,
        "fecha_hoy": date.today().isoformat(),
    }

    return render(
        request,
        "gestion/entregas/confeccionar_planilla_entrega.html",
        context,
    )