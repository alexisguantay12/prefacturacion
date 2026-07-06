from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from applications.gestion.models import PlanillaEntrega


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
def anular_planilla_entrega(request, planilla_id):
    planilla = get_object_or_404(
        PlanillaEntrega,
        id=planilla_id,
        is_deleted=False
    )

    if planilla.entregada:
        return JsonResponse({
            "ok": False,
            "message": "No se puede anular una planilla ya entregada."
        }, status=400)

    if planilla.anulada:
        return JsonResponse({
            "ok": False,
            "message": "La planilla ya se encuentra anulada."
        }, status=400)

    planilla.anulada = True
    planilla.fecha_anulacion = timezone.now()
    planilla.user_updated = request.user
    planilla.save()

    return JsonResponse({
        "ok": True,
        "message": "La confección fue anulada correctamente."
    })


@login_required
@require_POST
def entregar_planilla_entrega(request, planilla_id):
    planilla = get_object_or_404(
        PlanillaEntrega,
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

    planilla.entregada = True

    if not planilla.fecha_entrega:
        planilla.fecha_entrega = timezone.now()

    planilla.user_updated = request.user
    planilla.save()

    return JsonResponse({
        "ok": True,
        "message": "La planilla fue marcada como entregada.",
        "print_url": request.build_absolute_uri(
            redirect("gestion_app:imprimir_planilla_entrega", planilla.id).url
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









from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect
from django.utils import timezone

from applications.entidades.models import Medico
from applications.gestion.models import OrdenAutorizacion, PlanillaEntrega, DetallePlanillaEntrega
from datetime import date

@login_required
def confeccionar_planilla_entrega(request):
    medico_id = request.GET.get("medico") or request.POST.get("medico")
    medico = None
    ordenes = []

    medicos = Medico.objects.filter(
        is_deleted=False
    ).order_by("apellido", "nombre")

    if medico_id:
        medico = Medico.objects.filter(id=medico_id).first()

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
            .order_by("fecha", "id")
        )

    if request.method == "POST":
        accion = request.POST.get("accion")
        ordenes_ids = request.POST.getlist("ordenes")
        observaciones = request.POST.get("observaciones", "").strip()
        fecha_entrega = request.POST.get("fecha_entrega") or None

        if not medico_id:
            messages.error(request, "Debe seleccionar un médico.")
            return redirect("gestion_app:confeccionar_planilla_entrega")

        if not ordenes_ids:
            messages.error(request, "Debe seleccionar al menos una orden autorizada.")
            return redirect(f"{request.path}?medico={medico_id}")

        if accion not in ["pendiente", "entregar"]:
            messages.error(request, "Acción inválida.")
            return redirect(f"{request.path}?medico={medico_id}")

        with transaction.atomic():
            ordenes_seleccionadas = (
                OrdenAutorizacion.objects
                .select_for_update()
                .filter(
                    id__in=ordenes_ids,
                    is_deleted=False,
                    medico_tenencia_id=medico_id,
                    esta_entregada=False,
                    autorizada=True,
                    estado="autorizada",
                )
            )

            if ordenes_seleccionadas.count() != len(ordenes_ids):
                messages.error(
                    request,
                    "Hay órdenes seleccionadas que no están autorizadas o ya fueron incluidas en otra planilla."
                )
                return redirect(f"{request.path}?medico={medico_id}")

            planilla = PlanillaEntrega.objects.create(
                medico_id=medico_id,
                fecha_entrega=fecha_entrega if accion == "entregar" else None,
                observaciones=observaciones,
                entregada=True if accion == "entregar" else False,
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
                id__in=ordenes_seleccionadas.values_list("id", flat=True)
            ).update(
                esta_entregada=True,
                fecha_entrega=timezone.now(),
                user_entrega=request.user,
            )

        if accion == "entregar":
            return redirect("gestion_app:imprimir_planilla_entrega", planilla.id)

        messages.success(
            request,
            "La planilla fue confeccionada y quedó pendiente de entrega física."
        )
        return redirect("gestion_app:lista_planillas_entrega")
    context = {
        "medicos": medicos,
        "medico": medico,
        "medico_id": medico_id,
        "ordenes": ordenes,
        "fecha_hoy": date.today().isoformat(),
    }

    return render(request, "gestion/entregas/confeccionar_planilla_entrega.html", context)