from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connections, transaction, IntegrityError
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET
from django.urls import reverse
from applications.entidades.models import (
    Paciente,
    Medico,
    ObraSocial,
    Plan,
    Servicio,
)

from applications.gestion.models import Preingreso, Numerador

def dictfetchone(cursor):
    """
    Convierte una fila SQL en un diccionario utilizando
    los alias definidos en el SELECT.
    """
    row = cursor.fetchone()

    if row is None:
        return None

    columns = [column[0] for column in cursor.description]

    return dict(zip(columns, row))


def limpiar_texto(valor):
    if valor is None:
        return ""

    return str(valor).strip()


def obtener_diagnostico_innova(datos):
    """
    Si Diagnostico está vacío o solamente contiene '-',
    utiliza MotivoIngreso.
    """
    diagnostico = limpiar_texto(datos.get("diagnostico"))
    motivo_ingreso = limpiar_texto(datos.get("motivo_ingreso"))

    if not diagnostico or diagnostico == "-":
        return motivo_ingreso

    return diagnostico

def normalizar_genero_innova(valor):
    valor = limpiar_texto(valor).upper()

    if valor in ("M", "MASCULINO"):
        return "Masculino"

    if valor in ("F", "FEMENINO"):
        return "Femenino"

    return None

def consultar_episodio_innova(documento):
    """
    Busca el episodio activo más reciente correspondiente al DNI.
    No realiza modificaciones en INNOVA.
    """
    documento = limpiar_texto(documento)

    if not documento:
        return None

    sql = """
        SELECT TOP (1)
            e.Id AS episodio,
            CONVERT(date,e.FechaModificacion) AS fecha_ingreso,
            e.Diagnostico AS diagnostico,
            e.MotivoIngreso AS motivo_ingreso,
            p.Documento_Numero AS dni,
            p.Nombres AS nombre,
            p.Apellido AS apellido,
            p.sexo as genero,
            CONVERT(date,p.FechaNacimiento) AS fecha_nacimiento,
            p.TelefonoCelular AS telefono,
            ex.NumeroDeAfiliado AS numero_afiliado,
            prof.Matricula AS medico_matricula,
            per.Nombres AS medico_nombre,
            per.Apellido AS medico_apellido,
            per.Documento_Numero AS medico_documento,
            CONCAT(par.Nombres,', ',par.Apellido) AS contacto_nombre,
            par.Documento_Numero AS contacto_dni,
            par.TelefonoCelular AS contacto_telefono,
            p2.Nombre AS contacto_parentesco
        FROM hce.Internacion.Episodios AS e
        INNER JOIN Personas AS p ON p.Id=e.IdPersona
        LEFT JOIN Profesionales AS prof
            ON prof.Id=e.IdProfesionalResponsableDeCabecera
        LEFT JOIN Personas AS per
            ON per.Id=prof.IdPersona
        LEFT JOIN Personas AS par
            ON par.Id=e.IdPersonaTutor
        LEFT JOIN Parentescos AS p2
            ON p2.Id=e.IdParentescoTutor
        LEFT JOIN Internacion.Expedientes AS ex
            ON ex.Id=e.IdExpediente
        WHERE p.Documento_Numero=%s
          AND e.IdTipoEpisodio IN (1,2)
          AND e.Estado='A'
        ORDER BY e.Id DESC;
    """
    print("Yo llego aca")
    
    try:
        with connections["innova"].cursor() as cursor:
            cursor.execute(sql, [documento])
            datos = dictfetchone(cursor)

        print("Datos encontrados:", datos)

    except Exception as error:
        print("ERROR AL CONECTAR O CONSULTAR INNOVA")
        print("Tipo:", type(error).__name__)
        print("Detalle:", str(error)) 
        raise

    if not datos:
        return None

    datos["diagnostico_final"] = obtener_diagnostico_innova(datos)

    return datos


@login_required
@require_GET
def buscar_ingreso_erp(request):
    documento = limpiar_texto(request.GET.get("documento"))

    if not documento:
        return JsonResponse(
            {
                "ok": False,
                "error": "Debe ingresar el documento del paciente.",
            },
            status=400,
        )

    try:
        datos = consultar_episodio_innova(documento)

    except Exception:
        return JsonResponse(
            {
                "ok": False,
                "error": "No se pudo consultar el sistema INNOVA.",
            },
            status=500,
        )

    if not datos:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No se encontró un episodio activo para "
                    "el documento indicado."
                ),
            },
            status=404,
        )

    episodio = limpiar_texto(datos.get("episodio"))
    dni = limpiar_texto(datos.get("dni"))

    if Preingreso.objects.filter(episodio=episodio).exists():
        return JsonResponse(
            {
                "ok": False,
                "error": "El episodio encontrado ya fue importado.",
                "redirect_url": reverse(
                    "gestion_app:lista_ingresos"
                ),
            },
            status=409,
        )

    paciente_local = Paciente.objects.filter(dni=dni).first()

    ingreso_abierto = None

    if paciente_local:
        ingreso_abierto = (
            Preingreso.objects
            .filter(
                paciente=paciente_local,
                es_preingreso=False,
                estado="ingresado",
                fecha_egreso__isnull=True,
            )
            .first()
        )

    if ingreso_abierto:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    f"El paciente ya posee el ingreso "
                    f"#{ingreso_abierto.numero} abierto."
                ),
                "redirect_url": reverse(
                    "gestion_app:lista_ingresos"
                ),
            },
            status=409,
        )

    fecha_ingreso = datos.get("fecha_ingreso")
    fecha_nacimiento = datos.get("fecha_nacimiento")

    return JsonResponse({
        "ok": True,
        "datos": {
            "episodio": episodio,
            "fecha_ingreso": (
                fecha_ingreso.isoformat()
                if fecha_ingreso else ""
            ),
            "diagnostico": datos.get("diagnostico_final") or "",

            "dni": dni,
            "nombre": limpiar_texto(datos.get("nombre")),
            "apellido": limpiar_texto(datos.get("apellido")),
            "fecha_nacimiento": (
                fecha_nacimiento.isoformat()
                if fecha_nacimiento else ""
            ),
            "telefono": limpiar_texto(datos.get("telefono")),

            "numero_afiliado": limpiar_texto(
                datos.get("numero_afiliado")
            ),
            "genero": normalizar_genero_innova(
                datos.get("genero")
            ),
            "medico_matricula": limpiar_texto(
                datos.get("medico_matricula")
            ),
            "medico_nombre": limpiar_texto(
                datos.get("medico_nombre")
            ),
            "medico_apellido": limpiar_texto(
                datos.get("medico_apellido")
            ),
            "medico_documento": limpiar_texto(
                datos.get("medico_documento")
            ),

            "contacto_nombre": limpiar_texto(
                datos.get("contacto_nombre")
            ),
            "contacto_dni": limpiar_texto(
                datos.get("contacto_dni")
            ),
            "contacto_telefono": limpiar_texto(
                datos.get("contacto_telefono")
            ),
            "contacto_parentesco": limpiar_texto(
                datos.get("contacto_parentesco")
            ),

            "paciente_existe": bool(paciente_local),
        },
    })




@login_required
def guardar_ingreso_erp(request):
    obras_sociales = ObraSocial.objects.all().order_by("nombre")

    planes = (
        Plan.objects
        .select_related("obra_social")
        .all()
        .order_by("obra_social__nombre", "nombre")
    )

    servicios = Servicio.objects.all().order_by("nombre")

    if request.method == "POST":
        dni = limpiar_texto(request.POST.get("dni"))
        episodio_enviado = limpiar_texto(
            request.POST.get("episodio")
        )

        telefono = limpiar_texto(
            request.POST.get("telefono")
        )

        obra_social_id = request.POST.get("obra_social")
        plan_id = request.POST.get("plan")
        servicio_id = request.POST.get("servicio") or None

        observaciones = limpiar_texto(
            request.POST.get("observaciones")
        )

        if not dni:
            messages.error(
                request,
                "No se recibió el documento del paciente."
            )
            return redirect("gestion_app:guardar_ingreso_erp")

        if not episodio_enviado:
            messages.error(
                request,
                "No se recibió el número de episodio."
            )
            return redirect("gestion_app:guardar_ingreso_erp")

        if not obra_social_id:
            messages.error(
                request,
                "Debe seleccionar una obra social."
            )
            return redirect("gestion_app:guardar_ingreso_erp")

        if not plan_id:
            messages.error(
                request,
                "Debe seleccionar un plan."
            )
            return redirect("gestion_app:guardar_ingreso_erp")

        obra_social = (
            ObraSocial.objects
            .filter(id=obra_social_id)
            .first()
        )

        plan = (
            Plan.objects
            .select_related("obra_social")
            .filter(id=plan_id)
            .first()
        )

        servicio = (
            Servicio.objects
            .filter(id=servicio_id)
            .first()
            if servicio_id else None
        )

        if not obra_social:
            messages.error(
                request,
                "La obra social seleccionada no existe."
            )
            return redirect("gestion_app:guardar_ingreso_erp")

        if not plan:
            messages.error(
                request,
                "El plan seleccionado no existe."
            )
            return redirect("gestion_app:guardar_ingreso_erp")

        if plan.obra_social_id != obra_social.id:
            messages.error(
                request,
                "El plan no corresponde a la obra social indicada."
            )
            return redirect("gestion_app:guardar_ingreso_erp")

        # Se vuelve a consultar INNOVA.
        # No se confía solamente en los campos enviados por el navegador.
        try:
            datos_erp = consultar_episodio_innova(dni)

        except Exception:
            messages.error(
                request,
                "No se pudo validar nuevamente el episodio en INNOVA."
            )
            return redirect("gestion_app:guardar_ingreso_erp")

        if not datos_erp:
            messages.error(
                request,
                "El episodio ya no se encuentra activo en INNOVA."
            )
            return redirect("gestion_app:lista_ingresos")

        episodio_real = limpiar_texto(
            datos_erp.get("episodio")
        )

        if episodio_real != episodio_enviado:
            messages.error(
                request,
                (
                    "El episodio activo cambió desde que se realizó "
                    "la búsqueda. Vuelva a iniciar la carga."
                )
            )
            return redirect("gestion_app:lista_ingresos")

        diagnostico = obtener_diagnostico_innova(datos_erp)

        if not diagnostico:
            messages.error(
                request,
                (
                    "INNOVA no informó diagnóstico ni motivo "
                    "de ingreso."
                )
            )
            return redirect("gestion_app:guardar_ingreso_erp")

        medico_matricula = limpiar_texto(
            datos_erp.get("medico_matricula")
        )

        medico_nombre = limpiar_texto(
            datos_erp.get("medico_nombre")
        )

        medico_apellido = limpiar_texto(
            datos_erp.get("medico_apellido")
        )

        medico_documento = limpiar_texto(
            datos_erp.get("medico_documento")
        )

        try:
            with transaction.atomic():
                # Evitar importar dos veces el mismo episodio.
                if (
                    Preingreso.objects
                    .select_for_update()
                    .filter(episodio=episodio_real)
                    .exists()
                ):
                    messages.error(
                        request,
                        "El episodio ya fue importado anteriormente."
                    )
                    return redirect("gestion_app:lista_ingresos")

                paciente = (
                    Paciente.objects
                    .select_for_update()
                    .filter(dni=dni)
                    .first()
                )

                if paciente:
                    ingreso_abierto = (
                        Preingreso.objects
                        .select_for_update()
                        .filter(
                            paciente=paciente,
                            es_preingreso=False,
                            estado="ingresado",
                            fecha_egreso__isnull=True,
                        )
                        .first()
                    )

                    if ingreso_abierto:
                        messages.error(
                            request,
                            (
                                f"El paciente ya posee el ingreso "
                                f"#{ingreso_abierto.numero} abierto."
                            )
                        )
                        return redirect(
                            "gestion_app:lista_ingresos"
                        )

                    # Los datos corroborados vienen de INNOVA.
                    paciente.nombre = limpiar_texto(
                        datos_erp.get("nombre")
                    )
                    paciente.apellido = limpiar_texto(
                        datos_erp.get("apellido")
                    )
                    paciente.fecha_nacimiento = datos_erp.get(
                        "fecha_nacimiento"
                    )

                    # El teléfono es el único dato editable.
                    paciente.telefono = telefono or None
                    paciente.genero = normalizar_genero_innova(
                        datos_erp.get("genero")
                    )

                    paciente.save(update_fields=[
                        "nombre",
                        "apellido",
                        "fecha_nacimiento",
                        "genero",
                        "telefono",
                    ]) 

                else:
                    paciente = Paciente.objects.create(
                        nombre=limpiar_texto(
                            datos_erp.get("nombre")
                        ),
                        apellido=limpiar_texto(
                            datos_erp.get("apellido")
                        ),
                        dni=dni,
                        fecha_nacimiento=datos_erp.get(
                            "fecha_nacimiento"
                        ),
                        genero=normalizar_genero_innova(
                            datos_erp.get("genero")
                        ),
                        telefono=telefono or None,
                        user_made=request.user,
                    )

                medico = None

                if medico_matricula:
                    medico = (
                        Medico.objects
                        .select_for_update()
                        .filter(
                            matricula__iexact=medico_matricula
                        )
                        .first()
                    )

                    if not medico:
                        medico = Medico.objects.create(
                            nombre=medico_nombre or "Sin nombre",
                            apellido=medico_apellido or "Sin apellido",
                            numero_documento=(
                                medico_documento or None
                            ),
                            matricula=medico_matricula,
                            user_made=request.user,
                        )

                numerador, creado = (
                    Numerador.objects
                    .select_for_update()
                    .get_or_create(
                        nombre="ingreso",
                        defaults={"ultimo": 0},
                    )
                )

                numerador.ultimo += 1
                numerador.save(update_fields=["ultimo"])

                ingreso = Preingreso.objects.create(
                    paciente=paciente,
                    obra_social=obra_social,
                    plan=plan,
                    numero_afiliado=(
                        limpiar_texto(
                            datos_erp.get("numero_afiliado")
                        ) or None
                    ),
                    medico=medico,
                    servicio=servicio,
                    numero=str(numerador.ultimo),
                    episodio=episodio_real,
                    fecha_ingreso=datos_erp.get(
                        "fecha_ingreso"
                    ),
                    fecha_probable_ingreso=None,
                    fecha_egreso=None,
                    diagnostico=diagnostico,
                    origen_paciente="otro",
                    prioridad="normal",

                    contacto_nombre=(
                        limpiar_texto(
                            datos_erp.get("contacto_nombre")
                        ) or None
                    ),
                    contacto_dni=(
                        limpiar_texto(
                            datos_erp.get("contacto_dni")
                        ) or None
                    ),
                    contacto_telefono=(
                        limpiar_texto(
                            datos_erp.get("contacto_telefono")
                        ) or None
                    ),
                    contacto_parentesco=(
                        limpiar_texto(
                            datos_erp.get("contacto_parentesco")
                        ) or None
                    ),

                    observaciones=observaciones or None,
                    estado="ingresado",
                    es_preingreso=False,
                    user_made=request.user,
                )

        except IntegrityError:
            messages.error(
                request,
                (
                    "No se pudo guardar el ingreso porque el episodio "
                    "o el paciente ya fue procesado."
                )
            )
            return redirect("gestion_app:lista_ingresos")

        except Exception:
            messages.error(
                request,
                "No se pudo guardar el ingreso. Intente nuevamente."
            )
            return redirect("gestion_app:guardar_ingreso_erp")

        messages.success(
            request,
            f"El ingreso #{ingreso.numero} fue creado correctamente."
        )

        return redirect("gestion_app:lista_ingresos")

    return render(
        request,
        "gestion/ingreso/guardar_ingreso_erp.html",
        {
            "obras_sociales": obras_sociales,
            "planes": planes,
            "servicios": servicios,
        },
    )



def consultar_paciente_innova(documento):
    documento = limpiar_texto(documento)

    if not documento:
        return None

    sql = """
        SELECT TOP (1)
            p.Documento_Numero AS dni,
            p.Nombres AS nombre,
            p.Apellido AS apellido,
            p.Sexo AS genero,
            CONVERT(date, p.FechaNacimiento) AS fecha_nacimiento,
            p.TelefonoCelular AS telefono
        FROM Personas AS p
        WHERE p.Documento_Numero = %s
    """

    with connections["innova"].cursor() as cursor:
        cursor.execute(sql, [documento])
        return dictfetchone(cursor)


@login_required
@require_GET
def buscar_paciente_innova_preingreso(request):
    documento = limpiar_texto(
        request.GET.get("documento")
    )

    if not documento:
        return JsonResponse({
            "ok": False,
            "error": "Debe ingresar el documento del paciente."
        }, status=400)

    try:
        datos = consultar_paciente_innova(documento)

    except Exception:
        return JsonResponse({
            "ok": False,
            "error": "No se pudo consultar INNOVA."
        }, status=500)

    if not datos:
        return JsonResponse({
            "ok": False,
            "error": "No se encontró el paciente en INNOVA."
        }, status=404)

    dni = limpiar_texto(datos.get("dni"))

    paciente_local = (
        Paciente.objects
        .filter(dni=dni)
        .first()
    )

    fecha_nacimiento = datos.get(
        "fecha_nacimiento"
    )

    return JsonResponse({
        "ok": True,
        "paciente": {
            "id": (
                paciente_local.id
                if paciente_local
                else None
            ),
            "existe_localmente": bool(
                paciente_local
            ),
            "dni": dni,
            "nombre": limpiar_texto(
                datos.get("nombre")
            ),
            "apellido": limpiar_texto(
                datos.get("apellido")
            ),
            "fecha_nacimiento": (
                fecha_nacimiento.isoformat()
                if fecha_nacimiento
                else ""
            ),
            "genero": normalizar_genero_innova(
                datos.get("genero")
            ),
            "telefono": limpiar_texto(
                datos.get("telefono")
            ),
        }
    })