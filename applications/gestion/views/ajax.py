from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from datetime import datetime
from django.db import transaction
from django.shortcuts import get_object_or_404
from applications.entidades.models import *
from ..models import *
from django.utils import timezone 
# =============================================================================
# AJAX PACIENTES
# =============================================================================


def buscar_pacientes_ajax(request):
    apellido = request.GET.get("apellido", "").strip()
    nombre = request.GET.get("nombre", "").strip()
    dni = request.GET.get("dni", "").strip()
    page_number = request.GET.get("page", 1)

    pacientes = Paciente.objects.all()

    if apellido:
        pacientes = pacientes.filter(
            apellido__icontains=apellido
        )

    if nombre:
        pacientes = pacientes.filter(
            nombre__icontains=nombre
        )

    if dni:
        pacientes = pacientes.filter(
            dni__icontains=dni
        )

    pacientes = pacientes.order_by("apellido", "nombre")

    paginator = Paginator(pacientes, 15)
    page_obj = paginator.get_page(page_number)

    resultados = [
        {
            "id": paciente.id,
            "apellido": paciente.apellido,
            "nombre": paciente.nombre,
            "dni": paciente.dni,
            "fecha_nacimiento": (
                paciente.fecha_nacimiento.strftime("%d/%m/%Y")
                if paciente.fecha_nacimiento
                else ""
            ),
            "telefono": paciente.telefono or "",
        }
        for paciente in page_obj
    ]

    return JsonResponse({
        "results": resultados,
        "has_next": page_obj.has_next(),
    })

@require_POST
def crear_paciente_ajax(request):
    apellido = request.POST.get("apellido", "").strip()
    nombre = request.POST.get("nombre", "").strip()
    dni = request.POST.get("dni", "").strip()
    fecha_nacimiento = request.POST.get("fecha_nacimiento") or None
    genero = request.POST.get("genero") or None
    telefono = request.POST.get("telefono", "").strip()
    direccion = request.POST.get("direccion", "").strip()
    provincia = request.POST.get("provincia", "").strip()
    nacionalidad = request.POST.get("nacionalidad", "").strip()

    if not apellido:
        return JsonResponse({"ok": False, "error": "El apellido es obligatorio."}, status=400)

    if not nombre:
        return JsonResponse({"ok": False, "error": "El nombre es obligatorio."}, status=400)

    if not dni:
        return JsonResponse({"ok": False, "error": "El DNI es obligatorio."}, status=400)

    if Paciente.objects.filter(dni=dni).exists():
        return JsonResponse({"ok": False, "error": "Ya existe un paciente con ese DNI."}, status=400)

    try:
        paciente = Paciente.objects.create(
            apellido=apellido,
            nombre=nombre,
            dni=dni,
            fecha_nacimiento=fecha_nacimiento,
            genero=genero,
            telefono=telefono or None,
            direccion=direccion or None,
            provincia=provincia or None,
            nacionalidad=nacionalidad or None,
        )
        paciente.refresh_from_db()
        return JsonResponse({
            "ok": True,
            "paciente": {
                "id": paciente.id,
                "apellido": paciente.apellido or "",
                "nombre": paciente.nombre or "",
                "dni": paciente.dni or "",
                "fecha_nacimiento": paciente.fecha_nacimiento.strftime("%Y-%m-%d") if paciente.fecha_nacimiento else "",
                "telefono": paciente.telefono or "",
            }
        })

    except IntegrityError:
        return JsonResponse({"ok": False, "error": "No se pudo crear el paciente. Verifique los datos."}, status=400)


# =============================================================================
# AJAX PRESTACIONES
# =============================================================================

def buscar_prestaciones_ajax(request):
    q = request.GET.get("q", "").strip()
    page = int(request.GET.get("page", 1))
    page_size = 15

    prestaciones = Prestacion.objects.all().order_by("codigo", "nombre")

    if q:
        prestaciones = prestaciones.filter(
            Q(codigo__icontains=q) |
            Q(nombre__icontains=q) |
            Q(descripcion__icontains=q)
        )

    total = prestaciones.count()
    start = (page - 1) * page_size
    end = start + page_size

    results = []

    for prestacion in prestaciones[start:end]:
        results.append({
            "id": prestacion.id,
            "codigo": prestacion.codigo or "",
            "nombre": prestacion.nombre or "",
            "descripcion": prestacion.descripcion or "",
        })

    return JsonResponse({
        "results": results,
        "has_next": end < total,
    })


def buscar_prestacion_por_codigo_ajax(request):
    codigo = request.GET.get("codigo", "").strip()

    prestacion = Prestacion.objects.filter(codigo__iexact=codigo).first()

    if not prestacion:
        return JsonResponse({"found": False})

    return JsonResponse({
        "found": True,
        "id": prestacion.id,
        "codigo": prestacion.codigo,
        "nombre": prestacion.nombre,
    })


# =============================================================================
# AJAX PREINGRESOS
# =============================================================================

def buscar_preingresos_ajax(request):
    q = request.GET.get("q", "").strip()
    page = request.GET.get("page", 1)

    preingresos = (
        Preingreso.objects
        .select_related(
            "paciente",
            "obra_social",
            "plan",
            "medico",
            "servicio",
        )
        .exclude(estado__in=["ingresado", "cerrado"])
        .order_by("-id")
    )

    if q:
        preingresos = preingresos.filter(
            Q(numero__icontains=q) |
            Q(paciente__apellido__icontains=q) |
            Q(paciente__nombre__icontains=q) |
            Q(paciente__dni__icontains=q)
        )

    paginator = Paginator(preingresos, 15)
    page_obj = paginator.get_page(page)

    results = []

    for p in page_obj:
        paciente = p.paciente

        results.append({
            "id": p.id,
            "numero": p.numero or "",
            "estado": p.get_estado_display(),
            "estado_raw": p.estado,
            "paciente_id": paciente.id,
            "paciente_nombre": paciente.nombre or "",
            "paciente_apellido": paciente.apellido or "",
            "paciente_dni": paciente.dni or "",
            "paciente_fecha_nacimiento": paciente.fecha_nacimiento.strftime("%Y-%m-%d") if paciente.fecha_nacimiento else "",
            "paciente_telefono": getattr(paciente, "telefono", "") or "",
            "obra_social_id": p.obra_social_id or "",
            "plan_id": p.plan_id or "",
            "numero_afiliado": p.numero_afiliado or "",
            "medico_id": p.medico_id or "",
            "servicio_id": p.servicio_id or "",
            "fecha_probable_ingreso": p.fecha_probable_ingreso.strftime("%Y-%m-%d") if p.fecha_probable_ingreso else "",
            "diagnostico": p.diagnostico or "",
            "origen_paciente": p.origen_paciente or "domicilio",
            "prioridad": p.prioridad or "programado",
            "contacto_nombre": p.contacto_nombre or "",
            "contacto_dni": p.contacto_dni or "",
            "contacto_telefono": p.contacto_telefono or "",
            "contacto_parentesco": p.contacto_parentesco or "",
            "observaciones": p.observaciones or "",
        })

    return JsonResponse({
        "results": results,
        "has_next": page_obj.has_next(),
    })

 
@require_POST
def cerrar_episodio_ajax(request, preingreso_id):
    fecha_egreso_str = request.POST.get("fecha_egreso", "").strip()

    if not fecha_egreso_str:
        return JsonResponse({
            "ok": False,
            "mensaje": "Debe indicar una fecha de egreso."
        }, status=400)

    try:
        fecha_egreso = datetime.strptime(
            fecha_egreso_str,
            "%Y-%m-%d"
        ).date()
    except ValueError:
        return JsonResponse({
            "ok": False,
            "mensaje": "La fecha de egreso no tiene un formato válido."
        }, status=400)

    try:
        with transaction.atomic():
            preingreso = (
                Preingreso.objects
                .select_for_update()
                .get(id=preingreso_id)
            )

            if preingreso.estado == "cerrado":
                return JsonResponse({
                    "ok": False,
                    "mensaje": "El episodio ya se encuentra cerrado."
                }, status=400)

            if preingreso.estado not in ["ingresado", "en_gestion"]:
                return JsonResponse({
                    "ok": False,
                    "mensaje": (
                        "El episodio no se puede cerrar porque su estado "
                        "actual no lo permite."
                    )
                }, status=400)

            if (
                preingreso.fecha_ingreso
                and fecha_egreso < preingreso.fecha_ingreso
            ):
                return JsonResponse({
                    "ok": False,
                    "mensaje": (
                        "La fecha de egreso no puede ser anterior "
                        "a la fecha de ingreso."
                    )
                }, status=400)

            preingreso.fecha_egreso = fecha_egreso
            preingreso.estado = "cerrado"
            preingreso.user_egreso=request.user
            preingreso.save(
                update_fields=[
                    "fecha_egreso",
                    "estado",
                    "user_egreso"
                ]
            )
            preingreso.refresh_from_db()

    except Preingreso.DoesNotExist:
        return JsonResponse({
            "ok": False,
            "mensaje": "El ingreso indicado no existe."
        }, status=404)

    return JsonResponse({
        "ok": True,
        "mensaje": "El episodio fue cerrado correctamente.",
        "estado": "cerrado",
        "estado_display": preingreso.get_estado_display(),
        "fecha_egreso": fecha_egreso.strftime("%d/%m/%Y"),
    })