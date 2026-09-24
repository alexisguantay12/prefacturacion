from datetime import date
from django.utils.dateparse import parse_date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count, Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from applications.entidades.models import Medico
from applications.gestion.models import (
    OrdenAutorizacion,
    PlanillaEntrega,
    DetallePlanillaEntrega,
)


# =============================================================================
# LISTADO DE PLANILLAS
# =============================================================================

@login_required
def lista_planillas_entrega(request):

    query = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()

    planillas = (
        PlanillaEntrega.objects
        .select_related(
            "medico",
            "user_confirmacion",
            "user_entrega",
            "user_anulacion",
        )
        .annotate(
            total_ordenes=Count(
                "detalles",
                distinct=True,
            )
        )
        .filter(
            is_deleted=False
        )
        .order_by("-id")
    )

    # -------------------------------------------------------------------------
    # BÚSQUEDA
    # -------------------------------------------------------------------------

    if query:
        planillas = planillas.filter(
            Q(medico__apellido__icontains=query)
            | Q(medico__nombre__icontains=query)
            | Q(medico__matricula__icontains=query)
            | Q(observaciones__icontains=query)
            | Q(id__icontains=query)
        )

    # -------------------------------------------------------------------------
    # ESTADO
    # -------------------------------------------------------------------------

    if estado in [
        "borrador",
        "confirmada",
        "entregada",
        "anulada",
    ]:
        planillas = planillas.filter(
            estado=estado
        )

    # -------------------------------------------------------------------------
    # PAGINACIÓN
    # -------------------------------------------------------------------------

    paginator = Paginator(
        planillas,
        15,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "planillas": page_obj.object_list,
        "page_obj": page_obj,
        "query": query,
        "estado": estado,
    }

    return render(
        request,
        "gestion/entregas/lista_planillas_entrega.html",
        context,
    )


# =============================================================================
# CONFIRMAR PLANILLA
# =============================================================================
#
# Facturación terminó de confeccionar la planilla.
#
# IMPORTANTE:
# Confirmar NO significa entregar físicamente.
#
# En esta acción:
#   - se cambia estado a "confirmada"
#   - se registra quién confirmó
#   - se registra cuándo confirmó
#   - NO se modifica OrdenAutorizacion.esta_entregada
#
# =============================================================================

@login_required
@require_POST
@transaction.atomic
def confirmar_planilla_entrega(request, planilla_id):

    planilla = get_object_or_404(
        PlanillaEntrega.objects
        .select_for_update()
        .select_related("medico"),
        id=planilla_id,
        is_deleted=False,
    )

    # -------------------------------------------------------------------------
    # VALIDACIONES DE ESTADO
    # -------------------------------------------------------------------------

    if planilla.estado == "anulada":
        return JsonResponse({
            "ok": False,
            "message": (
                "No se puede confirmar una planilla anulada."
            ),
        }, status=400)

    if planilla.estado == "entregada":
        return JsonResponse({
            "ok": False,
            "message": (
                "La planilla ya fue entregada."
            ),
        }, status=400)

    if planilla.estado == "confirmada":
        return JsonResponse({
            "ok": False,
            "message": (
                "La planilla ya se encuentra confirmada."
            ),
        }, status=400)

    if planilla.estado != "borrador":
        return JsonResponse({
            "ok": False,
            "message": (
                "El estado actual de la planilla "
                "no permite confirmarla."
            ),
        }, status=400)

    # -------------------------------------------------------------------------
    # DETALLES
    # -------------------------------------------------------------------------

    detalles = (
        DetallePlanillaEntrega.objects
        .select_for_update()
        .filter(
            planilla_entrega=planilla,
        )
    )

    if not detalles.exists():
        return JsonResponse({
            "ok": False,
            "message": (
                "La planilla no contiene órdenes."
            ),
        }, status=400)

    ordenes_ids = list(
        detalles.values_list(
            "orden_id",
            flat=True,
        )
    )

    # -------------------------------------------------------------------------
    # VALIDAR ÓRDENES
    # -------------------------------------------------------------------------

    ordenes = (
        OrdenAutorizacion.objects
        .select_for_update()
        .filter(
            id__in=ordenes_ids,
            deleted_at__isnull=True,
            medico_tenencia_id=planilla.medico_id,
            autorizada=True,
            estado="autorizada",
            esta_entregada=False,
        )
    )

    if ordenes.count() != len(ordenes_ids):

        return JsonResponse({
            "ok": False,
            "message": (
                "Una o más órdenes de la planilla "
                "ya no están disponibles para confirmar."
            ),
        }, status=400)

    # -------------------------------------------------------------------------
    # CONFIRMAR
    # -------------------------------------------------------------------------

    planilla.estado = "confirmada"
    planilla.fecha_confirmacion = timezone.now()
    planilla.user_confirmacion = request.user
    planilla.user_updated = request.user

    planilla.save(
        update_fields=[
            "estado",
            "fecha_confirmacion",
            "user_confirmacion",
            "user_updated",
        ]
    )

    return JsonResponse({
        "ok": True,
        "message": (
            f"La planilla N.º {planilla.id} "
            "fue confirmada correctamente."
        ),
    })


# =============================================================================
# ANULAR PLANILLA
# =============================================================================
#
# Se permite anular:
#   - borrador
#   - confirmada
#
# No se permite anular:
#   - entregada
#
# Como las órdenes todavía no están físicamente entregadas,
# NO tenemos que modificar esta_entregada.
#
# =============================================================================

@login_required
@require_POST
@transaction.atomic
def anular_planilla_entrega(request, planilla_id):

    planilla = get_object_or_404(
        PlanillaEntrega.objects.select_for_update(),
        id=planilla_id,
        is_deleted=False,
    )

    if planilla.estado == "anulada":

        return JsonResponse({
            "ok": False,
            "message": (
                "La planilla ya se encuentra anulada."
            ),
        }, status=400)

    if planilla.estado == "entregada":

        return JsonResponse({
            "ok": False,
            "message": (
                "No se puede anular una planilla "
                "que ya fue entregada."
            ),
        }, status=400)

    # -------------------------------------------------------------------------
    # ANULAR
    # -------------------------------------------------------------------------

    planilla.estado = "anulada"
    planilla.fecha_anulacion = timezone.now()
    planilla.user_anulacion = request.user
    planilla.user_updated = request.user

    planilla.save(
        update_fields=[
            "estado",
            "fecha_anulacion",
            "user_anulacion",
            "user_updated",
        ]
    )

    return JsonResponse({
        "ok": True,
        "message": (
            "La planilla fue anulada correctamente."
        ),
    })


# =============================================================================
# ENTREGAR PLANILLA
# =============================================================================
#
# Esta acción corresponde a la entrega física.
#
# Solo puede ejecutarse sobre una planilla CONFIRMADA.
#
# Recién acá:
#
#   OrdenAutorizacion.esta_entregada = True
#   OrdenAutorizacion.fecha_entrega = hoy
#   OrdenAutorizacion.user_entrega = usuario
#
# =============================================================================
@login_required
@require_POST
@transaction.atomic
def entregar_planilla_entrega(request, planilla_id):

    planilla = get_object_or_404(
        PlanillaEntrega.objects.select_for_update(),
        id=planilla_id,
        is_deleted=False,
    )

    # -------------------------------------------------------------------------
    # VALIDACIONES DE ESTADO
    # -------------------------------------------------------------------------

    if planilla.estado == "anulada":

        return JsonResponse({
            "ok": False,
            "message": (
                "No se puede entregar una planilla anulada."
            ),
        }, status=400)

    if planilla.estado == "entregada":

        return JsonResponse({
            "ok": False,
            "message": (
                "La planilla ya fue entregada."
            ),
        }, status=400)

    if planilla.estado != "confirmada":

        return JsonResponse({
            "ok": False,
            "message": (
                "La planilla debe estar confirmada "
                "antes de realizar la entrega."
            ),
        }, status=400)

    # -------------------------------------------------------------------------
    # OBSERVACIÓN DE ENTREGA
    # -------------------------------------------------------------------------

    observacion_entrega = request.POST.get(
        "observacion_entrega",
        "",
    ).strip()

    # La dejamos opcional.
    # Si más adelante quieren hacerla obligatoria,
    # validamos acá.

    if len(observacion_entrega) > 500:

        return JsonResponse({
            "ok": False,
            "message": (
                "La observación de entrega no puede "
                "superar los 500 caracteres."
            ),
        }, status=400)

    # -------------------------------------------------------------------------
    # ÓRDENES
    # -------------------------------------------------------------------------

    ordenes_ids = list(
        planilla.detalles.values_list(
            "orden_id",
            flat=True,
        )
    )

    if not ordenes_ids:

        return JsonResponse({
            "ok": False,
            "message": (
                "La planilla no contiene órdenes."
            ),
        }, status=400)

    ordenes = (
        OrdenAutorizacion.objects
        .select_for_update()
        .filter(
            id__in=ordenes_ids,
            deleted_at__isnull=True,
            autorizada=True,
            estado="autorizada",
            esta_entregada=False,
        )
    )

    if ordenes.count() != len(ordenes_ids):

        return JsonResponse({
            "ok": False,
            "message": (
                "Una o más órdenes de la planilla "
                "ya no pueden ser entregadas."
            ),
        }, status=400)

    # -------------------------------------------------------------------------
    # FECHA DE ENTREGA
    # -------------------------------------------------------------------------

    fecha_entrega = timezone.now()

    # -------------------------------------------------------------------------
    # ACTUALIZAR PLANILLA
    # -------------------------------------------------------------------------

    planilla.estado = "entregada"
    planilla.fecha_entrega = fecha_entrega
    planilla.user_entrega = request.user
    planilla.observacion_entrega = (
        observacion_entrega or None
    )
    planilla.user_updated = request.user

    planilla.save(
        update_fields=[
            "estado",
            "fecha_entrega",
            "user_entrega",
            "observacion_entrega",
            "user_updated",
        ]
    )

    # -------------------------------------------------------------------------
    # ACTUALIZAR ÓRDENES
    # -------------------------------------------------------------------------

    cantidad_ordenes = ordenes.update(
        esta_entregada=True,
        fecha_entrega=fecha_entrega,
        user_entrega=request.user,
    )

    # -------------------------------------------------------------------------
    # RESPUESTA
    # -------------------------------------------------------------------------

    return JsonResponse({
        "ok": True,
        "message": (
            "La planilla fue marcada como entregada. "
            f"Se actualizaron {cantidad_ordenes} órdenes."
        ),
        "print_url": request.build_absolute_uri(
            redirect(
                "gestion_app:imprimir_planilla_entrega",
                planilla.id,
            ).url
        ),
    })

# =============================================================================
# IMPRIMIR PLANILLA
# =============================================================================

@login_required
def imprimir_planilla_entrega(request, planilla_id):

    planilla = get_object_or_404(
        PlanillaEntrega.objects
        .select_related(
            "medico",
            "user_confirmacion",
            "user_entrega",
            "user_anulacion",
        )
        .prefetch_related(
            "detalles",
            "detalles__orden",
            "detalles__orden__preingreso",
            "detalles__orden__preingreso__paciente",
            "detalles__orden__preingreso__obra_social",
            "detalles__orden__detalles",
            "detalles__orden__detalles__prestacion",
        ),
        id=planilla_id,
        is_deleted=False,
    )

    context = {
        "planilla": planilla,
        "detalles": planilla.detalles.all(),
        "fecha_impresion": timezone.now(),
    }

    return render(
        request,
        "gestion/entregas/imprimir_planilla_entrega.html",
        context,
    )


# =============================================================================
# DETALLE PLANILLA
# =============================================================================

@login_required
def detalle_planilla_entrega(request, planilla_id):

    planilla = get_object_or_404(
        PlanillaEntrega.objects.select_related(
            "medico",
            "user_confirmacion",
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
            "orden__preingreso__obra_social",
            "orden__medico",
            "orden__medico_tenencia",
            "user_made",
        )
        .prefetch_related(
            "orden__detalles__prestacion",
        )
        .order_by(
            "orden__id"
        )
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


# =============================================================================
# CONFECCIONAR PLANILLA DE ENTREGA
# =============================================================================

@login_required
def confeccionar_planilla_entrega(request):

    medico_id = (
        request.GET.get("medico")
        or request.POST.get("medico")
    )

    medico = None
    ordenes = []

    # =========================================================================
    # MÉDICOS DISPONIBLES
    # =========================================================================

    # -------------------------------------------------------------------------
    # Para cada orden determinamos si ya está incluida en una planilla activa.
    #
    # Planillas que bloquean la orden:
    #
    # - borrador
    # - confirmada
    # - entregada
    #
    # Una planilla anulada NO bloquea la orden.
    # -------------------------------------------------------------------------

    orden_en_planilla_activa = (
        DetallePlanillaEntrega.objects
        .filter(
            orden_id=OuterRef("pk"),
            planilla_entrega__is_deleted=False,
        )
        .exclude(
            planilla_entrega__estado="anulada"
        )
    )

    # -------------------------------------------------------------------------
    # Órdenes disponibles por médico
    # -------------------------------------------------------------------------

    ordenes_disponibles_medico = (
        OrdenAutorizacion.objects
        .filter(
            medico_tenencia_id=OuterRef("pk"),
            deleted_at__isnull=True,
            autorizada=True,
            estado="autorizada",
            esta_entregada=False,
        )
        .annotate(
            ya_en_planilla=Exists(
                orden_en_planilla_activa
            )
        )
        .filter(
            ya_en_planilla=False
        )
    )

    # -------------------------------------------------------------------------
    # Solo médicos que tienen alguna orden disponible
    # -------------------------------------------------------------------------

    medicos = (
        Medico.objects
        .filter(
            is_deleted=False
        )
        .annotate(
            tiene_ordenes_pendientes=Exists(
                ordenes_disponibles_medico
            )
        )
        .filter(
            tiene_ordenes_pendientes=True
        )
        .order_by(
            "apellido",
            "nombre",
        )
    )

    # =========================================================================
    # ÓRDENES DEL MÉDICO SELECCIONADO
    # =========================================================================

    if medico_id:

        medico = (
            Medico.objects
            .filter(
                id=medico_id,
                is_deleted=False,
            )
            .first()
        )

        if medico:

            detalle_planilla_activa = (
                DetallePlanillaEntrega.objects
                .filter(
                    orden_id=OuterRef("pk"),
                    planilla_entrega__is_deleted=False,
                )
                .exclude(
                    planilla_entrega__estado="anulada"
                )
            )

            ordenes = (
                OrdenAutorizacion.objects
                .select_related(
                    "preingreso",
                    "preingreso__paciente",
                    "preingreso__obra_social",
                    "preingreso__plan",
                    "medico_tenencia",
                )
                .prefetch_related(
                    "detalles",
                    "detalles__prestacion",
                )
                .annotate(
                    ya_en_planilla=Exists(
                        detalle_planilla_activa
                    )
                )
                .filter(
                    deleted_at__isnull=True,
                    medico_tenencia_id=medico_id,
                    autorizada=True,
                    estado="autorizada",
                    esta_entregada=False,
                    ya_en_planilla=False,
                )
                .order_by(
                    "fecha",
                    "id",
                )
            )

            ordenes = list(ordenes)

            # -----------------------------------------------------------------
            # DATOS AUXILIARES PARA EL FRONT
            # -----------------------------------------------------------------

            for orden in ordenes:

                detalles_validos = [
                    detalle
                    for detalle in orden.detalles.all()
                    if getattr(
                        detalle,
                        "deleted_at",
                        None,
                    ) is None
                ]

                # -------------------------------------------------------------
                # FECHA DE EJECUCIÓN
                # -------------------------------------------------------------

                fechas_detalles = [
                    detalle.fecha_desde
                    for detalle in detalles_validos
                    if detalle.fecha_desde
                ]

                if getattr(
                    orden,
                    "fecha_ejecucion",
                    None,
                ):

                    orden.fecha_ejecucion_mostrar = (
                        orden.fecha_ejecucion
                    )

                elif fechas_detalles:

                    orden.fecha_ejecucion_mostrar = min(
                        fechas_detalles
                    )

                else:

                    orden.fecha_ejecucion_mostrar = (
                        orden.fecha
                    )

                # -------------------------------------------------------------
                # CÓDIGOS DE PRESTACIONES
                # -------------------------------------------------------------
                #
                # Los dejamos únicos y conservando el orden.
                #
                # Ejemplo:
                #
                # 80720, 180130, 180125
                #
                # -------------------------------------------------------------

                codigos = []

                for detalle in detalles_validos:

                    prestacion = getattr(
                        detalle,
                        "prestacion",
                        None,
                    )

                    codigo = getattr(
                        prestacion,
                        "codigo",
                        None,
                    )

                    if not codigo:
                        continue

                    codigo = str(
                        codigo
                    ).strip()

                    if (
                        codigo
                        and codigo not in codigos
                    ):
                        codigos.append(
                            codigo
                        )

                orden.codigos_prestaciones = codigos

    # =========================================================================
    # POST - CREACIÓN DE PLANILLA
    # =========================================================================

    if request.method == "POST":

        accion = request.POST.get(
            "accion",
            "",
        ).strip()

        ordenes_ids_post = request.POST.getlist(
            "ordenes"
        )

        observaciones = request.POST.get(
            "observaciones",
            "",
        ).strip()

        # ---------------------------------------------------------------------
        # MÉDICO
        # ---------------------------------------------------------------------

        if not medico_id:

            messages.error(
                request,
                "Debe seleccionar un médico.",
            )

            return redirect(
                "gestion_app:confeccionar_planilla_entrega"
            )

        medico_post = (
            Medico.objects
            .filter(
                id=medico_id,
                is_deleted=False,
            )
            .first()
        )

        if not medico_post:

            messages.error(
                request,
                "El médico seleccionado no es válido.",
            )

            return redirect(
                "gestion_app:confeccionar_planilla_entrega"
            )

        # ---------------------------------------------------------------------
        # ÓRDENES
        # ---------------------------------------------------------------------

        if not ordenes_ids_post:

            messages.error(
                request,
                "Debe seleccionar al menos una orden autorizada.",
            )

            return redirect(
                f"{request.path}?medico={medico_id}"
            )

        # ---------------------------------------------------------------------
        # ACCIÓN
        # ---------------------------------------------------------------------

        if accion not in [
            "borrador",
            "confirmar",
        ]:

            messages.error(
                request,
                "Acción inválida.",
            )

            return redirect(
                f"{request.path}?medico={medico_id}"
            )

        # ---------------------------------------------------------------------
        # IDS
        # ---------------------------------------------------------------------

        try:

            ordenes_ids = {
                int(orden_id)
                for orden_id in ordenes_ids_post
            }

        except (TypeError, ValueError):

            messages.error(
                request,
                "La selección contiene órdenes inválidas.",
            )

            return redirect(
                f"{request.path}?medico={medico_id}"
            )

        # =====================================================================
        # TRANSACCIÓN
        # =====================================================================

        with transaction.atomic():

            # -----------------------------------------------------------------
            # BLOQUEAR ÓRDENES
            # -----------------------------------------------------------------

            ordenes_seleccionadas = list(
                OrdenAutorizacion.objects
                .select_for_update()
                .filter(
                    id__in=ordenes_ids,
                    deleted_at__isnull=True,
                    medico_tenencia_id=medico_id,
                    autorizada=True,
                    estado="autorizada",
                    esta_entregada=False,
                )
            )

            encontrados_ids = {
                orden.id
                for orden in ordenes_seleccionadas
            }

            if encontrados_ids != ordenes_ids:

                messages.error(
                    request,
                    (
                        "Una o más órdenes seleccionadas "
                        "ya no se encuentran disponibles."
                    ),
                )

                return redirect(
                    f"{request.path}?medico={medico_id}"
                )

            # -----------------------------------------------------------------
            # VALIDAR OTRA PLANILLA
            # -----------------------------------------------------------------

            usadas = set(
                DetallePlanillaEntrega.objects
                .filter(
                    orden_id__in=ordenes_ids,
                    planilla_entrega__is_deleted=False,
                )
                .exclude(
                    planilla_entrega__estado="anulada"
                )
                .values_list(
                    "orden_id",
                    flat=True,
                )
            )

            if usadas:

                messages.error(
                    request,
                    (
                        "Una o más órdenes seleccionadas "
                        "ya fueron incluidas en otra planilla."
                    ),
                )

                return redirect(
                    f"{request.path}?medico={medico_id}"
                )

            # -----------------------------------------------------------------
            # ESTADO INICIAL
            # -----------------------------------------------------------------

            if accion == "confirmar":
                estado_planilla = "confirmada"
            else:
                estado_planilla = "borrador"

            # -----------------------------------------------------------------
            # CREAR PLANILLA
            # -----------------------------------------------------------------

            planilla = PlanillaEntrega.objects.create(

                medico_id=medico_id,

                estado=estado_planilla,

                observaciones=observaciones,

                fecha_confirmacion=(
                    timezone.now()
                    if accion == "confirmar"
                    else None
                ),

                user_confirmacion=(
                    request.user
                    if accion == "confirmar"
                    else None
                ),

                user_made=request.user,
            )

            # -----------------------------------------------------------------
            # DETALLES
            # -----------------------------------------------------------------

            detalles = [
                DetallePlanillaEntrega(
                    planilla_entrega=planilla,
                    orden=orden,
                    user_made=request.user,
                )
                for orden in ordenes_seleccionadas
            ]

            DetallePlanillaEntrega.objects.bulk_create(
                detalles
            )

            # -----------------------------------------------------------------
            # IMPORTANTE
            #
            # NO se modifica:
            #
            # orden.esta_entregada
            # orden.fecha_entrega
            # orden.user_entrega
            #
            # Eso recién ocurre en la entrega física.
            # -----------------------------------------------------------------

        # =====================================================================
        # RESULTADO
        # =====================================================================

        if accion == "confirmar":

            messages.success(
                request,
                (
                    "La planilla fue confeccionada "
                    "y confirmada correctamente."
                ),
            )

        else:

            messages.success(
                request,
                (
                    "La planilla fue guardada como borrador."
                ),
            )

        return redirect(
            "gestion_app:detalle_planilla_entrega",
            planilla_id=planilla.id,
        )

    # =========================================================================
    # GET
    # =========================================================================

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


# =============================================================================
# EDITAR DATOS DE UNA ORDEN DESDE CONFECCIÓN DE PLANILLA
# =============================================================================

@login_required
@require_POST
def editar_datos_orden_planilla_ajax(request, orden_id):

    numero_cupon = request.POST.get(
        "numero_cupon",
        "",
    ).strip()

    fecha_ejecucion_raw = request.POST.get(
        "fecha_ejecucion",
        "",
    ).strip()

    # -------------------------------------------------------------------------
    # VALIDACIONES DE CAMPOS
    # -------------------------------------------------------------------------

    if not numero_cupon:

        return JsonResponse({
            "ok": False,
            "mensaje": (
                "Debe ingresar el número de cupón."
            ),
        }, status=400)

    if not fecha_ejecucion_raw:

        return JsonResponse({
            "ok": False,
            "mensaje": (
                "Debe ingresar la fecha de ejecución."
            ),
        }, status=400)

    fecha_ejecucion = parse_date(
        fecha_ejecucion_raw
    )

    if not fecha_ejecucion:

        return JsonResponse({
            "ok": False,
            "mensaje": (
                "La fecha de ejecución ingresada no es válida."
            ),
        }, status=400)

    # -------------------------------------------------------------------------
    # TRANSACCIÓN
    # -------------------------------------------------------------------------

    try:

        with transaction.atomic():

            orden = (
                OrdenAutorizacion.objects
                .select_for_update()
                .get(
                    id=orden_id,
                    deleted_at__isnull=True,
                )
            )

            # -----------------------------------------------------------------
            # DEBE ESTAR AUTORIZADA
            # -----------------------------------------------------------------

            if (
                not orden.autorizada
                or orden.estado != "autorizada"
            ):

                return JsonResponse({
                    "ok": False,
                    "mensaje": (
                        "Solo se pueden modificar órdenes autorizadas."
                    ),
                }, status=400)

            # -----------------------------------------------------------------
            # NO PUEDE ESTAR ENTREGADA
            # -----------------------------------------------------------------

            if orden.esta_entregada:

                return JsonResponse({
                    "ok": False,
                    "mensaje": (
                        "No se puede modificar una orden "
                        "que ya fue entregada."
                    ),
                }, status=400)

            # -----------------------------------------------------------------
            # SI YA ESTÁ EN UNA PLANILLA CONFIRMADA O ENTREGADA,
            # TAMPOCO PERMITIMOS CAMBIAR ESTOS DATOS DESDE ESTE CIRCUITO.
            #
            # Esto nos sirve también cuando adaptemos editar_planilla_entrega.
            # -----------------------------------------------------------------

            bloqueada_por_planilla = (
                DetallePlanillaEntrega.objects
                .filter(
                    orden=orden,
                    planilla_entrega__is_deleted=False,
                    planilla_entrega__estado__in=[
                        "confirmada",
                        "entregada",
                    ],
                )
                .exists()
            )

            if bloqueada_por_planilla:

                return JsonResponse({
                    "ok": False,
                    "mensaje": (
                        "La orden pertenece a una planilla "
                        "que ya fue confirmada o entregada."
                    ),
                }, status=400)

            # -----------------------------------------------------------------
            # ACTUALIZAR
            # -----------------------------------------------------------------

            orden.numero_cupon = numero_cupon
            orden.fecha_ejecucion = fecha_ejecucion
            orden.user_updated = request.user

            orden.save(
                update_fields=[
                    "numero_cupon",
                    "fecha_ejecucion",
                    "user_updated",
                ]
            )

    except OrdenAutorizacion.DoesNotExist:

        return JsonResponse({
            "ok": False,
            "mensaje": (
                "La orden indicada no existe."
            ),
        }, status=404)

    # -------------------------------------------------------------------------
    # RESPUESTA
    # -------------------------------------------------------------------------

    return JsonResponse({
        "ok": True,
        "mensaje": (
            f"La orden N.º {orden.id:06d} "
            "fue actualizada correctamente."
        ),
        "orden": {
            "id": orden.id,
            "numero_cupon": orden.numero_cupon,
            "fecha_ejecucion": (
                orden.fecha_ejecucion.isoformat()
            ),
            "fecha_ejecucion_display": (
                orden.fecha_ejecucion.strftime(
                    "%d/%m/%Y"
                )
            ),
        },
    })

# =============================================================================
# EDITAR PLANILLA
# =============================================================================
#
# Solo se puede modificar una planilla en estado BORRADOR.
#
# Editar significa:
#
#   - agregar DetallePlanillaEntrega
#   - quitar DetallePlanillaEntrega
#   - modificar observaciones
#
# Los datos propios de una OrdenAutorizacion:
#
#   - numero_cupon
#   - fecha_ejecucion
#
# se modifican mediante editar_datos_orden_planilla_ajax.
#
# NO significa:
#
#   - entregar una orden
#   - modificar fecha_entrega
#   - modificar user_entrega
#   - modificar esta_entregada
#
# =============================================================================

@login_required
def editar_planilla_entrega(request, planilla_id):

    planilla = get_object_or_404(
        PlanillaEntrega.objects.select_related(
            "medico",
        ),
        id=planilla_id,
        is_deleted=False,
    )

    # =========================================================================
    # SOLO BORRADOR
    # =========================================================================

    if planilla.estado != "borrador":

        messages.error(
            request,
            (
                "Solo se pueden modificar las órdenes "
                "de una planilla en estado borrador."
            ),
        )

        return redirect(
            "gestion_app:detalle_planilla_entrega",
            planilla_id=planilla.id,
        )

    # =========================================================================
    # ÓRDENES ACTUALES
    # =========================================================================

    ordenes_actuales_ids = set(
        DetallePlanillaEntrega.objects
        .filter(
            planilla_entrega=planilla,
        )
        .values_list(
            "orden_id",
            flat=True,
        )
    )

    # =========================================================================
    # ÓRDENES OCUPADAS POR OTRAS PLANILLAS
    # =========================================================================

    ordenes_otras_planillas_ids = set(
        DetallePlanillaEntrega.objects
        .filter(
            planilla_entrega__is_deleted=False,
        )
        .exclude(
            planilla_entrega=planilla,
        )
        .exclude(
            planilla_entrega__estado="anulada",
        )
        .values_list(
            "orden_id",
            flat=True,
        )
    )

    # =========================================================================
    # ÓRDENES DISPONIBLES
    # =========================================================================

    ordenes = (
        OrdenAutorizacion.objects
        .select_related(
            "preingreso",
            "preingreso__paciente",
            "preingreso__obra_social",
            "preingreso__plan",
            "medico",
            "medico_tenencia",
        )
        .prefetch_related(
            "detalles",
            "detalles__prestacion",
        )
        .filter(
            deleted_at__isnull=True,
            medico_tenencia_id=planilla.medico_id,
            autorizada=True,
            estado="autorizada",
            esta_entregada=False,
        )
        .exclude(
            id__in=ordenes_otras_planillas_ids,
        )
        .order_by(
            "fecha",
            "id",
        )
    )

    ordenes = list(ordenes)

    # =========================================================================
    # PREPARAR DATOS PARA EL FRONT
    # =========================================================================

    for orden in ordenes:

        # ---------------------------------------------------------------------
        # SELECCIONADA ACTUALMENTE
        # ---------------------------------------------------------------------

        orden.seleccionada = (
            orden.id in ordenes_actuales_ids
        )

        # ---------------------------------------------------------------------
        # DETALLES VÁLIDOS
        # ---------------------------------------------------------------------

        detalles_validos = [
            detalle
            for detalle in orden.detalles.all()
            if getattr(
                detalle,
                "deleted_at",
                None,
            ) is None
        ]

        # ---------------------------------------------------------------------
        # FECHA DE EJECUCIÓN
        # ---------------------------------------------------------------------

        fechas_detalles = [
            detalle.fecha_desde
            for detalle in detalles_validos
            if detalle.fecha_desde
        ]

        if getattr(
            orden,
            "fecha_ejecucion",
            None,
        ):

            orden.fecha_ejecucion_mostrar = (
                orden.fecha_ejecucion
            )

        elif fechas_detalles:

            orden.fecha_ejecucion_mostrar = min(
                fechas_detalles
            )

        else:

            orden.fecha_ejecucion_mostrar = (
                orden.fecha
            )

        # ---------------------------------------------------------------------
        # CÓDIGOS DE PRESTACIONES
        # ---------------------------------------------------------------------

        codigos = []

        for detalle in detalles_validos:

            prestacion = getattr(
                detalle,
                "prestacion",
                None,
            )

            codigo = getattr(
                prestacion,
                "codigo",
                None,
            )

            if not codigo:
                continue

            codigo = str(
                codigo
            ).strip()

            if (
                codigo
                and codigo not in codigos
            ):
                codigos.append(
                    codigo
                )

        orden.codigos_prestaciones = codigos

    # =========================================================================
    # POST - GUARDAR COMPOSICIÓN DE PLANILLA
    # =========================================================================

    if request.method == "POST":

        ordenes_post = request.POST.getlist(
            "ordenes"
        )

        observaciones = request.POST.get(
            "observaciones",
            "",
        ).strip()

        # ---------------------------------------------------------------------
        # CONVERTIR IDS
        # ---------------------------------------------------------------------

        try:

            seleccionadas_ids = {
                int(orden_id)
                for orden_id in ordenes_post
            }

        except (TypeError, ValueError):

            messages.error(
                request,
                "La selección contiene órdenes inválidas.",
            )

            return redirect(
                "gestion_app:editar_planilla_entrega",
                planilla_id=planilla.id,
            )

        # ---------------------------------------------------------------------
        # NO DEJAR PLANILLA VACÍA
        # ---------------------------------------------------------------------

        if not seleccionadas_ids:

            messages.error(
                request,
                "La planilla debe contener al menos una orden.",
            )

            return redirect(
                "gestion_app:editar_planilla_entrega",
                planilla_id=planilla.id,
            )

        # =========================================================================
        # TRANSACCIÓN
        # =========================================================================

        with transaction.atomic():

            # -----------------------------------------------------------------
            # BLOQUEAR PLANILLA
            # -----------------------------------------------------------------

            planilla = (
                PlanillaEntrega.objects
                .select_for_update()
                .select_related(
                    "medico"
                )
                .get(
                    id=planilla_id,
                    is_deleted=False,
                )
            )

            # -----------------------------------------------------------------
            # REVALIDAR ESTADO
            # -----------------------------------------------------------------

            if planilla.estado != "borrador":

                messages.error(
                    request,
                    (
                        "La planilla dejó de estar en borrador "
                        "y ya no puede modificarse."
                    ),
                )

                return redirect(
                    "gestion_app:detalle_planilla_entrega",
                    planilla_id=planilla.id,
                )

            # -----------------------------------------------------------------
            # BLOQUEAR DETALLES ACTUALES
            # -----------------------------------------------------------------

            detalles_actuales = list(
                DetallePlanillaEntrega.objects
                .select_for_update()
                .filter(
                    planilla_entrega=planilla,
                )
            )

            actuales_ids = {
                detalle.orden_id
                for detalle in detalles_actuales
            }

            # -----------------------------------------------------------------
            # BLOQUEAR ÓRDENES SELECCIONADAS
            # -----------------------------------------------------------------

            ordenes_seleccionadas = list(
                OrdenAutorizacion.objects
                .select_for_update()
                .filter(
                    id__in=seleccionadas_ids,
                    deleted_at__isnull=True,
                    medico_tenencia_id=planilla.medico_id,
                    autorizada=True,
                    estado="autorizada",
                    esta_entregada=False,
                )
            )

            encontrados_ids = {
                orden.id
                for orden in ordenes_seleccionadas
            }

            if encontrados_ids != seleccionadas_ids:

                messages.error(
                    request,
                    (
                        "Una o más órdenes seleccionadas "
                        "ya no se encuentran disponibles."
                    ),
                )

                return redirect(
                    "gestion_app:editar_planilla_entrega",
                    planilla_id=planilla.id,
                )

            # -----------------------------------------------------------------
            # VERIFICAR OTRAS PLANILLAS
            # -----------------------------------------------------------------

            usadas_en_otras = set(
                DetallePlanillaEntrega.objects
                .filter(
                    orden_id__in=seleccionadas_ids,
                    planilla_entrega__is_deleted=False,
                )
                .exclude(
                    planilla_entrega=planilla,
                )
                .exclude(
                    planilla_entrega__estado="anulada",
                )
                .values_list(
                    "orden_id",
                    flat=True,
                )
            )

            if usadas_en_otras:

                messages.error(
                    request,
                    (
                        "Una o más órdenes seleccionadas "
                        "ya pertenecen a otra planilla."
                    ),
                )

                return redirect(
                    "gestion_app:editar_planilla_entrega",
                    planilla_id=planilla.id,
                )

            # -----------------------------------------------------------------
            # CALCULAR DIFERENCIAS
            # -----------------------------------------------------------------

            quitar_ids = (
                actuales_ids
                - seleccionadas_ids
            )

            agregar_ids = (
                seleccionadas_ids
                - actuales_ids
            )

            # =================================================================
            # QUITAR
            # =================================================================

            if quitar_ids:

                DetallePlanillaEntrega.objects.filter(
                    planilla_entrega=planilla,
                    orden_id__in=quitar_ids,
                ).delete()

            # =================================================================
            # AGREGAR
            # =================================================================

            if agregar_ids:

                nuevos_detalles = [
                    DetallePlanillaEntrega(
                        planilla_entrega=planilla,
                        orden=orden,
                        user_made=request.user,
                    )
                    for orden in ordenes_seleccionadas
                    if orden.id in agregar_ids
                ]

                DetallePlanillaEntrega.objects.bulk_create(
                    nuevos_detalles
                )

            # -----------------------------------------------------------------
            # PLANILLA
            # -----------------------------------------------------------------

            planilla.observaciones = observaciones
            planilla.user_updated = request.user

            planilla.save(
                update_fields=[
                    "observaciones",
                    "user_updated",
                ]
            )

            # -----------------------------------------------------------------
            # IMPORTANTE
            #
            # NO se toca OrdenAutorizacion.esta_entregada.
            #
            # Las modificaciones de:
            #
            # - numero_cupon
            # - fecha_ejecucion
            #
            # se realizan por editar_datos_orden_planilla_ajax.
            # -----------------------------------------------------------------

        # =========================================================================
        # RESULTADO
        # =========================================================================

        messages.success(
            request,
            (
                "Planilla actualizada correctamente. "
                f"Se agregaron {len(agregar_ids)} orden(es) "
                f"y se quitaron {len(quitar_ids)} orden(es)."
            ),
        )

        return redirect(
            "gestion_app:detalle_planilla_entrega",
            planilla_id=planilla.id,
        )

    # =========================================================================
    # GET
    # =========================================================================

    context = {
        "planilla": planilla,
        "ordenes": ordenes,
        "total_actual": len(
            ordenes_actuales_ids
        ),
    }

    return render(
        request,
        "gestion/entregas/editar_planilla_entrega.html",
        context,
    )