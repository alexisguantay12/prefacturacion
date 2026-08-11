from datetime import date,datetime
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from applications.entidades.models import *
from ..models import *
from django.core.paginator import Paginator 

# =============================================================================
# PREINGRESOS
# =============================================================================

@login_required
def lista_preingresos(request):
    query = request.GET.get("q", "").strip()
    obra_social_id = request.GET.get("obra_social", "").strip()

    preingresos = (
        Preingreso.objects
        .select_related("paciente", "obra_social", "medico", "servicio", "plan")
        .annotate(
            total_ordenes=Count("ordenes", distinct=True),
            ordenes_autorizadas=Count(
                "ordenes",
                filter=Q(ordenes__autorizada=True),
                distinct=True
            ),
            ordenes_pendientes=Count(
                "ordenes",
                filter=Q(ordenes__autorizada=False),
                distinct=True
            ),
        )
        .exclude(estado__in=["ingresado", "cerrado"])
        .order_by("-created_at", "-id")
    )

    if query:
        preingresos = preingresos.filter(
            Q(id__icontains=query) |
            Q(numero__icontains=query) |
            Q(paciente__nombre__icontains=query) |
            Q(paciente__apellido__icontains=query) |
            Q(paciente__dni__icontains=query)
        )

    if obra_social_id:
        preingresos = preingresos.filter(obra_social_id=obra_social_id)

    paginator = Paginator(preingresos, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    obras_sociales = ObraSocial.objects.all().order_by("nombre")

    return render(request, "gestion/preingreso/lista_preingresos.html", {
        "preingresos": page_obj,
        "page_obj": page_obj,
        "query": query,
        "obra_social_id": obra_social_id,
        "obras_sociales": obras_sociales,
    })


@login_required
def agregar_preingreso(request):
    obras_sociales = ObraSocial.objects.all().order_by("nombre")
    medicos = Medico.objects.all().order_by("apellido", "nombre")
    servicios = Servicio.objects.all().order_by("nombre")
    planes = Plan.objects.all().order_by("obra_social__nombre", "nombre")

    def render_form(paciente_seleccionado=None):
        return render(request, "gestion/preingreso/agregar_preingreso.html", {
            "obras_sociales": obras_sociales,
            "planes": planes,
            "medicos": medicos,
            "servicios": servicios,
            "form_data": request.POST,
            "paciente_seleccionado": paciente_seleccionado,
        })

    if request.method == "POST":
        paciente_id = request.POST.get("paciente")
        obra_social_id = request.POST.get("obra_social")
        plan_id = request.POST.get("plan") or None
        medico_id = request.POST.get("medico") or None
        servicio_id = request.POST.get("servicio") or None

        fecha_probable_ingreso = request.POST.get("fecha_probable_ingreso") or None
        numero_afiliado = request.POST.get("numero_afiliado", "").strip()
        diagnostico = request.POST.get("diagnostico", "").strip()
        origen_paciente = request.POST.get("origen_paciente") or "domicilio"
        prioridad = request.POST.get("prioridad") or "normal"

        contacto_nombre = request.POST.get("contacto_nombre", "").strip()
        contacto_dni = request.POST.get("contacto_dni", "").strip()
        contacto_parentesco = request.POST.get("contacto_parentesco", "").strip()
        contacto_telefono = request.POST.get("contacto_telefono", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()
        paciente_telefono = request.POST.get("paciente_telefono", "").strip()

        paciente = Paciente.objects.filter(id=paciente_id).first() if paciente_id else None
        obra_social = ObraSocial.objects.filter(id=obra_social_id).first() if obra_social_id else None

        if not paciente_id:
            messages.error(request, "Debe seleccionar un paciente.")
            return render_form()

        if not paciente:
            messages.error(request, "El paciente seleccionado no existe.")
            return render_form()

        if not obra_social_id:
            messages.error(request, "Debe seleccionar una obra social.")
            return render_form(paciente)

        if not obra_social:
            messages.error(request, "La obra social seleccionada no existe.")
            return render_form(paciente)

        if not fecha_probable_ingreso:
            messages.error(request, "Debe indicar la fecha probable de ingreso.")
            return render_form(paciente)

        plan = Plan.objects.filter(id=plan_id).first() if plan_id else None
        medico = Medico.objects.filter(id=medico_id).first() if medico_id else None
        servicio = Servicio.objects.filter(id=servicio_id).first() if servicio_id else None

        if plan and plan.obra_social_id != obra_social.id:
            messages.error(request, "El plan seleccionado no corresponde a la obra social indicada.")
            return render_form(paciente)

        try:
            with transaction.atomic():
                paciente.telefono = paciente_telefono
                paciente.save(update_fields=["telefono"])

                preingreso = Preingreso.objects.create(
                    paciente=paciente,
                    obra_social=obra_social,
                    plan=plan,
                    numero_afiliado=numero_afiliado or None,
                    medico=medico,
                    servicio=servicio,
                    fecha_probable_ingreso=fecha_probable_ingreso,
                    diagnostico=diagnostico or None,
                    origen_paciente=origen_paciente,
                    prioridad=prioridad,
                    contacto_nombre=contacto_nombre or None,
                    contacto_dni=contacto_dni or None,
                    contacto_parentesco=contacto_parentesco or None,
                    contacto_telefono=contacto_telefono or None,
                    observaciones=observaciones or None,
                    estado="pendiente",
                    user_made=request.user
                )

        except Exception:
            messages.error(request, "No se pudo guardar el preingreso. Intente nuevamente.")
            return render_form(paciente)

        messages.success(request, f"El preingreso #{preingreso.id} fue creado correctamente.")
        return redirect("gestion_app:lista_preingresos")

    return render(request, "gestion/preingreso/agregar_preingreso.html", {
        "obras_sociales": obras_sociales,
        "planes": planes,
        "medicos": medicos,
        "servicios": servicios,
        "form_data": {},
        "paciente_seleccionado": None,
    })

@login_required
def detalle_preingreso(request, preingreso_id):
    preingreso = get_object_or_404(
        Preingreso.objects.select_related(
            "paciente",
            "obra_social",
            "plan",
            "medico",
            "servicio",
        ),
        id=preingreso_id,
    )

    medicos = Medico.objects.all().order_by(
        "apellido",
        "nombre",
    )

    ordenes = list(
        OrdenAutorizacion.objects
        .filter(preingreso=preingreso)
        .select_related(
            "medico",
            "medico_tenencia",
        )
        .annotate(
            cantidad_prestaciones=Count(
                "detalles",
                filter=Q(
                    detalles__deleted_at__isnull=True
                ),
                distinct=True,
            )
        )
        .order_by("-created_at", "-id")
    )

    hoy = date.today()

    for orden in ordenes:
        orden.puede_editar = False
        orden.puede_editar_codigos = False
        orden.dias_transcurridos = None

        fecha_orden = orden.fecha

        if not fecha_orden:
            continue

        if isinstance(fecha_orden, datetime):
            fecha_orden = fecha_orden.date()

        dias_transcurridos = (hoy - fecha_orden).days

        orden.dias_transcurridos = dias_transcurridos

        orden.puede_editar = (
            orden.estado != "anulada"
            and 0 <= dias_transcurridos <= 45
        )

        orden.puede_editar_codigos = (
            orden.puede_editar
            and dias_transcurridos <= 14
            and not orden.autorizada
        )

    return render(
        request,
        "gestion/preingreso/detalle_preingreso.html",
        {
            "preingreso": preingreso,
            "ordenes": ordenes,
            "medicos": medicos,
        },
    )

@login_required
def editar_preingreso(request, preingreso_id):
    preingreso = get_object_or_404(Preingreso, id=preingreso_id)

    obras_sociales = ObraSocial.objects.all().order_by("nombre")
    planes = Plan.objects.all().order_by("nombre")
    medicos = Medico.objects.all().order_by("apellido", "nombre")
    servicios = Servicio.objects.all().order_by("nombre")

    if request.method == "POST":
        with transaction.atomic():
            obra_social_id = request.POST.get("obra_social") or None
            plan_id = request.POST.get("plan") or None
            medico_id = request.POST.get("medico") or None
            servicio_id = request.POST.get("servicio") or None

            preingreso.fecha_probable_ingreso = request.POST.get("fecha_probable_ingreso") or None
            preingreso.diagnostico = request.POST.get("diagnostico", "").strip()
            preingreso.origen_paciente = request.POST.get("origen_paciente", "").strip()
            preingreso.numero_afiliado = request.POST.get("numero_afiliado", "").strip()

            preingreso.contacto_nombre = request.POST.get("contacto_nombre", "").strip()
            preingreso.contacto_dni = request.POST.get("contacto_dni", "").strip()
            preingreso.contacto_parentesco = request.POST.get("contacto_parentesco", "").strip()
            preingreso.contacto_telefono = request.POST.get("contacto_telefono", "").strip()

            preingreso.obra_social = ObraSocial.objects.filter(id=obra_social_id).first() if obra_social_id else None
            preingreso.plan = Plan.objects.filter(id=plan_id).first() if plan_id else None
            preingreso.medico = Medico.objects.filter(id=medico_id).first() if medico_id else None
            preingreso.servicio = Servicio.objects.filter(id=servicio_id).first() if servicio_id else None
            preingreso.user_updated=request.user
            preingreso.save()

            messages.success(request, "Preingreso actualizado correctamente.")
            return redirect("gestion_app:detalle_preingreso", preingreso_id=preingreso.id)

    return render(request, "gestion/preingreso/editar_preingreso.html", {
        "preingreso": preingreso,
        "obras_sociales": obras_sociales,
        "planes": planes,
        "medicos": medicos,
        "servicios": servicios,
    })

@login_required
def lista_ordenes_preingreso(request, preingreso_id):
    preingreso = get_object_or_404(
        Preingreso.objects.select_related("paciente", "obra_social", "medico", "servicio"),
        id=preingreso_id
    )

    ordenes = OrdenAutorizacion.objects.filter(preingreso=preingreso).order_by("-created_at", "-id")

    return render(request, "gestion/preingreso/lista_ordenes_preingreso.html", {
        "preingreso": preingreso,
        "ordenes": ordenes,
    })

@login_required
def imprimir_preingreso(request, preingreso_id):
    preingreso = get_object_or_404(
        Preingreso.objects.select_related(
            "paciente",
            "obra_social",
            "plan",
            "medico",
            "servicio",
        ),
        id=preingreso_id
    )

    return render(request, "gestion/preingreso/imprimir_preingreso.html", {
        "preingreso": preingreso,
        "fecha_impresion": timezone.now(),
    })


# =============================================================================
# ÓRDENES DE PREINGRESO
# =============================================================================

@login_required
def agregar_orden_preingreso(request, preingreso_id):
    preingreso = get_object_or_404(
        Preingreso.objects.select_related(
            "paciente",
            "obra_social",
            "plan",
            "medico",
            "servicio",
        ),
        id=preingreso_id
    )

    medicos = Medico.objects.all().order_by("apellido", "nombre")

    if request.method == "POST":
        fecha = request.POST.get("fecha") or None
        medico_id = request.POST.get("medico") or None
        observaciones = request.POST.get("observaciones", "").strip()
        detalles_json = request.POST.get("detalles_json", "[]")

        try:
            detalles = json.loads(detalles_json)
        except json.JSONDecodeError:
            detalles = []

        if not medico_id:
            messages.error(request, "Debe seleccionar el médico de la orden.")
            return redirect("gestion_app:agregar_orden_preingreso", preingreso_id=preingreso.id)

        medico = Medico.objects.filter(id=medico_id).first()

        if not medico:
            messages.error(request, "El médico seleccionado no es válido.")
            return redirect("gestion_app:agregar_orden_preingreso", preingreso_id=preingreso.id)

        if not detalles:
            messages.error(request, "Debe cargar al menos un detalle en la orden.")
            return redirect("gestion_app:agregar_orden_preingreso", preingreso_id=preingreso.id)

        try:
            with transaction.atomic():
                orden = OrdenAutorizacion.objects.create(
                    preingreso=preingreso,
                    fecha=fecha,
                    medico=medico,
                    medico_tenencia=medico,
                    observaciones=observaciones or None,
                    user_made=request.user
                )

                for item in detalles:
                    prestacion_id = item.get("prestacion_id")

                    if not prestacion_id:
                        continue

                    prestacion = get_object_or_404(Prestacion, id=prestacion_id)

                    DetalleOrden.objects.create(
                        orden=orden,
                        prestacion=prestacion,
                        medico=medico,
                        cantidad=item.get("cantidad") or 1,
                        honorarios_gastos=item.get("honorarios_gastos") or None,
                        tipo_honorario=item.get("tipo_honorario") or None,
                        fecha_desde=item.get("fecha_desde") or None,
                        fecha_hasta=item.get("fecha_hasta") or None,
                        observaciones=item.get("observaciones") or None,
                    )

            messages.success(request, "La orden fue cargada correctamente.")
            return redirect("gestion_app:detalle_preingreso", preingreso_id=preingreso.id)

        except Exception as e:
            messages.error(request, f"Ocurrió un error al guardar la orden: {e}")
            return redirect("gestion_app:agregar_orden_preingreso", preingreso_id=preingreso.id)

    medico_default = medicos.filter(matricula="9063").first()

    return render(request, "gestion/orden/agregar_orden_preingreso.html", {
        "preingreso": preingreso,
        "medicos": medicos,
        "fecha_hoy": date.today().isoformat(),
        "medico_default": medico_default,
        "tipos_orden": OrdenAutorizacion.TIPOS,
        "honorarios_gastos": DetalleOrden.HONORARIOS_GASTOS,
        "tipos_honorario": DetalleOrden.TIPOS_HONORARIO,
    })

@login_required
def detalle_orden_preingreso(request, orden_id):
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

    return render(request, "gestion/orden/detalle_orden_preingreso.html", {
        "orden": orden,
        "detalles": detalles,
    })