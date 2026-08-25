from django.urls import path
from django.db import IntegrityError
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

from .models import Servicio, Paciente, Medico, ObraSocial, Prestacion, Plan
from django.contrib.auth.decorators import login_required

# ============================================================
# HELPERS
# ============================================================

def paginar(request, queryset, cantidad=15):
    paginator = Paginator(queryset, cantidad)
    page_number = request.GET.get("page")
    return paginator.get_page(page_number)


def asignar_usuario_si_existe(obj, request):
    """
    Helper defensivo por si BaseAbstractWithUser tiene campos de auditoría.
    No rompe si el modelo no los tiene.
    """
    if request.user.is_authenticated:
        if hasattr(obj, "user_created") and not obj.pk:
            obj.user_created = request.user
        if hasattr(obj, "user_updated"):
            obj.user_updated = request.user
        if hasattr(obj, "usuario_creacion") and not obj.pk:
            obj.usuario_creacion = request.user
        if hasattr(obj, "usuario_modificacion"):
            obj.usuario_modificacion = request.user
        if hasattr(obj, "created_by") and not obj.pk:
            obj.created_by = request.user
        if hasattr(obj, "updated_by"):
            obj.updated_by = request.user


# ============================================================
# SERVICIOS
# ============================================================

@login_required
def listado_servicios(request):
    buscar = request.GET.get("buscar", "").strip()

    servicios = Servicio.objects.all().order_by("nombre")

    if buscar:
        servicios = servicios.filter(
            Q(nombre__icontains=buscar) |
            Q(descripcion__icontains=buscar)
        )

    page_obj = paginar(request, servicios)

    return render(request, "entidades/servicio/listado_servicios.html", {
        "page_obj": page_obj,
        "buscar": buscar,
    })

@login_required
def agregar_servicio(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()

        if not nombre:
            messages.error(request, "El nombre del servicio es obligatorio.")
            return redirect("entidades_app:agregar_servicio")

        try:
            servicio = Servicio(
                nombre=nombre,
                descripcion=descripcion or None,
            ) 
            servicio.save()

            messages.success(request, "Servicio agregado correctamente.")
            return redirect("entidades_app:listado_servicios")

        except IntegrityError:
            messages.error(request, "Ya existe un servicio con ese nombre.")
            return redirect("entidades_app:agregar_servicio")

    return render(request, "entidades/servicio/agregar_servicio.html")

@login_required
def editar_servicio(request, pk):
    servicio = get_object_or_404(Servicio, pk=pk)

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()

        if not nombre:
            messages.error(request, "El nombre del servicio es obligatorio.")
            return redirect("entidades_app:editar_servicio", pk=servicio.pk)

        try:
            servicio.nombre = nombre
            servicio.descripcion = descripcion or None 
            servicio.save()

            messages.success(request, "Servicio actualizado correctamente.")
            return redirect("entidades_app:listado_servicios")

        except IntegrityError:
            messages.error(request, "Ya existe otro servicio con ese nombre.")
            return redirect("entidades_app:editar_servicio", pk=servicio.pk)

    return render(request, "entidades/servicio/editar_servicio.html", {
        "servicio": servicio,
    })

@login_required
def eliminar_servicio(request, pk):
    servicio = get_object_or_404(Servicio, pk=pk)

    if request.method == "POST":
        try:
            servicio.delete()
            messages.success(request, "Servicio eliminado correctamente.")
            return redirect("entidades_app:listado_servicios")
        except Exception:
            messages.error(request, "No se puede eliminar el servicio porque tiene registros relacionados.")
            return redirect("entidades_app:listado_servicios")

    return redirect("entidades_app:listado_servicios")


# ============================================================
# PACIENTES
# ============================================================
@login_required
def listado_pacientes(request):
    buscar = request.GET.get("buscar", "").strip()

    pacientes = Paciente.objects.all().order_by("apellido", "nombre")

    if buscar:
        pacientes = pacientes.filter(
            Q(nombre__icontains=buscar) |
            Q(apellido__icontains=buscar) |
            Q(dni__icontains=buscar) |
            Q(telefono__icontains=buscar)
        )

    page_obj = paginar(request, pacientes)

    return render(request, "entidades/paciente/listado_pacientes.html", {
        "page_obj": page_obj,
        "buscar": buscar,
    })

@login_required
def agregar_paciente(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        apellido = request.POST.get("apellido", "").strip()
        dni = request.POST.get("dni", "").strip()
        fecha_nacimiento = request.POST.get("fecha_nacimiento") or None
        genero = request.POST.get("genero") or None
        telefono = request.POST.get("telefono", "").strip()
        direccion = request.POST.get("direccion", "").strip()
        nacionalidad = request.POST.get("nacionalidad", "").strip()
        provincia = request.POST.get("provincia", "").strip()

        if not nombre or not apellido or not dni:
            messages.error(request, "Nombre, apellido y DNI son obligatorios.")
            return redirect("entidades_app:agregar_paciente")

        if Paciente.objects.filter(dni=dni).exists():
            messages.error(request, "Ya existe un paciente registrado con ese DNI.")
            return redirect("entidades_app:agregar_paciente")

        paciente = Paciente(
            nombre=nombre,
            apellido=apellido,
            dni=dni,
            fecha_nacimiento=fecha_nacimiento,
            genero=genero,
            telefono=telefono or None,
            direccion=direccion or None,
            nacionalidad=nacionalidad or None,
            provincia=provincia or None,
        ) 
        paciente.save()

        messages.success(request, "Paciente agregado correctamente.")
        return redirect("entidades_app:listado_pacientes")

    return render(request, "entidades/paciente/agregar_paciente.html")

@login_required
def editar_paciente(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        apellido = request.POST.get("apellido", "").strip()
        dni = request.POST.get("dni", "").strip()
        fecha_nacimiento = request.POST.get("fecha_nacimiento") or None
        genero = request.POST.get("genero") or None
        telefono = request.POST.get("telefono", "").strip()
        direccion = request.POST.get("direccion", "").strip()
        nacionalidad = request.POST.get("nacionalidad", "").strip()
        provincia = request.POST.get("provincia", "").strip()

        if not nombre or not apellido or not dni:
            messages.error(request, "Nombre, apellido y DNI son obligatorios.")
            return redirect("entidades_app:editar_paciente", pk=paciente.pk)

        if Paciente.objects.filter(dni=dni).exclude(pk=paciente.pk).exists():
            messages.error(request, "Ya existe otro paciente registrado con ese DNI.")
            return redirect("entidades_app:editar_paciente", pk=paciente.pk)

        paciente.nombre = nombre
        paciente.apellido = apellido
        paciente.dni = dni
        paciente.fecha_nacimiento = fecha_nacimiento
        paciente.genero = genero
        paciente.telefono = telefono or None
        paciente.direccion = direccion or None
        paciente.nacionalidad = nacionalidad or None
        paciente.provincia = provincia or None
 
        paciente.save()

        messages.success(request, "Paciente actualizado correctamente.")
        return redirect("entidades_app:listado_pacientes")

    return render(request, "entidades/paciente/editar_paciente.html", {
        "paciente": paciente,
    })

@login_required
def eliminar_paciente(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)

    if request.method == "POST":
        try:
            paciente.delete()
            messages.success(request, "Paciente eliminado correctamente.")
            return redirect("entidades_app:listado_pacientes")
        except Exception:
            messages.error(request, "No se puede eliminar el paciente porque tiene registros relacionados.")
            return redirect("entidades_app:listado_pacientes")

   


# ============================================================
# MÉDICOS
# ============================================================
@login_required
def listado_medicos(request):
    buscar = request.GET.get("buscar", "").strip()

    medicos = Medico.objects.select_related("servicio").all().order_by("apellido", "nombre")

    if buscar:
        medicos = medicos.filter(
            Q(nombre__icontains=buscar) |
            Q(apellido__icontains=buscar) |
            Q(numero_documento__icontains=buscar) |
            Q(matricula__icontains=buscar) |
            Q(servicio__nombre__icontains=buscar)
        )

    page_obj = paginar(request, medicos)

    return render(request, "entidades/medico/listado_medicos.html", {
        "page_obj": page_obj,
        "buscar": buscar,
    })

@login_required
def agregar_medico(request):
    servicios = Servicio.objects.all().order_by("nombre")

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        apellido = request.POST.get("apellido", "").strip()
        numero_documento = request.POST.get("numero_documento", "").strip()
        matricula = request.POST.get("matricula", "").strip()
        servicio_id = request.POST.get("servicio") or None

        if not nombre or not apellido or not matricula:
            messages.error(request, "Nombre, apellido y matrícula son obligatorios.")
            return redirect("entidades_app:agregar_medico")

        servicio = Servicio.objects.filter(pk=servicio_id).first() if servicio_id else None

        medico = Medico(
            nombre=nombre,
            apellido=apellido,
            numero_documento=numero_documento or None,
            matricula=matricula,
            servicio=servicio,
        ) 
        medico.save()

        messages.success(request, "Médico agregado correctamente.")
        return redirect("entidades_app:listado_medicos")

    return render(request, "entidades/medico/agregar_medico.html", {
        "servicios": servicios,
    })

@login_required
def editar_medico(request, pk):
    medico = get_object_or_404(Medico, pk=pk)
    servicios = Servicio.objects.all().order_by("nombre")

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        apellido = request.POST.get("apellido", "").strip()
        numero_documento = request.POST.get("numero_documento", "").strip()
        matricula = request.POST.get("matricula", "").strip()
        servicio_id = request.POST.get("servicio") or None

        if not nombre or not apellido or not matricula:
            messages.error(request, "Nombre, apellido y matrícula son obligatorios.")
            return redirect("entidades_app:editar_medico", pk=medico.pk)

        servicio = Servicio.objects.filter(pk=servicio_id).first() if servicio_id else None

        medico.nombre = nombre
        medico.apellido = apellido
        medico.numero_documento = numero_documento or None
        medico.matricula = matricula
        medico.servicio = servicio
 
        medico.save()

        messages.success(request, "Médico actualizado correctamente.")
        return redirect("entidades_app:listado_medicos")

    return render(request, "entidades/medico/editar_medico.html", {
        "medico": medico,
        "servicios": servicios,
    })

@login_required
def eliminar_medico(request, pk):
    medico = get_object_or_404(Medico, pk=pk)

    if request.method == "POST":
        try:
            medico.delete()
            messages.success(request, "Médico eliminado correctamente.")
            return redirect("entidades_app:listado_medicos")
        except Exception:
            messages.error(request, "No se puede eliminar el médico porque tiene registros relacionados.")
            return redirect("entidades_app:listado_medicos")

    

# ============================================================
# OBRAS SOCIALES
# ============================================================
@login_required
def listado_obras_sociales(request):
    buscar = request.GET.get("buscar", "").strip()

    obras_sociales = ObraSocial.objects.all().order_by("nombre")

    if buscar:
        obras_sociales = obras_sociales.filter(
            Q(nombre__icontains=buscar) |
            Q(sigla__icontains=buscar) |
            Q(descripcion__icontains=buscar)
        )

    page_obj = paginar(request, obras_sociales)

    return render(request, "entidades/obrasocial/listado_obras_sociales.html", {
        "page_obj": page_obj,
        "buscar": buscar,
    })

@login_required
def agregar_obra_social(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        sigla = request.POST.get("sigla", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()

        if not nombre:
            messages.error(request, "El nombre de la obra social es obligatorio.")
            return redirect("entidades_app:agregar_obra_social")

        try:
            obra_social = ObraSocial(
                nombre=nombre,
                sigla=sigla or None,
                descripcion=descripcion or None,
            ) 
            obra_social.save()

            messages.success(request, "Obra social agregada correctamente.")
            return redirect("entidades_app:listado_obras_sociales")

        except IntegrityError:
            messages.error(request, "Ya existe una obra social con ese nombre.")
            return redirect("entidades_app:agregar_obra_social")

    return render(request, "entidades/obrasocial/agregar_obra_social.html")

@login_required
def editar_obra_social(request, pk):
    obra_social = get_object_or_404(ObraSocial, pk=pk)

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        sigla = request.POST.get("sigla", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()

        if not nombre:
            messages.error(request, "El nombre de la obra social es obligatorio.")
            return redirect("entidades_app:editar_obra_social", pk=obra_social.pk)

        try:
            obra_social.nombre = nombre
            obra_social.sigla = sigla or None
            obra_social.descripcion = descripcion or None 
            obra_social.save()

            messages.success(request, "Obra social actualizada correctamente.")
            return redirect("entidades_app:listado_obras_sociales")

        except IntegrityError:
            messages.error(request, "Ya existe otra obra social con ese nombre.")
            return redirect("entidades_app:editar_obra_social", pk=obra_social.pk)

    return render(request, "entidades/obrasocial/editar_obra_social.html", {
        "obra_social": obra_social,
    })

@login_required
def eliminar_obra_social(request, pk):
    obra_social = get_object_or_404(ObraSocial, pk=pk)

    if request.method == "POST":
        try:
            obra_social.delete()
            messages.success(request, "Obra social eliminada correctamente.")
            return redirect("entidades_app:listado_obras_sociales")
        except Exception:
            messages.error(request, "No se puede eliminar la obra social porque tiene registros relacionados.")
            return redirect("entidades_app:listado_obras_sociales")


# ============================================================
# PRESTACIONES
# ============================================================
@login_required
def listado_prestaciones(request):
    buscar = request.GET.get("buscar", "").strip()

    prestaciones = Prestacion.objects.all().order_by("codigo", "nombre")

    if buscar:
        prestaciones = prestaciones.filter(
            Q(codigo__icontains=buscar) |
            Q(nombre__icontains=buscar) |
            Q(descripcion__icontains=buscar)
        )

    page_obj = paginar(request, prestaciones)

    return render(request, "entidades/prestacion/listado_prestaciones.html", {
        "page_obj": page_obj,
        "buscar": buscar,
    })

@login_required
def agregar_prestacion(request):
    if request.method == "POST":
        codigo = request.POST.get("codigo", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()

        if not codigo or not nombre:
            messages.error(request, "Código y nombre son obligatorios.")
            return redirect("entidades_app:agregar_prestacion")

        try:
            prestacion = Prestacion(
                codigo=codigo,
                nombre=nombre,
                descripcion=descripcion or None,
            ) 
            prestacion.save()

            messages.success(request, "Prestación agregada correctamente.")
            return redirect("entidades_app:listado_prestaciones")

        except IntegrityError:
            messages.error(request, "Ya existe una prestación con ese código.")
            return redirect("entidades_app:agregar_prestacion")

    return render(request, "entidades/prestacion/agregar_prestacion.html")

@login_required
def editar_prestacion(request, pk):
    prestacion = get_object_or_404(Prestacion, pk=pk)

    if request.method == "POST":
        codigo = request.POST.get("codigo", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()

        if not codigo or not nombre:
            messages.error(request, "Código y nombre son obligatorios.")
            return redirect("entidades_app:editar_prestacion", pk=prestacion.pk)

        try:
            prestacion.codigo = codigo
            prestacion.nombre = nombre
            prestacion.descripcion = descripcion or None 
            prestacion.save()

            messages.success(request, "Prestación actualizada correctamente.")
            return redirect("entidades_app:listado_prestaciones")

        except IntegrityError:
            messages.error(request, "Ya existe otra prestación con ese código.")
            return redirect("entidades_app:editar_prestacion", pk=prestacion.pk)

    return render(request, "entidades/prestacion/editar_prestacion.html", {
        "prestacion": prestacion,
    })

@login_required
def eliminar_prestacion(request, pk):
    prestacion = get_object_or_404(Prestacion, pk=pk)

    if request.method == "POST":
        try:
            prestacion.delete()
            messages.success(request, "Prestación eliminada correctamente.")
            return redirect("entidades_app:listado_prestaciones")
        except Exception:
            messages.error(request, "No se puede eliminar la prestación porque tiene registros relacionados.")
            return redirect("entidades_app:listado_prestaciones")
 


# ============================================================
# PLANES
# ============================================================
@login_required
def listado_planes(request):
    buscar = request.GET.get("buscar", "").strip()

    planes = Plan.objects.select_related("obra_social").all().order_by(
        "obra_social__nombre",
        "nombre"
    )

    if buscar:
        planes = planes.filter(
            Q(nombre__icontains=buscar) |
            Q(obra_social__nombre__icontains=buscar) |
            Q(obra_social__sigla__icontains=buscar)
        )

    page_obj = paginar(request, planes)

    return render(request, "entidades/plan/listado_planes.html", {
        "page_obj": page_obj,
        "buscar": buscar,
    })

@login_required
def agregar_plan(request):
    obras_sociales = ObraSocial.objects.all().order_by("nombre")

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        obra_social_id = request.POST.get("obra_social")

        if not nombre:
            messages.error(request, "El nombre del plan es obligatorio.")
            return redirect("entidades_app:agregar_plan")

        if not obra_social_id:
            messages.error(request, "Debe seleccionar una obra social.")
            return redirect("entidades_app:agregar_plan")

        obra_social = get_object_or_404(ObraSocial, pk=obra_social_id)

        plan = Plan(
            nombre=nombre,
            obra_social=obra_social
        )
        plan.save()

        messages.success(request, "Plan agregado correctamente.")
        return redirect("entidades_app:listado_planes")

    return render(request, "entidades/plan/agregar_plan.html", {
        "obras_sociales": obras_sociales,
    })

@login_required
def editar_plan(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    obras_sociales = ObraSocial.objects.all().order_by("nombre")

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        obra_social_id = request.POST.get("obra_social")

        if not nombre:
            messages.error(request, "El nombre del plan es obligatorio.")
            return redirect("entidades_app:editar_plan", pk=plan.pk)

        if not obra_social_id:
            messages.error(request, "Debe seleccionar una obra social.")
            return redirect("entidades_app:editar_plan", pk=plan.pk)

        obra_social = get_object_or_404(ObraSocial, pk=obra_social_id)

        plan.nombre = nombre
        plan.obra_social = obra_social
        plan.save()

        messages.success(request, "Plan actualizado correctamente.")
        return redirect("entidades_app:listado_planes")

    return render(request, "entidades/plan/editar_plan.html", {
        "plan": plan,
        "obras_sociales": obras_sociales,
    })

@login_required
def eliminar_plan(request, pk):
    plan = get_object_or_404(Plan, pk=pk)

    if request.method == "POST":
        try:
            plan.delete()
            messages.success(request, "Plan eliminado correctamente.")
            return redirect("entidades_app:listado_planes")
        except Exception:
            messages.error(request, "No se puede eliminar el plan porque tiene registros relacionados.")
            return redirect("entidades_app:listado_planes")
