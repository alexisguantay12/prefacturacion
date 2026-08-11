from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from applications.entidades.models import *
from ..models import *
from .ordenes import redirigir_segun_origen


# =============================================================================
# ACCIONES SOBRE ÓRDENES
# =============================================================================

@require_POST

def autorizar_orden(request, orden_id):
    orden = get_object_or_404(OrdenAutorizacion, id=orden_id)

    if orden.estado == "anulada":
        messages.error(request, "No se puede autorizar una orden anulada.")
        return redirigir_segun_origen(request, orden)

    orden.autorizada = True
    orden.estado = "autorizada"
    orden.save()

    orden.fecha_autorizacion= timezone.now()
    orden.user_autorizacion= request.user
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

    orden.user_anulacion= request.user
    orden.fecha_anulacion=timezone.now()
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

    orden.user_tenencia=request.user
    orden.fecha_tenencia=timezone.now()

    orden.medico_tenencia = medico
    orden.save()

    messages.success(request, "Tenencia actualizada correctamente.")
    return redirigir_segun_origen(request, orden)




import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from applications.entidades.models import Medico, Prestacion
from applications.gestion.models import (
    DetalleOrden,
    HistoricoOrden,
    OrdenAutorizacion,
) 

def _fecha_orden_como_date(orden):
    fecha_orden = orden.fecha

    if not fecha_orden:
        return None

    if isinstance(fecha_orden, date) and not hasattr(fecha_orden, "hour"):
        return fecha_orden

    return fecha_orden


def _permisos_edicion_orden(orden):
    """
    Día 0 a 14 inclusive:
        médico, observaciones y detalles.

    Día 15 a 45 inclusive:
        médico y observaciones.

    Día 46 en adelante:
        sin edición.

    Orden anulada:
        sin edición.
    """
    fecha_orden = _fecha_orden_como_date(orden)

    if not fecha_orden:
        return {
            "dias_transcurridos": None,
            "puede_editar": False,
            "puede_editar_codigos": False,
            "motivo_bloqueo": "La orden no tiene una fecha válida.",
        }

    dias_transcurridos = (date.today() - fecha_orden).days

    if dias_transcurridos < 0:
        return {
            "dias_transcurridos": dias_transcurridos,
            "puede_editar": False,
            "puede_editar_codigos": False,
            "motivo_bloqueo": "La fecha de la orden es posterior a la fecha actual.",
        }

    if orden.estado == "anulada":
        return {
            "dias_transcurridos": dias_transcurridos,
            "puede_editar": False,
            "puede_editar_codigos": False,
            "motivo_bloqueo": "Las órdenes anuladas no pueden editarse.",
        }
    if orden.esta_entregada:
            return {
                "dias_transcurridos": dias_transcurridos,
                "puede_editar": False,
                "puede_editar_codigos": False,
                "motivo_bloqueo": "Las órdenes entregadas no pueden editarse",
            }
    puede_editar = dias_transcurridos <= 45

    # Regla segura: si está autorizada, no se cambian códigos aunque tenga <= 14 días.
    puede_editar_codigos = (
        puede_editar
        and dias_transcurridos <= 14
        and not orden.autorizada
    )

    motivo_bloqueo = ""

    if not puede_editar:
        motivo_bloqueo = "El plazo de edición de 45 días ya venció."
    elif orden.autorizada:
        motivo_bloqueo = (
            "La orden está autorizada. Solo pueden modificarse el médico "
            "y las observaciones."
        )
    elif dias_transcurridos > 14:
        motivo_bloqueo = (
            "El plazo de 14 días para modificar prestaciones ya venció."
        )

    return {
        "dias_transcurridos": dias_transcurridos,
        "puede_editar": puede_editar,
        "puede_editar_codigos": puede_editar_codigos,
        "motivo_bloqueo": motivo_bloqueo,
    }


def _normalizar_detalle_json(item):
    return {
        "prestacion_id": str(item.get("prestacion_id") or "").strip(),
        "cantidad": int(item.get("cantidad") or 1),
        "honorarios_gastos": (
            str(item.get("honorarios_gastos") or "").strip() or None
        ),
        "tipo_honorario": (
            str(item.get("tipo_honorario") or "").strip() or None
        ),
        "fecha_desde": (
            str(item.get("fecha_desde") or "").strip() or None
        ),
        "fecha_hasta": (
            str(item.get("fecha_hasta") or "").strip() or None
        ),
        "observaciones": (
            str(item.get("observaciones") or "").strip() or None
        ),
    }


def _detalle_actual_normalizado(detalle):
    return {
        "prestacion_id": str(detalle.prestacion_id or ""),
        "cantidad": int(detalle.cantidad or 1),
        "honorarios_gastos": detalle.honorarios_gastos or None,
        "tipo_honorario": detalle.tipo_honorario or None,
        "fecha_desde": (
            detalle.fecha_desde.isoformat()
            if detalle.fecha_desde else None
        ),
        "fecha_hasta": (
            detalle.fecha_hasta.isoformat()
            if detalle.fecha_hasta else None
        ),
        "observaciones": detalle.observaciones or None,
    }


@login_required
def editar_orden_ingreso(request, orden_id):
    orden = get_object_or_404(
        OrdenAutorizacion.objects
        .select_related(
            "preingreso",
            "preingreso__paciente",
            "preingreso__obra_social",
            "preingreso__plan",
            "preingreso__medico",
            "preingreso__servicio",
            "medico",
            "medico_tenencia",
        )
        .prefetch_related(
            "detalles",
            "detalles__prestacion",
        ),
        id=orden_id,
    )

    preingreso = orden.preingreso
    permisos = _permisos_edicion_orden(orden)

    if not permisos["puede_editar"]:
        messages.error(request, permisos["motivo_bloqueo"])
        if orden.preingreso.estado=='pendiente':
            return redirect(
                "gestion_app:detalle_preingreso",
                preingreso_id=preingreso.id,
            )
        else:
            return redirect(
                "gestion_app:detalle_ingreso",
                preingreso_id=preingreso.id,
            )

    medicos = Medico.objects.all().order_by("apellido", "nombre")

    if request.method == "POST":
        medico_id = request.POST.get("medico") or None
        observaciones = request.POST.get("observaciones", "").strip()
        detalles_json = request.POST.get("detalles_json", "[]")

        if not medico_id:
            messages.error(request, "Debe seleccionar el médico de la orden.")
            return redirect(
                "gestion_app:editar_orden_ingreso",
                orden_id=orden.id,
            )

        medico = Medico.objects.filter(id=medico_id).first()

        if not medico:
            messages.error(request, "El médico seleccionado no es válido.")
            return redirect(
                "gestion_app:editar_orden_ingreso",
                orden_id=orden.id,
            )

        detalles_nuevos = []

        if permisos["puede_editar_codigos"]:
            try:
                detalles_recibidos = json.loads(detalles_json)
            except json.JSONDecodeError:
                detalles_recibidos = []

            if not isinstance(detalles_recibidos, list):
                detalles_recibidos = []

            if not detalles_recibidos:
                messages.error(
                    request,
                    "Debe conservar al menos un detalle en la orden.",
                )
                return redirect(
                    "gestion_app:editar_orden_ingreso",
                    orden_id=orden.id,
                )

            try:
                detalles_nuevos = [
                    _normalizar_detalle_json(item)
                    for item in detalles_recibidos
                ]
            except (TypeError, ValueError):
                messages.error(
                    request,
                    "Hay valores inválidos en los detalles de la orden.",
                )
                return redirect(
                    "gestion_app:editar_orden_ingreso",
                    orden_id=orden.id,
                )

            if any(
                not item["prestacion_id"]
                or item["cantidad"] <= 0
                for item in detalles_nuevos
            ):
                messages.error(
                    request,
                    "Todos los detalles deben tener una prestación válida "
                    "y una cantidad mayor a cero.",
                )
                return redirect(
                    "gestion_app:editar_orden_ingreso",
                    orden_id=orden.id,
                )

            prestaciones_ids = {
                int(item["prestacion_id"])
                for item in detalles_nuevos
            }

            prestaciones = {
                prestacion.id: prestacion
                for prestacion in Prestacion.objects.filter(
                    id__in=prestaciones_ids
                )
            }

            if len(prestaciones) != len(prestaciones_ids):
                messages.error(
                    request,
                    "Una o más prestaciones seleccionadas no existen.",
                )
                return redirect(
                    "gestion_app:editar_orden_ingreso",
                    orden_id=orden.id,
                )

        detalles_actuales = list(
            orden.detalles.all().order_by("id")
        )

        cambio_medico = orden.medico_id != medico.id
        cambio_observaciones = (
            (orden.observaciones or "") != observaciones
        )

        cambio_detalles = False

        if permisos["puede_editar_codigos"]:
            actuales_normalizados = sorted(
                (
                    _detalle_actual_normalizado(detalle)
                    for detalle in detalles_actuales
                ),
                key=lambda item: (
                    item["prestacion_id"],
                    item["cantidad"],
                    item["honorarios_gastos"] or "",
                    item["tipo_honorario"] or "",
                    item["fecha_desde"] or "",
                    item["fecha_hasta"] or "",
                    item["observaciones"] or "",
                ),
            )

            nuevos_normalizados = sorted(
                detalles_nuevos,
                key=lambda item: (
                    item["prestacion_id"],
                    item["cantidad"],
                    item["honorarios_gastos"] or "",
                    item["tipo_honorario"] or "",
                    item["fecha_desde"] or "",
                    item["fecha_hasta"] or "",
                    item["observaciones"] or "",
                ),
            )

            cambio_detalles = (
                actuales_normalizados != nuevos_normalizados
            )

        if not (
            cambio_medico
            or cambio_observaciones
            or cambio_detalles
        ):
            messages.info(
                request,
                "No se detectaron cambios en la orden.",
            )
            if orden.preingreso.estado =='pendiente':
                return redirect(
                    "gestion_app:detalle_preingreso",
                    preingreso_id=preingreso.id,
                )
            else: 
                return redirect(
                    "gestion_app:detalle_ingreso",
                    preingreso_id=preingreso.id,
                )
        try:
            with transaction.atomic():
                orden_bloqueada = (
                    OrdenAutorizacion.objects
                    .select_for_update()
                    .get(id=orden.id)
                )

                # Guardar una copia del estado anterior.
                crear_historico_orden(
                    orden=orden_bloqueada,
                    usuario=request.user,
                    motivo="edicion",
                )

                orden_bloqueada.medico = medico
                orden_bloqueada.observaciones = observaciones or None
                orden_bloqueada.user_updated = request.user
                if not orden_bloqueada.autorizada:
                    orden_bloqueada.medico_tenencia = medico

                orden_bloqueada.save(
                    update_fields=[
                        "medico",
                        "medico_tenencia",
                        "observaciones",
                        "user_updated",
                        "updated_at",
                    ]
                )

                if permisos["puede_editar_codigos"]:
                    orden_bloqueada.detalles.all().delete()

                    nuevos_objetos = []

                    for item in detalles_nuevos:
                        prestacion_id = int(item["prestacion_id"])

                        nuevos_objetos.append(
                            DetalleOrden(
                                orden=orden_bloqueada,
                                prestacion=prestaciones[prestacion_id],
                                medico=medico,
                                cantidad=item["cantidad"],
                                honorarios_gastos=item["honorarios_gastos"],
                                tipo_honorario=item["tipo_honorario"],
                                fecha_desde=item["fecha_desde"],
                                fecha_hasta=item["fecha_hasta"],
                                observaciones=item["observaciones"],
                            )
                        )

                    DetalleOrden.objects.bulk_create(nuevos_objetos)
            messages.success(
                request,
                "La orden fue actualizada correctamente.",
            )
            if orden.preingreso.estado=='pendiente':
                return redirect(
                    "gestion_app:detalle_preingreso",
                    orden.preingreso.id,
                )
            else:
                return redirect(
                    "gestion_app:detalle_ingreso",
                    orden.preingreso.id,
                )

        except Exception as exc:
            messages.error(
                request,
                f"Ocurrió un error al actualizar la orden: {exc}",
            )
            return redirect(
                "gestion_app:editar_orden_ingreso",
                orden_id=orden.id,
            )

    detalles_iniciales = []

    for detalle in orden.detalles.all().order_by("id"):
        detalles_iniciales.append({
            "prestacion_id": detalle.prestacion_id,
            "prestacion_codigo": (
                detalle.prestacion.codigo
                if detalle.prestacion else ""
            ),
            "prestacion_nombre": (
                detalle.prestacion.nombre
                if detalle.prestacion else ""
            ),
            "cantidad": detalle.cantidad or 1,
            "honorarios_gastos": detalle.honorarios_gastos or "",
            "tipo_honorario": detalle.tipo_honorario or "",
            "fecha_desde": (
                detalle.fecha_desde.isoformat()
                if detalle.fecha_desde else ""
            ),
            "fecha_hasta": (
                detalle.fecha_hasta.isoformat()
                if detalle.fecha_hasta else ""
            ),
            "observaciones": detalle.observaciones or "",
        })

    return render(
        request,
        "gestion/orden/editar_orden.html",
        {
            "orden": orden,
            "preingreso": preingreso,
            "medicos": medicos,
            "detalles_iniciales": detalles_iniciales,
            "puede_editar_codigos": permisos["puede_editar_codigos"],
            "dias_transcurridos": permisos["dias_transcurridos"],
            "motivo_bloqueo_codigos": permisos["motivo_bloqueo"],
            "honorarios_gastos": DetalleOrden.HONORARIOS_GASTOS,
            "tipos_honorario": DetalleOrden.TIPOS_HONORARIO,
        },
    )


def crear_historico_orden(orden, usuario, motivo="edición"):
     
    historico = HistoricoOrden.objects.create(
        orden=orden, 
        medico=orden.medico, 
        observaciones=orden.observaciones,
        usuario=usuario,
        motivo=motivo, 
    )

    detalles = []
    for detalle in orden.detalles.all():
        print(orden.detalles.all())
        detalles.append(
            HistoricoDetalleOrden(
                historico_orden=historico,
                prestacion_codigo=detalle.prestacion.codigo,
                prestacion_nombre=detalle.prestacion.nombre, 
                cantidad=detalle.cantidad,
                honorarios_gastos=detalle.honorarios_gastos,
                tipo_honorario=detalle.tipo_honorario,
                fecha_desde=detalle.fecha_desde,
                fecha_hasta=detalle.fecha_hasta,
                observaciones=detalle.observaciones,
            )
        )

    HistoricoDetalleOrden.objects.bulk_create(detalles)

    return historico

@require_GET
@login_required
def historial_orden_ajax(request, orden_id):
    orden = get_object_or_404(
        OrdenAutorizacion.objects.select_related(
            "medico",
            "preingreso",
        ),
        id=orden_id,
    )

    historiales = (
        HistoricoOrden.objects
        .filter(orden=orden)
        .select_related(
            "usuario",
            "medico",
        )
        .prefetch_related("detalles")
        .order_by("-fecha_actualizacion")
    )

    versiones = []

    for historial in historiales:
        medico_nombre = None

        if historial.medico:
            medico_nombre = (
                f"{historial.medico.apellido}, "
                f"{historial.medico.nombre}"
            )

        versiones.append({
            "id": historial.id, 
            "fecha_actualizacion": timezone.now(),
            "usuario": (
                historial.usuario.get_full_name()
                or historial.usuario.username
                if historial.usuario else "Usuario no disponible"
            ),
            "motivo": historial.get_motivo_display(),
            "medico": medico_nombre or "Sin médico",
            "observaciones": historial.observaciones or "",
            "detalles": [
                {
                    "codigo": detalle.prestacion_codigo or "-",
                    "nombre": detalle.prestacion_nombre or "-",
                    "cantidad": detalle.cantidad,
                    "honorarios_gastos": detalle.honorarios_gastos or "-",
                    "tipo_honorario": detalle.tipo_honorario or "-",
                    "fecha_desde": (
                        detalle.fecha_desde.strftime("%d/%m/%Y")
                        if detalle.fecha_desde else "-"
                    ),
                    "fecha_hasta": (
                        detalle.fecha_hasta.strftime("%d/%m/%Y")
                        if detalle.fecha_hasta else "-"
                    ),
                    "observaciones": detalle.observaciones or "",
                }
                for detalle in historial.detalles.all()
            ],
        })

    return JsonResponse({
        "ok": True,
        "orden_id": orden.id,
        "versiones": versiones,
    })


