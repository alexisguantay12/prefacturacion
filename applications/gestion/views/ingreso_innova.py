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

from applications.gestion.models import Preingreso, Numerador, OrdenAutorizacion

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


def dictfetchall(cursor):
    """
    Convierte todas las filas SQL en una lista de diccionarios
    utilizando los alias definidos en el SELECT.
    """
    rows = cursor.fetchall()

    columns = [
        column[0]
        for column in cursor.description
    ]

    return [
        dict(zip(columns, row))
        for row in rows
    ]


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
            CONVERT(date,e.IngresoReal) AS fecha_ingreso,
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
          AND UPPER(LTRIM(RTRIM(ISNULL(p.Nombres, '')))) <> 'RN'
        ORDER BY e.Id DESC;
    """

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



def consultar_episodios_innova(documento):
    """
    Busca todos los episodios del paciente correspondientes
    a los últimos 45 días.

    Se utiliza únicamente para mostrar el listado inicial
    de episodios disponibles para seleccionar.
    """
    documento = limpiar_texto(documento)

    if not documento:
        return []

    sql = """
        SELECT
            e.Id AS episodio,
            CONVERT(date, e.IngresoReal) AS fecha_ingreso,
            p.Documento_Numero AS dni,
            p.Nombres AS nombre,
            p.Apellido AS apellido
        FROM hce.Internacion.Episodios AS e
        INNER JOIN Personas AS p
            ON p.Id = e.IdPersona
        WHERE p.Documento_Numero = %s
          AND e.IdTipoEpisodio IN (1,2)
          AND e.IngresoReal >= DATEADD(DAY, -45, GETDATE())
          AND e.Estado='A'
          AND UPPER(
                LTRIM(
                    RTRIM(
                        ISNULL(p.Nombres, '')
                    )
                )
              ) <> 'RN'
        ORDER BY
            e.IngresoReal DESC,
            e.Id DESC;
    """

    try:
        with connections["innova"].cursor() as cursor:
            cursor.execute(
                sql,
                [documento]
            )

            episodios = dictfetchall(
                cursor
            )

        print(
            "Episodios encontrados:",
            episodios
        )

    except Exception as error:
        print(
            "ERROR AL CONSULTAR EPISODIOS EN INNOVA"
        )
        print(
            "Tipo:",
            type(error).__name__
        )
        print(
            "Detalle:",
            str(error)
        )

        raise

    return episodios


@login_required
@require_GET
def buscar_ingreso_erp(request):
    documento = limpiar_texto(
        request.GET.get("documento")
    )

    if not documento:
        return JsonResponse(
            {
                "ok": False,
                "error": "Debe ingresar el documento del paciente.",
            },
            status=400,
        )

    try:
        episodios = consultar_episodios_innova(
            documento
        )

    except Exception:
        return JsonResponse(
            {
                "ok": False,
                "error": "No se pudo consultar el sistema INNOVA.",
            },
            status=500,
        )

    if not episodios:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No se encontraron episodios para "
                    "el documento indicado en los últimos 45 días."
                ),
            },
            status=404,
        )

    episodios_response = []

    for datos in episodios:
        episodio = limpiar_texto(
            datos.get("episodio")
        )

        dni = limpiar_texto(
            datos.get("dni")
        )

        fecha_ingreso = datos.get(
            "fecha_ingreso"
        )

        ya_importado = (
            Preingreso.objects
            .filter(
                episodio=episodio
            )
            .exists()
        )

        episodios_response.append(
            {
                "episodio": episodio,

                "dni": dni,

                "nombre": limpiar_texto(
                    datos.get("nombre")
                ),

                "apellido": limpiar_texto(
                    datos.get("apellido")
                ),

                "fecha_ingreso": (
                    fecha_ingreso.isoformat()
                    if fecha_ingreso else ""
                ),

                "ya_importado": ya_importado,
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "episodios": episodios_response,
        }
    )


def consultar_episodio_innova_por_id(
    documento,
    episodio
):
    """
    Recupera de INNOVA un episodio específico correspondiente
    al DNI indicado.

    Se utiliza después de que el usuario selecciona un episodio
    y también para revalidarlo antes de guardar.
    """
    documento = limpiar_texto(documento)
    episodio = limpiar_texto(episodio)

    if not documento or not episodio:
        return None

    sql = """
        SELECT TOP (1)
            e.Id AS episodio,
            CONVERT(date, e.IngresoReal) AS fecha_ingreso,
            e.Estado AS estado_episodio,
            e.Diagnostico AS diagnostico,
            e.MotivoIngreso AS motivo_ingreso,

            p.Documento_Numero AS dni,
            p.Nombres AS nombre,
            p.Apellido AS apellido,
            p.Sexo AS genero,
            CONVERT(date, p.FechaNacimiento) AS fecha_nacimiento,
            p.TelefonoCelular AS telefono,

            ex.NumeroDeAfiliado AS numero_afiliado,

            prof.Matricula AS medico_matricula,
            per.Nombres AS medico_nombre,
            per.Apellido AS medico_apellido,
            per.Documento_Numero AS medico_documento,

            CONCAT(
                par.Nombres,
                ', ',
                par.Apellido
            ) AS contacto_nombre,

            par.Documento_Numero AS contacto_dni,
            par.TelefonoCelular AS contacto_telefono,
            p2.Nombre AS contacto_parentesco

        FROM hce.Internacion.Episodios AS e

        INNER JOIN Personas AS p
            ON p.Id = e.IdPersona

        LEFT JOIN Profesionales AS prof
            ON prof.Id = e.IdProfesionalResponsableDeCabecera

        LEFT JOIN Personas AS per
            ON per.Id = prof.IdPersona

        LEFT JOIN Personas AS par
            ON par.Id = e.IdPersonaTutor

        LEFT JOIN Parentescos AS p2
            ON p2.Id = e.IdParentescoTutor

        LEFT JOIN Internacion.Expedientes AS ex
            ON ex.Id = e.IdExpediente

        WHERE p.Documento_Numero = %s
          AND e.Id = %s
          AND e.IdTipoEpisodio IN (1,2)
          AND e.IngresoReal >= DATEADD(DAY, -45, GETDATE())
          AND UPPER(
                LTRIM(
                    RTRIM(
                        ISNULL(p.Nombres, '')
                    )
                )
              ) <> 'RN';
    """

    try:
        with connections["innova"].cursor() as cursor:
            cursor.execute(
                sql,
                [
                    documento,
                    episodio,
                ]
            )

            datos = dictfetchone(
                cursor
            )

        print(
            "Episodio específico encontrado:",
            datos
        )

    except Exception as error:
        print(
            "ERROR AL CONSULTAR EPISODIO EN INNOVA"
        )
        print(
            "Tipo:",
            type(error).__name__
        )
        print(
            "Detalle:",
            str(error)
        )

        raise

    if not datos:
        return None

    datos["diagnostico_final"] = (
        obtener_diagnostico_innova(
            datos
        )
    )

    return datos



def obtener_preingresos_candidatos(dni):
    """
    Busca preingresos abiertos del mismo paciente para mostrarlos
    como posibles coincidencias del episodio seleccionado en INNOVA.

    No vincula ni modifica nada: la selección queda a cargo del operador.
    """
    dni = limpiar_texto(dni)

    if not dni:
        return []

    preingresos = (
        Preingreso.objects
        .filter(
            paciente__dni=dni,
            es_preingreso=True,
            estado__in=(
                "pendiente",
                "en_gestion",
            ),
        )
        .select_related(
            "paciente",
            "obra_social",
            "plan",
            "medico",
            "servicio",
        )
        .order_by(
            "fecha_probable_ingreso",
            "id",
        )
    )

    resultado = []

    for preingreso in preingresos:

        if limpiar_texto(preingreso.episodio):
            continue

        total_ordenes = (
            OrdenAutorizacion.objects
            .filter(preingreso=preingreso)
            .count()
        )

        medico = ""

        if preingreso.medico:
            medico = limpiar_texto(
                f"{preingreso.medico.apellido}, "
                f"{preingreso.medico.nombre}"
            )

        servicio = ""

        if preingreso.servicio:
            servicio = limpiar_texto(
                preingreso.servicio.nombre
            )

        obra_social = ""

        if preingreso.obra_social:
            obra_social = limpiar_texto(
                preingreso.obra_social.nombre
            )

        plan = ""

        if preingreso.plan:
            plan = limpiar_texto(
                preingreso.plan.nombre
            )

        resultado.append(
            {
                "id": preingreso.id,

                "numero": (
                    limpiar_texto(preingreso.numero)
                    or str(preingreso.id)
                ),

                "fecha_probable_ingreso": (
                    preingreso.fecha_probable_ingreso.isoformat()
                    if preingreso.fecha_probable_ingreso
                    else ""
                ),

                "estado": limpiar_texto(
                    preingreso.estado
                ),

                "estado_display": (
                    preingreso.get_estado_display()
                ),

                "servicio": servicio,

                "medico": medico,

                "obra_social": obra_social,

                "plan": plan,

                "numero_afiliado": limpiar_texto(
                    preingreso.numero_afiliado
                ),

                "diagnostico": limpiar_texto(
                    preingreso.diagnostico
                ),

                "observaciones": limpiar_texto(
                    preingreso.observaciones
                ),

                "total_ordenes": total_ordenes,
            }
        )

    return resultado


@login_required
@require_GET
def buscar_episodio_erp_detalle(request):
    documento = limpiar_texto(
        request.GET.get("documento")
    )

    episodio = limpiar_texto(
        request.GET.get("episodio")
    )

    if not documento:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Debe indicar el documento del paciente."
                ),
            },
            status=400,
        )

    if not episodio:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Debe indicar el episodio."
                ),
            },
            status=400,
        )

    try:
        datos = consultar_episodio_innova_por_id(
            documento,
            episodio
        )

    except Exception:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No se pudo consultar el episodio "
                    "en INNOVA."
                ),
            },
            status=500,
        )

    if not datos:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No se encontró el episodio indicado "
                    "para ese paciente dentro de los "
                    "últimos 45 días."
                ),
            },
            status=404,
        )

    episodio_real = limpiar_texto(
        datos.get("episodio")
    )

    dni = limpiar_texto(
        datos.get("dni")
    )

    if episodio_real != episodio:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El episodio recuperado no coincide "
                    "con el episodio solicitado."
                ),
            },
            status=409,
        )

    if dni != documento:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El episodio indicado no corresponde "
                    "al documento solicitado."
                ),
            },
            status=409,
        )

    if (
        Preingreso.objects
        .filter(
            episodio=episodio_real
        )
        .exists()
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El episodio seleccionado ya fue "
                    "importado anteriormente."
                ),
            },
            status=409,
        )

    paciente_local = (
        Paciente.objects
        .filter(
            dni=dni
        )
        .first()
    )

    # ---------------------------------------------------------
    # POSIBLES PREINGRESOS RELACIONADOS
    # ---------------------------------------------------------
    # Se buscan por DNI, pero no se asocian automáticamente.
    # El frontend permitirá que el operador elija uno o continúe
    # sin preingreso.
    # ---------------------------------------------------------

    preingresos = obtener_preingresos_candidatos(
        dni
    )

    fecha_ingreso = datos.get(
        "fecha_ingreso"
    )

    fecha_nacimiento = datos.get(
        "fecha_nacimiento"
    )

    return JsonResponse(
        {
            "ok": True,

            "tiene_preingresos": bool(
                preingresos
            ),

            "preingresos": preingresos,

            "datos": {
                "episodio": episodio_real,

                "fecha_ingreso": (
                    fecha_ingreso.isoformat()
                    if fecha_ingreso else ""
                ),

                "estado_episodio": limpiar_texto(
                    datos.get("estado_episodio")
                ),

                "diagnostico": (
                    datos.get("diagnostico_final")
                    or ""
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
                    if fecha_nacimiento else ""
                ),

                "telefono": limpiar_texto(
                    datos.get("telefono")
                ),

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

                "paciente_existe": bool(
                    paciente_local
                ),
            },
        }
    )

 
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
        episodio_enviado = limpiar_texto(request.POST.get("episodio"))
        telefono = limpiar_texto(request.POST.get("telefono"))
        obra_social_id = request.POST.get("obra_social")
        plan_id = request.POST.get("plan")
        servicio_id = request.POST.get("servicio") or None
        observaciones = limpiar_texto(request.POST.get("observaciones"))
        preingreso_id = limpiar_texto(request.POST.get("preingreso_id"))

        # -----------------------------------------------------
        # VALIDACIONES INICIALES
        # -----------------------------------------------------

        if preingreso_id and not preingreso_id.isdigit():
            messages.error(
                request,
                "El preingreso seleccionado no es válido."
            )
            return redirect("gestion_app:guardar_ingreso_erp")

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

        # -----------------------------------------------------
        # COBERTURA
        # -----------------------------------------------------

        obra_social = ObraSocial.objects.filter(
            id=obra_social_id
        ).first()

        plan = (
            Plan.objects
            .select_related("obra_social")
            .filter(id=plan_id)
            .first()
        )

        servicio = (
            Servicio.objects.filter(id=servicio_id).first()
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

        # -----------------------------------------------------
        # REVALIDAR EPISODIO EXACTO EN INNOVA
        # -----------------------------------------------------

        try:
            datos_erp = consultar_episodio_innova_por_id(
                dni,
                episodio_enviado
            )

        except Exception:
            messages.error(
                request,
                "No se pudo validar nuevamente el episodio en INNOVA."
            )
            return redirect("gestion_app:guardar_ingreso_erp")

        if not datos_erp:
            messages.error(
                request,
                "El episodio seleccionado ya no pudo ser encontrado en INNOVA."
            )
            return redirect("gestion_app:lista_ingresos")

        episodio_real = limpiar_texto(
            datos_erp.get("episodio")
        )

        dni_real = limpiar_texto(
            datos_erp.get("dni")
        )

        if episodio_real != episodio_enviado:
            messages.error(
                request,
                "El episodio recuperado desde INNOVA no coincide con el seleccionado."
            )
            return redirect("gestion_app:lista_ingresos")

        if dni_real != dni:
            messages.error(
                request,
                "El episodio recuperado desde INNOVA no corresponde al paciente indicado."
            )
            return redirect("gestion_app:lista_ingresos")

        # -----------------------------------------------------
        # DIAGNÓSTICO
        # -----------------------------------------------------

        diagnostico = obtener_diagnostico_innova(datos_erp)

        if not diagnostico:
            messages.error(
                request,
                "INNOVA no informó diagnóstico ni motivo de ingreso."
            )
            return redirect("gestion_app:guardar_ingreso_erp")

        # -----------------------------------------------------
        # DATOS DEL MÉDICO
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # TRANSACCIÓN
        # -----------------------------------------------------

        try:
            with transaction.atomic():

                # ---------------------------------------------
                # PREINGRESO SELECCIONADO
                # ---------------------------------------------

                preingreso_seleccionado = None

                if preingreso_id:

                    preingreso_seleccionado = (
                        Preingreso.objects
                        .select_for_update()
                        .select_related("paciente")
                        .filter(id=int(preingreso_id))
                        .first()
                    )

                    if not preingreso_seleccionado:
                        messages.error(
                            request,
                            "El preingreso seleccionado ya no existe."
                        )
                        return redirect(
                            "gestion_app:guardar_ingreso_erp"
                        )

                    if not preingreso_seleccionado.es_preingreso:
                        messages.error(
                            request,
                            "El registro seleccionado ya no es un preingreso disponible."
                        )
                        return redirect(
                            "gestion_app:lista_ingresos"
                        )

                    if preingreso_seleccionado.estado not in (
                        "pendiente",
                        "en_gestion"
                    ):
                        messages.error(
                            request,
                            "El preingreso seleccionado ya no está disponible para convertirse."
                        )
                        return redirect(
                            "gestion_app:lista_ingresos"
                        )

                    dni_preingreso = limpiar_texto(
                        preingreso_seleccionado.paciente.dni
                    )

                    if dni_preingreso != dni_real:
                        messages.error(
                            request,
                            "El preingreso no corresponde al paciente del episodio de INNOVA."
                        )
                        return redirect(
                            "gestion_app:guardar_ingreso_erp"
                        )

                    episodio_preingreso = limpiar_texto(
                        preingreso_seleccionado.episodio
                    )

                    if (
                        episodio_preingreso
                        and episodio_preingreso != episodio_real
                    ):
                        messages.error(
                            request,
                            "El preingreso ya posee otro episodio asociado."
                        )
                        return redirect(
                            "gestion_app:lista_ingresos"
                        )

                # ---------------------------------------------
                # EVITAR DUPLICAR EPISODIO
                # ---------------------------------------------

                episodios_existentes = (
                    Preingreso.objects
                    .select_for_update()
                    .filter(episodio=episodio_real)
                )

                if preingreso_seleccionado:
                    episodios_existentes = (
                        episodios_existentes.exclude(
                            id=preingreso_seleccionado.id
                        )
                    )

                if episodios_existentes.exists():
                    messages.error(
                        request,
                        "El episodio ya fue importado anteriormente."
                    )
                    return redirect(
                        "gestion_app:lista_ingresos"
                    )

                # ---------------------------------------------
                # PACIENTE
                # ---------------------------------------------

                paciente = (
                    Paciente.objects
                    .select_for_update()
                    .filter(dni=dni)
                    .first()
                )

                if paciente:

                    paciente.nombre = limpiar_texto(
                        datos_erp.get("nombre")
                    )

                    paciente.apellido = limpiar_texto(
                        datos_erp.get("apellido")
                    )

                    paciente.fecha_nacimiento = datos_erp.get(
                        "fecha_nacimiento"
                    )

                    paciente.genero = normalizar_genero_innova(
                        datos_erp.get("genero")
                    )

                    paciente.telefono = telefono or None

                    paciente.save(
                        update_fields=[
                            "nombre",
                            "apellido",
                            "fecha_nacimiento",
                            "genero",
                            "telefono",
                        ]
                    )

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

                # ---------------------------------------------
                # MÉDICO
                # ---------------------------------------------

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
                            numero_documento=medico_documento or None,
                            matricula=medico_matricula,
                            user_made=request.user,
                        )

                # =============================================
                # NUMERADOR ÚNICO PARA AMBOS TIPOS DE INGRESO
                # =============================================

                numerador, creado = (
                    Numerador.objects
                    .select_for_update()
                    .get_or_create(
                        nombre="ingreso",
                        defaults={"ultimo": 0}
                    )
                )

                numerador.ultimo += 1

                numerador.save(
                    update_fields=["ultimo"]
                )

                numero_ingreso = str(numerador.ultimo)

                # =============================================
                # CON PREINGRESO
                # CONVERTIR EL MISMO REGISTRO
                # =============================================

                if preingreso_seleccionado:

                    ingreso = preingreso_seleccionado

                    # NUEVO: asignar número del numerador
                    ingreso.numero = numero_ingreso

                    ingreso.paciente = paciente
                    ingreso.obra_social = obra_social
                    ingreso.plan = plan

                    ingreso.numero_afiliado = (
                        limpiar_texto(
                            datos_erp.get("numero_afiliado")
                        ) or None
                    )

                    ingreso.medico = medico
                    ingreso.servicio = servicio
                    ingreso.episodio = episodio_real

                    ingreso.fecha_ingreso = datos_erp.get(
                        "fecha_ingreso"
                    )

                    ingreso.fecha_egreso = None
                    ingreso.diagnostico = diagnostico

                    ingreso.contacto_nombre = (
                        limpiar_texto(
                            datos_erp.get("contacto_nombre")
                        ) or None
                    )

                    ingreso.contacto_dni = (
                        limpiar_texto(
                            datos_erp.get("contacto_dni")
                        ) or None
                    )

                    ingreso.contacto_telefono = (
                        limpiar_texto(
                            datos_erp.get("contacto_telefono")
                        ) or None
                    )

                    ingreso.contacto_parentesco = (
                        limpiar_texto(
                            datos_erp.get("contacto_parentesco")
                        ) or None
                    )

                    # Conservar observaciones originales
                    # cuando no se escriben nuevas.

                    if observaciones:
                        ingreso.observaciones = observaciones

                    ingreso.estado = "ingresado"
                    ingreso.es_preingreso = False

                    ingreso.save()

                # =============================================
                # SIN PREINGRESO
                # CREAR INGRESO NUEVO
                # =============================================

                else:

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

                        # MISMO NUMERADOR
                        numero=numero_ingreso,

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
                "No se pudo guardar el ingreso porque el episodio ya fue procesado o existe un conflicto de integridad."
            )

            return redirect(
                "gestion_app:lista_ingresos"
            )

        except Exception as error:

            print("ERROR AL GUARDAR INGRESO ERP")
            print("Tipo:", type(error).__name__)
            print("Detalle:", str(error))

            messages.error(
                request,
                "No se pudo guardar el ingreso. Intente nuevamente."
            )

            return redirect(
                "gestion_app:guardar_ingreso_erp"
            )

        # -----------------------------------------------------
        # MENSAJE DE ÉXITO
        # -----------------------------------------------------

        if preingreso_id:

            messages.success(
                request,
                (
                    f"El preingreso fue vinculado al episodio "
                    f"{episodio_real} y convertido correctamente "
                    f"en el ingreso #{ingreso.numero}."
                )
            )

        else:

            messages.success(
                request,
                f"El ingreso #{ingreso.numero} fue creado correctamente."
            )

        return redirect(
            "gestion_app:lista_ingresos"
        )

    # ---------------------------------------------------------
    # GET
    # ---------------------------------------------------------

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

    dni = limpiar_texto(
        datos.get("dni")
    )

    paciente_local = (
        Paciente.objects
        .filter(
            dni=dni
        )
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