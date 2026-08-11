from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from applications.entidades.models import Medico

from applications.gestion.models import (
    Preingreso,
    OrdenAutorizacion,
    DetalleOrden,
    ProcedimientoProgramado,
    PlantillaOrdenProcedimiento,
)


# =========================================================
# LISTAR PROCEDIMIENTOS DISPONIBLES PARA PREINGRESO
# AJAX
# =========================================================

@login_required
@require_GET
def procedimientos_preingreso_ajax(request, preingreso_id):

    preingreso = get_object_or_404(
        Preingreso,
        id=preingreso_id
    )

    # Solo permitimos generación automática si todavía
    # no existen órdenes asociadas.
    if preingreso.ordenes.exists():

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Este preingreso ya posee órdenes asociadas. "
                    "No se puede generar un procedimiento automático."
                )
            },
            status=409
        )

    procedimientos = (
        ProcedimientoProgramado.objects
        .filter(
            activo=True,
            ordenes_plantilla__activo=True
        )
        .distinct()
        .order_by("nombre")
    )

    resultado = []

    for procedimiento in procedimientos:

        plantillas = (
            procedimiento
            .ordenes_plantilla
            .filter(activo=True)
            .prefetch_related(
                "detalles__prestacion"
            )
            .order_by(
                "orden",
                "id"
            )
        )

        plantillas_json = []
        total_detalles = 0

        for plantilla in plantillas:

            detalles_activos = [
                detalle
                for detalle in plantilla.detalles.all()
                if detalle.activo
            ]

            # No mostramos plantillas vacías.
            if not detalles_activos:
                continue

            total_detalles += len(detalles_activos)

            plantillas_json.append(
                {
                    "id": plantilla.id,
                    "nombre": plantilla.nombre,
                    "observaciones": (
                        plantilla.observaciones or ""
                    ),
                    "orden": plantilla.orden,
                    "cantidad_detalles": len(
                        detalles_activos
                    ),
                }
            )

        # Si el procedimiento no tiene ninguna plantilla útil,
        # tampoco lo mostramos.
        if not plantillas_json:
            continue

        resultado.append(
            {
                "id": procedimiento.id,
                "nombre": procedimiento.nombre,
                "descripcion": (
                    procedimiento.descripcion or ""
                ),
                "cantidad_ordenes": len(
                    plantillas_json
                ),
                "cantidad_detalles": total_detalles,
                "plantillas": plantillas_json,
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "procedimientos": resultado,
        }
    )


# =========================================================
# GENERAR ÓRDENES DESDE PROCEDIMIENTO
# AJAX
# =========================================================

@login_required
@require_POST
def generar_ordenes_procedimiento_ajax(
    request,
    preingreso_id
):

    preingreso = get_object_or_404(
        Preingreso,
        id=preingreso_id
    )

    procedimiento_id = request.POST.get(
        "procedimiento_id",
        ""
    ).strip()

    fecha_desde_raw = request.POST.get(
        "fecha_desde",
        ""
    ).strip()

    fecha_hasta_raw = request.POST.get(
        "fecha_hasta",
        ""
    ).strip()

    # =====================================================
    # VALIDACIONES
    # =====================================================

    if not procedimiento_id:

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Debe seleccionar un procedimiento."
                )
            },
            status=400
        )

    if not fecha_desde_raw or not fecha_hasta_raw:

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Debe completar la fecha desde "
                    "y la fecha hasta."
                )
            },
            status=400
        )

    try:

        fecha_desde = datetime.strptime(
            fecha_desde_raw,
            "%Y-%m-%d"
        ).date()

        fecha_hasta = datetime.strptime(
            fecha_hasta_raw,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Las fechas ingresadas no son válidas."
                )
            },
            status=400
        )

    if fecha_desde > fecha_hasta:

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "La fecha desde no puede ser posterior "
                    "a la fecha hasta."
                )
            },
            status=400
        )

    procedimiento = get_object_or_404(
        ProcedimientoProgramado,
        id=procedimiento_id,
        activo=True
    )

    # =====================================================
    # MÉDICO SANTA CLARA - MATRÍCULA 9063
    # =====================================================

    medico_santa_clara = (
        Medico.objects
        .filter(
            matricula__iexact="9063"
        )
        .first()
    )

    if not medico_santa_clara:

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No se encontró el médico Santa Clara "
                    "con matrícula 9063. "
                    "No se generó ninguna orden."
                )
            },
            status=409
        )

    # =====================================================
    # PLANTILLAS DEL PROCEDIMIENTO
    # =====================================================

    plantillas = list(
        PlantillaOrdenProcedimiento.objects
        .filter(
            procedimiento=procedimiento,
            activo=True
        )
        .prefetch_related(
            "detalles__prestacion"
        )
        .order_by(
            "orden",
            "id"
        )
    )

    if not plantillas:

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El procedimiento seleccionado "
                    "no posee plantillas activas."
                )
            },
            status=400
        )

    cantidad_ordenes = 0
    cantidad_detalles = 0

    try:

        with transaction.atomic():

            # Bloqueamos el preingreso para evitar
            # doble generación por doble click.
            preingreso_bloqueado = (
                Preingreso.objects
                .select_for_update()
                .get(
                    id=preingreso.id
                )
            )

            if preingreso_bloqueado.ordenes.exists():

                return JsonResponse(
                    {
                        "ok": False,
                        "error": (
                            "El preingreso ya posee órdenes "
                            "asociadas. No se generó ninguna "
                            "orden adicional."
                        )
                    },
                    status=409
                )

            hoy = datetime.today()

            # =================================================
            # GENERAR UNA ORDEN POR CADA PLANTILLA
            # =================================================

            for plantilla in plantillas:

                detalles_plantilla = [
                    detalle
                    for detalle in plantilla.detalles.all()
                    if detalle.activo
                ]

                # No crear una orden sin detalles.
                if not detalles_plantilla:
                    continue

                orden = OrdenAutorizacion.objects.create(
                    preingreso=preingreso_bloqueado,

                    tipo="practica",

                    fecha=hoy,

                    medico=medico_santa_clara,

                    observaciones=(
                        plantilla.observaciones
                        or (
                            f"{procedimiento.nombre} - "
                            f"{plantilla.nombre}"
                        )
                    ),

                    estado="pendiente",

                    user_made=request.user,
                )

                cantidad_ordenes += 1

                detalles_a_crear = []

                for plantilla_detalle in detalles_plantilla:

                    detalles_a_crear.append(
                        DetalleOrden(
                            orden=orden,

                            prestacion=(
                                plantilla_detalle.prestacion
                            ),

                            cantidad=(
                                plantilla_detalle.cantidad
                            ),

                            honorarios_gastos=(
                                plantilla_detalle.honorarios_gastos
                            ),

                            tipo_honorario=(
                                plantilla_detalle.tipo_honorario
                            ),

                            fecha_desde=fecha_desde,
                            fecha_hasta=fecha_hasta,

                            user_made=request.user,
                        )
                    )

                DetalleOrden.objects.bulk_create(
                    detalles_a_crear
                )

                cantidad_detalles += len(
                    detalles_a_crear
                )

            if cantidad_ordenes == 0:

                raise ValueError(
                    (
                        "Las plantillas activas del "
                        "procedimiento no poseen "
                        "prestaciones activas."
                    )
                )

    except ValueError as e:

        return JsonResponse(
            {
                "ok": False,
                "error": str(e)
            },
            status=400
        )

    except Exception:

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Ocurrió un error al generar las órdenes. "
                    "No se realizó ningún cambio."
                )
            },
            status=500
        )

    return JsonResponse(
        {
            "ok": True,

            "mensaje": (
                f'Se generaron {cantidad_ordenes} '
                f'órdenes para "{procedimiento.nombre}".'
            ),

            "procedimiento": procedimiento.nombre,

            "ordenes_creadas": cantidad_ordenes,

            "detalles_creados": cantidad_detalles,
        }
    )