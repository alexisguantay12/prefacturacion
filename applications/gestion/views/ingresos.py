from datetime import date
import json

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404

from applications.entidades.models import *
from ..models import *
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.utils import timezone

# =============================================================================
# INGRESOS
# =============================================================================
@login_required
def lista_ingresos(request):
    paciente = request.GET.get("paciente", "").strip()
    dni = request.GET.get("dni", "").strip()
    episodio = request.GET.get("episodio", "").strip()
    orden = request.GET.get("orden", "").strip()
    obra_social_id = request.GET.get("obra_social", "").strip()

    ingresos = (
        Preingreso.objects
        .select_related(
            "paciente",
            "obra_social",
            "plan",
            "medico",
            "servicio",
        )
        .annotate(
            total_ordenes=Count("ordenes", distinct=True)
        )
        .filter(
            estado__in=["ingresado", "cerrado"]
        )
        .order_by("-fecha_ingreso", "-id")
    )

    if paciente:
        ingresos = ingresos.filter(
            Q(paciente__apellido__icontains=paciente) |
            Q(paciente__nombre__icontains=paciente)
        )

    if dni:
        ingresos = ingresos.filter(
            paciente__dni__icontains=dni
        )

    if episodio:
        ingresos = ingresos.filter(
            episodio__icontains=episodio
        )

    if orden:
        try:
            orden_id = int(orden)

            ingresos = ingresos.filter(
                ordenes__id=orden_id
            ).distinct()

        except (TypeError, ValueError):
            ingresos = ingresos.none()

    if obra_social_id:
        ingresos = ingresos.filter(
            obra_social_id=obra_social_id
        )

    paginator = Paginator(ingresos, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    obras_sociales = ObraSocial.objects.all().order_by("nombre")

    return render(
        request,
        "gestion/ingreso/lista_ingresos.html",
        {
            "ingresos": page_obj,
            "page_obj": page_obj,
            "paciente": paciente,
            "dni": dni,
            "episodio": episodio,
            "orden": orden,
            "obra_social_id": obra_social_id,
            "obras_sociales": obras_sociales,
        }
    )
@login_required
def agregar_ingreso(request):
    obras_sociales = ObraSocial.objects.all().order_by("nombre")
    medicos = Medico.objects.all().order_by("apellido", "nombre")
    servicios = Servicio.objects.all().order_by("nombre")
    planes = Plan.objects.all().order_by("obra_social__nombre", "nombre")

    if request.method == "POST":
        paciente_id = request.POST.get("paciente")
        obra_social_id = request.POST.get("obra_social")
        plan_id = request.POST.get("plan") or None
        medico_id = request.POST.get("medico") or None
        servicio_id = request.POST.get("servicio") or None

        fecha_ingreso = request.POST.get("fecha_ingreso") or None
        numero_afiliado = request.POST.get("numero_afiliado", "").strip()
        diagnostico = request.POST.get("diagnostico", "").strip()

        contacto_nombre = request.POST.get("contacto_nombre", "").strip()
        contacto_dni = request.POST.get("contacto_dni", "").strip()
        contacto_parentesco = request.POST.get("contacto_parentesco", "").strip()
        contacto_telefono = request.POST.get("contacto_telefono", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()
        episodio = request.POST.get("episodio", "").strip()

        if not paciente_id:
            messages.error(request, "Debe seleccionar un paciente.")
            return redirect("gestion_app:agregar_ingreso")

        if not obra_social_id:
            messages.error(request, "Debe seleccionar una obra social.")
            return redirect("gestion_app:agregar_ingreso")

        if not fecha_ingreso:
            messages.error(request, "Debe indicar la fecha de ingreso.")
            return redirect("gestion_app:agregar_ingreso")

        paciente = Paciente.objects.filter(id=paciente_id).first()
        obra_social = ObraSocial.objects.filter(id=obra_social_id).first()

        if not paciente:
            messages.error(request, "El paciente seleccionado no existe.")
            return redirect("gestion_app:agregar_ingreso")

        if not obra_social:
            messages.error(request, "La obra social seleccionada no existe.")
            return redirect("gestion_app:agregar_ingreso")

        plan = Plan.objects.filter(id=plan_id).first() if plan_id else None
        medico = Medico.objects.filter(id=medico_id).first() if medico_id else None
        servicio = Servicio.objects.filter(id=servicio_id).first() if servicio_id else None

        if plan and plan.obra_social_id != obra_social.id:
            messages.error(request, "El plan seleccionado no corresponde a la obra social indicada.")
            return redirect("gestion_app:agregar_ingreso")

        try:
            with transaction.atomic():
                numerador, creado = Numerador.objects.select_for_update().get_or_create(
                    nombre="ingreso",
                    defaults={"ultimo": 0}
                )

                numerador.ultimo += 1
                numerador.save(update_fields=["ultimo"])

                ingreso = Preingreso.objects.create(
                    paciente=paciente,
                    obra_social=obra_social,
                    plan=plan,
                    numero_afiliado=numero_afiliado or None,
                    medico=medico,
                    es_preingreso= False,
                    servicio=servicio,
                    numero=numerador.ultimo,
                    fecha_ingreso=fecha_ingreso,
                    fecha_probable_ingreso=None,
                    diagnostico=diagnostico or None,
                    episodio=episodio,
                    contacto_nombre=contacto_nombre or None,
                    contacto_dni=contacto_dni or None,
                    contacto_parentesco=contacto_parentesco or None,
                    contacto_telefono=contacto_telefono or None,
                    observaciones=observaciones or None,
                    estado="ingresado",
                    user_made = request.user
                )

        except Exception:
            messages.error(request, "No se pudo guardar el ingreso. Intente nuevamente.")
            return redirect("gestion_app:agregar_ingreso")

        messages.success(request, f"El ingreso #{ingreso.numero} fue creado correctamente.")
        return redirect("gestion_app:lista_ingresos")

    return render(request, "gestion/ingreso/agregar_ingreso.html", {
        "obras_sociales": obras_sociales,
        "planes": planes,
        "medicos": medicos,
        "servicios": servicios,
    })

@login_required
def detalle_ingreso(request, preingreso_id):
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

    ordenes = (
        OrdenAutorizacion.objects
        .filter(preingreso=preingreso)
        .select_related("medico")
        .annotate(cantidad_prestaciones=Count("detalles"))
        .order_by("-created_at", "-id")
    )

    medicos = Medico.objects.all().order_by("apellido", "nombre")

    return render(request, "gestion/ingreso/detalle_ingreso.html", {
        "preingreso": preingreso,
        "ordenes": ordenes,
        "medicos": medicos,
    })


@login_required
def editar_ingreso(request, ingreso_id):
    ingreso = get_object_or_404(
        Preingreso,
        id=ingreso_id,
        estado="ingresado"
    )

    obras_sociales = ObraSocial.objects.all().order_by("nombre")
    medicos = Medico.objects.all().order_by("apellido", "nombre")
    servicios = Servicio.objects.all().order_by("nombre")
    planes = Plan.objects.all().order_by("obra_social__nombre", "nombre")

    if request.method == "POST":
        obra_social_id = request.POST.get("obra_social")
        plan_id = request.POST.get("plan") or None
        medico_id = request.POST.get("medico") or None
        servicio_id = request.POST.get("servicio") or None

        episodio = request.POST.get("episodio", "").strip()
        fecha_ingreso = request.POST.get("fecha_ingreso") or None
        numero_afiliado = request.POST.get("numero_afiliado", "").strip()
        diagnostico = request.POST.get("diagnostico", "").strip()

        contacto_nombre = request.POST.get("contacto_nombre", "").strip()
        contacto_dni = request.POST.get("contacto_dni", "").strip()
        contacto_parentesco = request.POST.get("contacto_parentesco", "").strip()
        contacto_telefono = request.POST.get("contacto_telefono", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()

        if not obra_social_id:
            messages.error(request, "Debe seleccionar una obra social.")
            return redirect("gestion_app:editar_ingreso", ingreso_id=ingreso.id)

        if not episodio:
            messages.error(request, "Debe indicar el número de episodio.")
            return redirect("gestion_app:editar_ingreso", ingreso_id=ingreso.id)

        if not fecha_ingreso:
            messages.error(request, "Debe indicar la fecha de ingreso.")
            return redirect("gestion_app:editar_ingreso", ingreso_id=ingreso.id)

        obra_social = ObraSocial.objects.filter(id=obra_social_id).first()

        if not obra_social:
            messages.error(request, "La obra social seleccionada no existe.")
            return redirect("gestion_app:editar_ingreso", ingreso_id=ingreso.id)

        numero_existente = Preingreso.objects.filter(
            episodio=episodio
        ).exclude(id=ingreso.id).exists()

        if numero_existente:
            messages.error(request, "Ya existe otro ingreso con ese número de episodio.")
            return redirect("gestion_app:editar_ingreso", ingreso_id=ingreso.id)

        plan = Plan.objects.filter(id=plan_id).first() if plan_id else None
        medico = Medico.objects.filter(id=medico_id).first() if medico_id else None
        servicio = Servicio.objects.filter(id=servicio_id).first() if servicio_id else None

        if plan and plan.obra_social_id != obra_social.id:
            messages.error(request, "El plan seleccionado no corresponde a la obra social indicada.")
            return redirect("gestion_app:editar_ingreso", ingreso_id=ingreso.id)

        try:
            with transaction.atomic():
                ingreso.obra_social = obra_social
                ingreso.plan = plan
                ingreso.medico = medico
                ingreso.servicio = servicio
                ingreso.episodio = episodio
                ingreso.fecha_ingreso = fecha_ingreso
                ingreso.fecha_probable_ingreso = None
                ingreso.numero_afiliado = numero_afiliado or None
                ingreso.diagnostico = diagnostico or None
                ingreso.contacto_nombre = contacto_nombre or None
                ingreso.contacto_dni = contacto_dni or None
                ingreso.contacto_parentesco = contacto_parentesco or None
                ingreso.contacto_telefono = contacto_telefono or None
                ingreso.observaciones = observaciones or None
                ingreso.estado = "ingresado"
                ingreso.user_updated=request.user
                ingreso.save()

        except Exception:
            messages.error(request, "No se pudo actualizar el ingreso. Intente nuevamente.")
            return redirect("gestion_app:editar_ingreso", ingreso_id=ingreso.id)

        messages.success(request, f"El ingreso #{ingreso.numero} fue actualizado correctamente.")
        return redirect("gestion_app:detalle_ingreso", preingreso_id=ingreso.id)

    return render(request, "gestion/ingreso/editar_ingreso.html", {
        "ingreso": ingreso,
        "obras_sociales": obras_sociales,
        "planes": planes,
        "medicos": medicos,
        "servicios": servicios,
    })


# =============================================================================
# INGRESO PROGRAMADO
# =============================================================================

@login_required
def agregar_ingreso_programado(request):
    obras_sociales = ObraSocial.objects.all().order_by("nombre")
    medicos = Medico.objects.all().order_by("apellido", "nombre")
    servicios = Servicio.objects.all().order_by("nombre")
    planes = Plan.objects.all().order_by("obra_social__nombre", "nombre")

    if request.method == "POST":
        preingreso_id = request.POST.get("preingreso_id")

        try:
            with transaction.atomic():
                preingreso = get_object_or_404(
                    Preingreso.objects.select_for_update(),
                    id=preingreso_id
                )

                if preingreso.estado in ["ingresado", "cerrado"]:
                    messages.error(request, "Este preingreso ya no está disponible para ingresar.")
                    return redirect("gestion_app:agregar_ingreso_programado")

                numerador, creado = Numerador.objects.select_for_update().get_or_create(
                    nombre="ingreso",
                    defaults={"ultimo": 0}
                )

                numerador.ultimo += 1
                numerador.save(update_fields=["ultimo"])

                preingreso.obra_social_id = request.POST.get("obra_social")
                preingreso.plan_id = request.POST.get("plan") or None
                preingreso.numero_afiliado = request.POST.get("numero_afiliado", "").strip() or None
                preingreso.numero = numerador.ultimo
                preingreso.fecha_ingreso = request.POST.get("fecha_ingreso") or None
                preingreso.servicio_id = request.POST.get("servicio") or None
                preingreso.medico_id = request.POST.get("medico") or None
                preingreso.origen_paciente = request.POST.get("origen_paciente") or "domicilio"
                preingreso.prioridad = request.POST.get("prioridad") or "programado"
                preingreso.diagnostico = request.POST.get("diagnostico", "").strip() or None
                preingreso.contacto_nombre = request.POST.get("contacto_nombre", "").strip() or None
                preingreso.contacto_dni = request.POST.get("contacto_dni", "").strip() or None
                preingreso.contacto_parentesco = request.POST.get("contacto_parentesco", "").strip() or None
                preingreso.contacto_telefono = request.POST.get("contacto_telefono", "").strip() or None
                preingreso.observaciones = request.POST.get("observaciones", "").strip() or None
                preingreso.episodio = request.POST.get("episodio")
                preingreso.estado = "ingresado"
                preingreso.user_updated= request.user
                preingreso.user_pasaje_internacion= request.user
                preingreso.fecha_pasaje_internacion=timezone.now()
                preingreso.save()

        except Exception:
            messages.error(request, "No se pudo registrar el ingreso programado. Intente nuevamente.")
            return redirect("gestion_app:agregar_ingreso_programado")

        messages.success(request, f"Ingreso programado registrado correctamente. Episodio #{preingreso.numero}")
        return redirect("gestion_app:lista_ingresos")

    return render(request, "gestion/ingreso/agregar_ingreso_programado.html", {
        "obras_sociales": obras_sociales,
        "planes": planes,
        "medicos": medicos,
        "servicios": servicios,
    })


# =============================================================================
# ÓRDENES DE INGRESO
# =============================================================================

@login_required
def agregar_orden_ingreso(request, preingreso_id):
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
            return redirect("gestion_app:agregar_orden_ingreso", preingreso_id=preingreso.id)

        medico = Medico.objects.filter(id=medico_id).first()

        if not medico:
            messages.error(request, "El médico seleccionado no es válido.")
            return redirect("gestion_app:agregar_orden_ingreso", preingreso_id=preingreso.id)

        if not detalles:
            messages.error(request, "Debe cargar al menos un detalle en la orden.")
            return redirect("gestion_app:agregar_orden_ingreso", preingreso_id=preingreso.id)

        try:
            with transaction.atomic():
                orden = OrdenAutorizacion.objects.create(
                    preingreso=preingreso,
                    fecha=fecha,
                    medico=medico,
                    observaciones=observaciones or None,
                    medico_tenencia=medico,
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
            return redirect("gestion_app:detalle_ingreso", preingreso_id=preingreso.id)

        except Exception as e:
            messages.error(request, f"Ocurrió un error al guardar la orden: {e}")
            return redirect("gestion_app:agregar_orden_ingreso", preingreso_id=preingreso.id)

    medico_default = medicos.filter(matricula="9063").first()

    return render(request, "gestion/orden/agregar_orden_ingreso.html", {
        "preingreso": preingreso,
        "medicos": medicos,
        "fecha_hoy": date.today().isoformat(),
        "medico_default": medico_default,
        "tipos_orden": OrdenAutorizacion.TIPOS,
        "honorarios_gastos": DetalleOrden.HONORARIOS_GASTOS,
        "tipos_honorario": DetalleOrden.TIPOS_HONORARIO,
    })