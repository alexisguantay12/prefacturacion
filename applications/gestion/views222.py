from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction 
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache

#ANCHOR: Seccion Principal


def home_view(request):
    return render(request,'gestion/orden_list.html')


from django.shortcuts import render
from django.db.models import Count, Q
from .models import Preingreso
from django.contrib.auth.decorators import login_required


@login_required
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
from django.db import transaction
from applications.entidades.models import * 
 
from .models import Preingreso

 
from .models import Preingreso

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
    medicos = Medico.objects.all().order_by("apellido", "nombre")
    ordenes = OrdenAutorizacion.objects.filter(preingreso=preingreso).order_by("-created_at", "-id")

    return render(request, "gestion/preingreso/detalle_preingreso.html", {
        "preingreso": preingreso,
        "ordenes": ordenes,
        "medicos":medicos
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

    return render(
        request,
        "gestion/orden/detalle_orden_preingreso.html",
        {
            "orden": orden,
            "detalles": detalles,
        }
    )

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

from datetime import date


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
        observaciones = request.POST.get("observaciones", "").strip()
        detalles_json = request.POST.get("detalles_json", "[]")
        print("El medico id es:",medico_id)
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
        print("El medico es:",medico)
        try:
            with transaction.atomic():
                orden = OrdenAutorizacion.objects.create(
                    preingreso=preingreso, 
                    fecha=fecha,
                    medico=medico, 
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
            return redirect("gestion_app:detalle_preingreso", preingreso_id=preingreso.id)

        except Exception as e:
            messages.error(request, f"Ocurrió un error al guardar la orden: {e}")
            print("El error es:", e)
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

        fecha_ingreso = request.POST.get("fecha_ingreso") or None
        numero_afiliado = request.POST.get("numero_afiliado", "").strip()
        diagnostico = request.POST.get("diagnostico", "").strip() 

        contacto_nombre = request.POST.get("contacto_nombre", "").strip()
        contacto_dni = request.POST.get("contacto_dni", "").strip()
        contacto_parentesco = request.POST.get("contacto_parentesco", "").strip()
        contacto_telefono = request.POST.get("contacto_telefono", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()
        episodio = request.POST.get("episodio").strip()
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
        "medicos":medicos
    })


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
                ingreso.save()

        except Exception:
            messages.error(request, "No se pudo actualizar el ingreso. Intente nuevamente.")
            return redirect("gestion_app:editar_ingreso", ingreso_id=ingreso.id)

        messages.success(request, f"El ingreso #{ingreso.numero} fue actualizado correctamente.")
        return redirect(
            "gestion_app:detalle_ingreso",
            preingreso_id=ingreso.id
        )

    return render(request, "gestion/ingreso/editar_ingreso.html", {
        "ingreso": ingreso,
        "obras_sociales": obras_sociales,
        "planes": planes,
        "medicos": medicos,
        "servicios": servicios,
    })




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
        tipo = request.POST.get("tipo")
        fecha = request.POST.get("fecha") or None
        medico_id = request.POST.get("medico") or None 
        observaciones = request.POST.get("observaciones", "").strip()
        detalles_json = request.POST.get("detalles_json", "[]")
        print("El medico id es:",medico_id)
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
        print("El medico es:",medico)
        try:
            with transaction.atomic():
                orden = OrdenAutorizacion.objects.create(
                    preingreso=preingreso, 
                    fecha=fecha,
                    medico=medico, 
                    observaciones=observaciones or None,
                    medico_tenencia=medico,
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
            print("El error es:", e)
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

                episodio = request.POST.get("episodio")

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
                preingreso.episodio=episodio

                preingreso.estado = "ingresado"
                preingreso.save()

        except Exception:
            messages.error(request, "No se pudo registrar el ingreso programado. Intente nuevamente.")
            return redirect("gestion_app:agregar_ingreso_programado")

        messages.success(
            request,
            f"Ingreso programado registrado correctamente. Episodio #{preingreso.numero}"
        )
        return redirect("gestion_app:lista_ingresos")

    return render(request, "gestion/ingreso/agregar_ingreso_programado.html", {
        "obras_sociales": obras_sociales,
        "planes": planes,
        "medicos": medicos,
        "servicios": servicios,
    })


 
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
    print("Esta es la orden:",orden.detalles.all())
    return render(request, "gestion/orden/imprimir_orden.html", {
        "orden": orden,
        "preingreso": orden.preingreso,
        "detalles": orden.detalles.all().order_by("id"),
        "fecha_impresion": timezone.now(),
        "duplicado":imprimir_duplicado
    })

 
from django.utils import timezone
def redirigir_segun_origen(request, orden):
    es_preingreso = request.POST.get("preingreso") == "true"

    if es_preingreso:
        return redirect("gestion_app:detalle_preingreso", preingreso_id=orden.preingreso_id)

    return redirect("gestion_app:detalle_ingreso", preingreso_id=orden.preingreso_id)


@require_POST
def autorizar_orden(request, orden_id):
    orden = get_object_or_404(OrdenAutorizacion, id=orden_id)

    if orden.estado == "anulada":
        messages.error(request, "No se puede autorizar una orden anulada.")
        return redirigir_segun_origen(request, orden)

    orden.autorizada = True
    orden.estado = "autorizada"
    orden.save()

    orden.detalles.update(autorizada=True)

    messages.success(request, "Orden autorizada correctamente.")
    return redirigir_segun_origen(request, orden)


@require_POST
def anular_orden(request, orden_id):
    orden = get_object_or_404(OrdenAutorizacion, id=orden_id)

    orden.estado = "anulada"
    orden.autorizada = False
    orden.fecha_anulacion = timezone.now()
    orden.motivo_anulacion = request.POST.get("motivo_anulacion", "").strip()
    orden.save()

    orden.detalles.update(autorizada=False)

    messages.success(request, "Orden anulada correctamente.")
    return redirigir_segun_origen(request, orden)


@require_POST
def cambiar_tenencia_orden(request, orden_id):
    orden = get_object_or_404(OrdenAutorizacion, id=orden_id)

    if orden.estado == "anulada":
        messages.error(request, "No se puede cambiar la tenencia de una orden anulada.")
        return redirigir_segun_origen(request, orden)

    if orden.estado != "autorizada" and not orden.autorizada:
        messages.error(request, "Solo se puede cambiar la tenencia de una orden autorizada.")
        return redirigir_segun_origen(request, orden)

    medico_id = request.POST.get("medico_id")
    medico = get_object_or_404(Medico, id=medico_id)

    orden.medico_tenencia = medico
    orden.save()

    messages.success(request, "Tenencia actualizada correctamente.")
    return redirigir_segun_origen(request, orden)