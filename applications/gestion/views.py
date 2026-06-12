from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone


# Create your vi 
def home_view(request):
    return render(request,'gestion/orden_list.html')


from django.shortcuts import render
from django.db.models import Count, Q
from .models import Preingreso


def lista_preingresos(request):
    query = request.GET.get("q", "")
    estado = request.GET.get("estado", "")

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
        .order_by("-created_at")
    )

    if query:
        preingresos = preingresos.filter(
            Q(paciente__nombre__icontains=query) |
            Q(paciente__apellido__icontains=query) |
            Q(paciente__dni__icontains=query) |
            Q(obra_social__nombre__icontains=query)
        )

    if estado:
        preingresos = preingresos.filter(estado=estado)
    
    preingresos= preingresos.exclude(estado__in=['ingresado','cerrado'])

    context = {
        "preingresos": preingresos,
        "query": query,
        "estado": estado,
        "estados": Preingreso.ESTADOS,
    }

    return render(request, "gestion/preingreso/lista_preingresos.html", context)



from .models import  *

from applications.entidades.models import * 
 
from .models import Preingreso

 
from .models import Preingreso


def agregar_preingreso(request):
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

        if not paciente_id:
            messages.error(request, "Debe seleccionar un paciente.")
            return redirect("gestion_app:agregar_preingreso")

        if not obra_social_id:
            messages.error(request, "Debe seleccionar una obra social.")
            return redirect("gestion_app:agregar_preingreso")

        if not fecha_probable_ingreso:
            messages.error(request, "Debe indicar la fecha probable de ingreso.")
            return redirect("gestion_app:agregar_preingreso")

        paciente = Paciente.objects.filter(id=paciente_id).first()
        obra_social = ObraSocial.objects.filter(id=obra_social_id).first()

        if not paciente:
            messages.error(request, "El paciente seleccionado no existe.")
            return redirect("gestion_app:agregar_preingreso")

        if not obra_social:
            messages.error(request, "La obra social seleccionada no existe.")
            return redirect("gestion_app:agregar_preingreso")

        plan = Plan.objects.filter(id=plan_id).first() if plan_id else None
        medico = Medico.objects.filter(id=medico_id).first() if medico_id else None
        servicio = Servicio.objects.filter(id=servicio_id).first() if servicio_id else None

        if plan and plan.obra_social_id != obra_social.id:
            messages.error(request, "El plan seleccionado no corresponde a la obra social indicada.")
            return redirect("gestion_app:agregar_preingreso")

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
        )

        messages.success(request, f"El preingreso #{preingreso.id} fue creado correctamente.")
        return redirect("gestion_app:lista_preingresos")

    return render(request, "gestion/preingreso/agregar_preingreso.html", {
        "obras_sociales": obras_sociales,
        "planes": planes,
        "medicos": medicos,
        "servicios": servicios,
    })



from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q
from django.core.paginator import Paginator
from django.db import IntegrityError
 


@require_GET
def buscar_pacientes_ajax(request):
    q = request.GET.get("q", "").strip()
    page = request.GET.get("page", 1)

    if len(q) < 2:
        return JsonResponse({
            "results": [],
            "has_next": False,
        })

    pacientes = Paciente.objects.filter(
        Q(dni__icontains=q) |
        Q(apellido__icontains=q) |
        Q(nombre__icontains=q)
    ).order_by("apellido", "nombre")

    paginator = Paginator(pacientes, 15)
    page_obj = paginator.get_page(page)

    results = []

    for paciente in page_obj.object_list:
        results.append({
            "id": paciente.id,
            "apellido": paciente.apellido or "",
            "nombre": paciente.nombre or "",
            "dni": paciente.dni or "",
            "fecha_nacimiento": paciente.fecha_nacimiento.strftime("%d/%m/%Y") if paciente.fecha_nacimiento else "",
            "telefono": paciente.telefono or "",
        })

    return JsonResponse({
        "results": results,
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

        return JsonResponse({
            "ok": True,
            "paciente": {
                "id": paciente.id,
                "apellido": paciente.apellido or "",
                "nombre": paciente.nombre or "",
                "dni": paciente.dni or "",
                "fecha_nacimiento": paciente.fecha_nacimiento.strftime("%d/%m/%Y") if paciente.fecha_nacimiento else "",
                "telefono": paciente.telefono or "",
            }
        })

    except IntegrityError:
        return JsonResponse({"ok": False, "error": "No se pudo crear el paciente. Verifique los datos."}, status=400)
    









def detalle_preingreso(request, preingreso_id):
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

    ordenes = OrdenAutorizacion.objects.filter(preingreso=preingreso).order_by("-created_at", "-id")

    return render(request, "gestion/preingreso/detalle_preingreso.html", {
        "preingreso": preingreso,
        "ordenes": ordenes,
    })


def editar_preingreso(request, preingreso_id):
    preingreso = get_object_or_404(Preingreso, id=preingreso_id)

    obras_sociales = ObraSocial.objects.all().order_by("nombre")
    planes = Plan.objects.all().order_by("nombre")
    medicos = Medico.objects.all().order_by("apellido", "nombre")
    servicios = Servicio.objects.all().order_by("nombre")

    if request.method == "POST":
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




from django.http import JsonResponse
import json


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

    prestaciones_page = prestaciones[start:end]

    results = []

    for prestacion in prestaciones_page:
        results.append({
            "id": prestacion.id,
            "codigo": prestacion.codigo or "",
            "nombre": prestacion.nombre or "",
            "descripcion": prestacion.descripcion or "" 
        })

    return JsonResponse({
        "results": results,
        "has_next": end < total,
    })

def buscar_prestacion_por_codigo_ajax(request):
    codigo = request.GET.get("codigo", "").strip()

    prestacion = Prestacion.objects.filter(codigo__iexact=codigo).first()
    print(codigo)
    print(prestacion)
    if not prestacion:
        return JsonResponse({"found": False})

    return JsonResponse({
        "found": True,
        "id": prestacion.id,
        "codigo": prestacion.codigo,
        "nombre": prestacion.nombre,
    })



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

    return render(
        request,
        "gestion/orden/detalle_orden.html",
        {
            "orden": orden,
            "detalles": detalles,
        }
    )




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
        tipo = request.POST.get("tipo")
        fecha = request.POST.get("fecha") or None
        medico_id = request.POST.get("medico") or None
        numero_cupon = request.POST.get("numero_cupon", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()
        detalles_json = request.POST.get("detalles_json", "[]")
        print("El medico id es:",medico_id)
        try:
            detalles = json.loads(detalles_json)
        except json.JSONDecodeError:
            detalles = []

        if not tipo:
            messages.error(request, "Debe seleccionar el tipo de orden.")
            return redirect("gestion_app:agregar_orden_preingreso", preingreso_id=preingreso.id)

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
        print("El medico es:",medico)
        try:
            with transaction.atomic():
                orden = OrdenAutorizacion.objects.create(
                    preingreso=preingreso,
                    tipo=tipo,
                    fecha=fecha,
                    medico=medico,
                    numero_cupon=numero_cupon or None,
                    observaciones=observaciones or None,
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
            return redirect("gestion_app:lista_ordenes_preingreso", preingreso_id=preingreso.id)

        except Exception as e:
            messages.error(request, f"Ocurrió un error al guardar la orden: {e}")
            print("El error es:", e)
            return redirect("gestion_app:agregar_orden_preingreso", preingreso_id=preingreso.id)

    return render(request, "gestion/orden/agregar_orden_preingreso.html", {
        "preingreso": preingreso,
        "medicos": medicos,
        "tipos_orden": OrdenAutorizacion.TIPOS,
        "honorarios_gastos": DetalleOrden.HONORARIOS_GASTOS,
        "tipos_honorario": DetalleOrden.TIPOS_HONORARIO,
    })


def lista_ingresos(request):
    query = request.GET.get("q", "").strip()  
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
            total_ordenes=Count("ordenes", distinct=True),
        )
        .order_by("-fecha_ingreso",  "-id")
    )

    if query:
        ingresos = ingresos.filter(
            Q(numero__icontains=query) |
            Q(paciente__apellido__icontains=query) |
            Q(paciente__nombre__icontains=query) |
            Q(paciente__dni__icontains=query) |
            Q(obra_social__nombre__icontains=query)
        )
    print(ingresos)

    ingresos = ingresos.filter(estado__in=['ingresado', 'cerrado'])
    print(ingresos)
    return render(request, "gestion/ingreso/lista_ingresos.html", {
        "ingresos": ingresos,
        "query": query, 
        "estados": Preingreso.ESTADOS,
    })

 
#####################----INGRESOS----##################

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

        numero = request.POST.get("numero", "").strip()
        fecha_ingreso = request.POST.get("fecha_ingreso") or None
        numero_afiliado = request.POST.get("numero_afiliado", "").strip()
        diagnostico = request.POST.get("diagnostico", "").strip()
        origen_paciente = request.POST.get("origen_paciente") or "domicilio"
        prioridad = request.POST.get("prioridad") or "normal"

        contacto_nombre = request.POST.get("contacto_nombre", "").strip()
        contacto_dni = request.POST.get("contacto_dni", "").strip()
        contacto_parentesco = request.POST.get("contacto_parentesco", "").strip()
        contacto_telefono = request.POST.get("contacto_telefono", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()

        if not paciente_id:
            messages.error(request, "Debe seleccionar un paciente.")
            return redirect("gestion_app:agregar_ingreso")

        if not obra_social_id:
            messages.error(request, "Debe seleccionar una obra social.")
            return redirect("gestion_app:agregar_ingreso")

        if not numero:
            messages.error(request, "Debe indicar el número de episodio.")
            return redirect("gestion_app:agregar_ingreso")

        if Preingreso.objects.filter(numero=numero).exists():
            messages.error(request, "Ya existe un ingreso con ese número de episodio.")
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

        ingreso = Preingreso.objects.create(
            paciente=paciente,
            obra_social=obra_social,
            plan=plan,
            numero_afiliado=numero_afiliado or None,
            medico=medico,
            servicio=servicio,
            numero=numero,
            fecha_ingreso=fecha_ingreso,
            fecha_probable_ingreso=None,
            diagnostico=diagnostico or None,
            origen_paciente=origen_paciente,
            prioridad=prioridad,
            contacto_nombre=contacto_nombre or None,
            contacto_dni=contacto_dni or None,
            contacto_parentesco=contacto_parentesco or None,
            contacto_telefono=contacto_telefono or None,
            observaciones=observaciones or None,
            estado="ingresado",
        )
        print(ingreso)
        messages.success(request, f"El ingreso #{ingreso.numero} fue creado correctamente.")
        return redirect("gestion_app:lista_ingresos")

    return render(request, "gestion/ingreso/agregar_ingreso.html", {
        "obras_sociales": obras_sociales,
        "planes": planes,
        "medicos": medicos,
        "servicios": servicios, 
    })








def buscar_preingresos_ajax(request):
    q = request.GET.get("q", "").strip()
    page = request.GET.get("page", 1)

    preingresos = Preingreso.objects.select_related(
        "paciente",
        "obra_social",
        "plan",
        "medico",
        "servicio",
    ).exclude(
        estado__in=["ingresado", "cerrado"]
    ).order_by("-id")

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


def agregar_ingreso_programado(request):
    obras_sociales = ObraSocial.objects.all().order_by("nombre")
    medicos = Medico.objects.all().order_by("apellido", "nombre")
    servicios = Servicio.objects.all().order_by("nombre")
    planes = Plan.objects.all().order_by("obra_social__nombre", "nombre")

    if request.method == "POST":
        preingreso_id = request.POST.get("preingreso_id")

        preingreso = get_object_or_404(
            Preingreso,
            id=preingreso_id
        )

        if preingreso.estado in ["ingresado", "cerrado"]:
            messages.error(request, "Este preingreso ya no está disponible para ingresar.")
            return redirect("gestion_app:agregar_ingreso_programado")

        preingreso.obra_social_id = request.POST.get("obra_social")
        preingreso.plan_id = request.POST.get("plan") or None
        preingreso.numero_afiliado = request.POST.get("numero_afiliado", "").strip()

        preingreso.numero = request.POST.get("numero", "").strip()
        preingreso.fecha_ingreso = request.POST.get("fecha_ingreso") or None

        preingreso.servicio_id = request.POST.get("servicio") or None
        preingreso.medico_id = request.POST.get("medico") or None

        preingreso.origen_paciente = request.POST.get("origen_paciente") or "domicilio"
        preingreso.prioridad = request.POST.get("prioridad") or "programado"
        preingreso.diagnostico = request.POST.get("diagnostico", "").strip()

        preingreso.contacto_nombre = request.POST.get("contacto_nombre", "").strip()
        preingreso.contacto_dni = request.POST.get("contacto_dni", "").strip()
        preingreso.contacto_parentesco = request.POST.get("contacto_parentesco", "").strip()
        preingreso.contacto_telefono = request.POST.get("contacto_telefono", "").strip()

        preingreso.observaciones = request.POST.get("observaciones", "").strip()

        preingreso.estado = "ingresado"
        preingreso.save()

        messages.success(request, "Ingreso programado registrado correctamente.")
        return redirect("gestion_app:lista_ingresos")

    return render(request, "gestion/ingreso/agregar_ingreso_programado.html", {
        "obras_sociales": obras_sociales,
        "planes": planes,
        "medicos": medicos,
        "servicios": servicios, 
    })




 
def imprimir_orden(request, orden_id):
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
    print("Esta es la orden:",orden.detalles.all())
    return render(request, "gestion/orden/imprimir_orden.html", {
        "orden": orden,
        "preingreso": orden.preingreso,
        "detalles": orden.detalles.all().order_by("id"),
        "fecha_impresion": timezone.now(),
    })