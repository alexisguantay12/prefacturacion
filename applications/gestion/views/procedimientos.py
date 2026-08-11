from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
 
from applications.entidades.models import *
from applications.gestion.models import *

# =========================================================
# PROCEDIMIENTOS
# =========================================================

@login_required
def lista_procedimientos(request):
    procedimientos = (
        ProcedimientoProgramado.objects
        .annotate(
            total_plantillas=Count(
                "ordenes_plantilla",
                distinct=True
            )
        )
        .order_by("nombre")
    )

    return render(
        request,
        "gestion/procedimientos/lista_procedimientos.html",
        {
            "procedimientos": procedimientos,
        }
    )


@login_required
def crear_procedimiento(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()
        activo = request.POST.get("activo") == "on"

        if not nombre:
            messages.error(
                request,
                "Debe ingresar el nombre del procedimiento."
            )

            return render(
                request,
                "gestion/procedimientos/crear_procedimiento.html",
                {
                    "nombre": nombre,
                    "descripcion": descripcion,
                    "activo": activo,
                }
            )

        procedimiento = ProcedimientoProgramado.objects.create(
            nombre=nombre,
            descripcion=descripcion or None,
            activo=activo,
            user_made=request.user,
        )

        messages.success(
            request,
            f'El procedimiento "{procedimiento.nombre}" fue creado correctamente.'
        )

        return redirect(
            "gestion_app:detalle_procedimiento",
            procedimiento.id
        )

    return render(
        request,
        "gestion/procedimientos/crear_procedimiento.html"
    )


@login_required
def detalle_procedimiento(request, procedimiento_id):
    procedimiento = get_object_or_404(
        ProcedimientoProgramado,
        id=procedimiento_id
    )

    plantillas = (
        PlantillaOrdenProcedimiento.objects
        .filter(
            procedimiento=procedimiento
        )
        .annotate(
            total_detalles=Count(
                "detalles",
                distinct=True
            )
        )
        .order_by(
            "orden",
            "id"
        )
    )

    return render(
        request,
        "gestion/procedimientos/detalle_procedimiento.html",
        {
            "procedimiento": procedimiento,
            "plantillas": plantillas,
        }
    )


@login_required
def editar_procedimiento(request, procedimiento_id):
    procedimiento = get_object_or_404(
        ProcedimientoProgramado,
        id=procedimiento_id
    )

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()
        activo = request.POST.get("activo") == "on"

        if not nombre:
            messages.error(
                request,
                "Debe ingresar el nombre del procedimiento."
            )

            return render(
                request,
                "gestion/procedimientos/editar_procedimiento.html",
                {
                    "procedimiento": procedimiento,
                }
            )

        procedimiento.nombre = nombre
        procedimiento.descripcion = descripcion or None
        procedimiento.activo = activo

        if hasattr(procedimiento, "user_modified"):
            procedimiento.user_modified = request.user

        procedimiento.save()

        messages.success(
            request,
            "El procedimiento fue actualizado correctamente."
        )

        return redirect(
            "gestion_app:detalle_procedimiento",
            procedimiento.id
        )

    return render(
        request,
        "gestion/procedimientos/editar_procedimiento.html",
        {
            "procedimiento": procedimiento,
        }
    )


@login_required
def eliminar_procedimiento(request, procedimiento_id):
    procedimiento = get_object_or_404(
        ProcedimientoProgramado,
        id=procedimiento_id
    )

    total_plantillas = procedimiento.ordenes_plantilla.count()

    if request.method == "POST":
        nombre = procedimiento.nombre

        procedimiento.delete()

        messages.success(
            request,
            f'El procedimiento "{nombre}" fue eliminado correctamente.'
        )

        return redirect(
            "gestion_app:lista_procedimientos"
        )

    return render(
        request,
        "gestion/procedimientos/eliminar_procedimiento.html",
        {
            "procedimiento": procedimiento,
            "total_plantillas": total_plantillas,
        }
    )


# =========================================================
# PLANTILLAS DE ÓRDENES
# =========================================================

@login_required
def crear_plantilla(request, procedimiento_id):
    procedimiento = get_object_or_404(
        ProcedimientoProgramado,
        id=procedimiento_id
    )

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()
        orden = request.POST.get("orden", "").strip()
        activo = request.POST.get("activo") == "on"

        if not nombre:
            messages.error(
                request,
                "Debe ingresar el nombre de la plantilla."
            )

            return render(
                request,
                "gestion/procedimientos/crear_plantilla.html",
                {
                    "procedimiento": procedimiento,
                    "nombre": nombre,
                    "observaciones": observaciones,
                    "orden": orden,
                    "activo": activo,
                }
            )

        try:
            orden = int(orden)

            if orden < 1:
                orden = 1

        except (TypeError, ValueError):
            orden = procedimiento.ordenes_plantilla.count() + 1

        plantilla = PlantillaOrdenProcedimiento.objects.create(
            procedimiento=procedimiento,
            nombre=nombre,
            observaciones=observaciones or None,
            orden=orden,
            activo=activo,
            user_made=request.user,
        )

        messages.success(
            request,
            f'La plantilla "{plantilla.nombre}" fue creada correctamente.'
        )

        return redirect(
            "gestion_app:detalle_procedimiento",
            procedimiento.id
        )

    siguiente_orden = procedimiento.ordenes_plantilla.count() + 1

    return render(
        request,
        "gestion/procedimientos/crear_plantilla.html",
        {
            "procedimiento": procedimiento,
            "siguiente_orden": siguiente_orden,
        }
    )


@login_required
def detalle_plantilla(request, plantilla_id):
    plantilla = get_object_or_404(
        PlantillaOrdenProcedimiento.objects
        .select_related(
            "procedimiento"
        ),
        id=plantilla_id
    )

    detalles = (
        PlantillaDetalleOrden.objects
        .filter(
            plantilla_orden=plantilla
        )
        .select_related(
            "prestacion"
        )
        .order_by(
            "orden",
            "id"
        )
    )

    return render(
        request,
        "gestion/procedimientos/detalle_plantilla.html",
        {
            "plantilla": plantilla,
            "procedimiento": plantilla.procedimiento,
            "detalles": detalles,
        }
    )


@login_required
def editar_plantilla(request, plantilla_id):
    plantilla = get_object_or_404(
        PlantillaOrdenProcedimiento.objects
        .select_related(
            "procedimiento"
        ),
        id=plantilla_id
    )

    procedimiento = plantilla.procedimiento

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()
        orden = request.POST.get("orden", "").strip()
        activo = request.POST.get("activo") == "on"

        if not nombre:
            messages.error(
                request,
                "Debe ingresar el nombre de la plantilla."
            )

            return render(
                request,
                "gestion/procedimientos/editar_plantilla.html",
                {
                    "plantilla": plantilla,
                    "procedimiento": procedimiento,
                }
            )

        try:
            orden = int(orden)

            if orden < 1:
                orden = 1

        except (TypeError, ValueError):
            orden = plantilla.orden

        plantilla.nombre = nombre
        plantilla.observaciones = observaciones or None
        plantilla.orden = orden
        plantilla.activo = activo

        if hasattr(plantilla, "user_modified"):
            plantilla.user_modified = request.user

        plantilla.save()

        messages.success(
            request,
            "La plantilla fue actualizada correctamente."
        )

        return redirect(
            "gestion_app:detalle_procedimiento",
            procedimiento.id
        )

    return render(
        request,
        "gestion/procedimientos/editar_plantilla.html",
        {
            "plantilla": plantilla,
            "procedimiento": procedimiento,
        }
    )


@login_required
def eliminar_plantilla(request, plantilla_id):
    plantilla = get_object_or_404(
        PlantillaOrdenProcedimiento.objects
        .select_related(
            "procedimiento"
        ),
        id=plantilla_id
    )

    procedimiento = plantilla.procedimiento
    total_detalles = plantilla.detalles.count()

    if request.method == "POST":
        nombre = plantilla.nombre

        plantilla.delete()

        messages.success(
            request,
            f'La plantilla "{nombre}" fue eliminada correctamente.'
        )

        return redirect(
            "gestion_app:detalle_procedimiento",
            procedimiento.id
        )

    return render(
        request,
        "gestion/procedimientos/eliminar_plantilla.html",
        {
            "plantilla": plantilla,
            "procedimiento": procedimiento,
            "total_detalles": total_detalles,
        }
    )




@login_required
def crear_detalle_plantilla(request, plantilla_id):
    plantilla = get_object_or_404(
        PlantillaOrdenProcedimiento.objects.select_related(
            "procedimiento"
        ),
        id=plantilla_id
    )

    procedimiento = plantilla.procedimiento

    prestaciones = (
        Prestacion.objects
        .all()
        .order_by("codigo", "nombre")
    )

    valores_honorarios_gastos = [
        valor
        for valor, etiqueta
        in DetalleOrden.HONORARIOS_GASTOS
    ]

    valores_tipo_honorario = [
        valor
        for valor, etiqueta
        in DetalleOrden.TIPOS_HONORARIO
    ]

    if request.method == "POST":

        prestacion_id = request.POST.get(
            "prestacion",
            ""
        ).strip()

        cantidad_raw = request.POST.get(
            "cantidad",
            "1"
        ).strip()

        honorarios_gastos = request.POST.get(
            "honorarios_gastos",
            ""
        ).strip()

        tipo_honorario = request.POST.get(
            "tipo_honorario",
            ""
        ).strip()

        orden_raw = request.POST.get(
            "orden",
            ""
        ).strip()

        activo = request.POST.get("activo") == "on"

        # =================================================
        # VALIDAR PRESTACION
        # =================================================

        if not prestacion_id:

            messages.error(
                request,
                "Debe seleccionar una prestación."
            )

            return render(
                request,
                "gestion/procedimientos/crear_detalle_plantilla.html",
                {
                    "plantilla": plantilla,
                    "procedimiento": procedimiento,
                    "prestaciones": prestaciones,

                    "prestacion_seleccionada": prestacion_id,
                    "cantidad": cantidad_raw,
                    "honorarios_gastos": honorarios_gastos,
                    "tipo_honorario": tipo_honorario,
                    "orden": orden_raw,
                    "activo": activo,

                    "honorarios_gastos_choices":
                        DetalleOrden.HONORARIOS_GASTOS,

                    "tipos_honorario_choices":
                        DetalleOrden.TIPOS_HONORARIO,
                }
            )

        prestacion = get_object_or_404(
            Prestacion,
            id=prestacion_id
        )

        # =================================================
        # VALIDAR CANTIDAD
        # =================================================

        try:
            cantidad = int(cantidad_raw)

            if cantidad < 1:
                raise ValueError

        except (TypeError, ValueError):

            messages.error(
                request,
                "La cantidad debe ser un número mayor o igual a 1."
            )

            return render(
                request,
                "gestion/procedimientos/crear_detalle_plantilla.html",
                {
                    "plantilla": plantilla,
                    "procedimiento": procedimiento,
                    "prestaciones": prestaciones,

                    "prestacion_seleccionada": prestacion_id,
                    "cantidad": cantidad_raw,
                    "honorarios_gastos": honorarios_gastos,
                    "tipo_honorario": tipo_honorario,
                    "orden": orden_raw,
                    "activo": activo,

                    "honorarios_gastos_choices":
                        DetalleOrden.HONORARIOS_GASTOS,

                    "tipos_honorario_choices":
                        DetalleOrden.TIPOS_HONORARIO,
                }
            )

        # =================================================
        # VALIDAR ORDEN
        # =================================================

        if orden_raw:

            try:
                orden = int(orden_raw)

                if orden < 1:
                    raise ValueError

            except (TypeError, ValueError):

                messages.error(
                    request,
                    "El orden debe ser un número mayor o igual a 1."
                )

                return render(
                    request,
                    "gestion/procedimientos/crear_detalle_plantilla.html",
                    {
                        "plantilla": plantilla,
                        "procedimiento": procedimiento,
                        "prestaciones": prestaciones,

                        "prestacion_seleccionada": prestacion_id,
                        "cantidad": cantidad_raw,
                        "honorarios_gastos": honorarios_gastos,
                        "tipo_honorario": tipo_honorario,
                        "orden": orden_raw,
                        "activo": activo,

                        "honorarios_gastos_choices":
                            DetalleOrden.HONORARIOS_GASTOS,

                        "tipos_honorario_choices":
                            DetalleOrden.TIPOS_HONORARIO,
                    }
                )

        else:
            orden = plantilla.detalles.count() + 1

        # =================================================
        # VALIDAR CONCEPTO
        # =================================================

        if honorarios_gastos not in valores_honorarios_gastos:

            messages.error(
                request,
                "Debe seleccionar un concepto válido."
            )

            return render(
                request,
                "gestion/procedimientos/crear_detalle_plantilla.html",
                {
                    "plantilla": plantilla,
                    "procedimiento": procedimiento,
                    "prestaciones": prestaciones,

                    "prestacion_seleccionada": prestacion_id,
                    "cantidad": cantidad,
                    "honorarios_gastos": honorarios_gastos,
                    "tipo_honorario": tipo_honorario,
                    "orden": orden,
                    "activo": activo,

                    "honorarios_gastos_choices":
                        DetalleOrden.HONORARIOS_GASTOS,

                    "tipos_honorario_choices":
                        DetalleOrden.TIPOS_HONORARIO,
                }
            )

        # =================================================
        # REGLAS CONCEPTO / NIVEL
        # =================================================

        # Si es gasto, no corresponde nivel.
        if honorarios_gastos == "gastos":
            tipo_honorario = None

        # Si es honorario, tiene que tener nivel.
        elif honorarios_gastos == "honorarios":

            if not tipo_honorario:

                messages.error(
                    request,
                    (
                        "Cuando el concepto es Honorarios "
                        "debe seleccionar un nivel."
                    )
                )

                return render(
                    request,
                    "gestion/procedimientos/crear_detalle_plantilla.html",
                    {
                        "plantilla": plantilla,
                        "procedimiento": procedimiento,
                        "prestaciones": prestaciones,

                        "prestacion_seleccionada": prestacion_id,
                        "cantidad": cantidad,
                        "honorarios_gastos": honorarios_gastos,
                        "tipo_honorario": tipo_honorario,
                        "orden": orden,
                        "activo": activo,

                        "honorarios_gastos_choices":
                            DetalleOrden.HONORARIOS_GASTOS,

                        "tipos_honorario_choices":
                            DetalleOrden.TIPOS_HONORARIO,
                    }
                )

            if tipo_honorario not in valores_tipo_honorario:

                messages.error(
                    request,
                    "El nivel de honorario seleccionado no es válido."
                )

                return render(
                    request,
                    "gestion/procedimientos/crear_detalle_plantilla.html",
                    {
                        "plantilla": plantilla,
                        "procedimiento": procedimiento,
                        "prestaciones": prestaciones,

                        "prestacion_seleccionada": prestacion_id,
                        "cantidad": cantidad,
                        "honorarios_gastos": honorarios_gastos,
                        "tipo_honorario": tipo_honorario,
                        "orden": orden,
                        "activo": activo,

                        "honorarios_gastos_choices":
                            DetalleOrden.HONORARIOS_GASTOS,

                        "tipos_honorario_choices":
                            DetalleOrden.TIPOS_HONORARIO,
                    }
                )

        # Si el concepto es "todo", permitimos nivel vacío.
        elif honorarios_gastos == "todo":

            if (
                tipo_honorario
                and tipo_honorario not in valores_tipo_honorario
            ):

                messages.error(
                    request,
                    "El nivel seleccionado no es válido."
                )

                return render(
                    request,
                    "gestion/procedimientos/crear_detalle_plantilla.html",
                    {
                        "plantilla": plantilla,
                        "procedimiento": procedimiento,
                        "prestaciones": prestaciones,

                        "prestacion_seleccionada": prestacion_id,
                        "cantidad": cantidad,
                        "honorarios_gastos": honorarios_gastos,
                        "tipo_honorario": tipo_honorario,
                        "orden": orden,
                        "activo": activo,

                        "honorarios_gastos_choices":
                            DetalleOrden.HONORARIOS_GASTOS,

                        "tipos_honorario_choices":
                            DetalleOrden.TIPOS_HONORARIO,
                    }
                )

        # =================================================
        # CREAR DETALLE
        # =================================================

        detalle = PlantillaDetalleOrden.objects.create(
            plantilla_orden=plantilla,
            prestacion=prestacion,
            cantidad=cantidad,
            honorarios_gastos=honorarios_gastos,
            tipo_honorario=tipo_honorario or None,
            orden=orden,
            activo=activo,
            user_made=request.user,
        )

        messages.success(
            request,
            (
                f'La prestación '
                f'"{detalle.prestacion.codigo} - '
                f'{detalle.prestacion.nombre}" '
                f'fue agregada correctamente.'
            )
        )

        return redirect(
            "gestion_app:detalle_plantilla",
            plantilla.id
        )

    # =====================================================
    # GET
    # =====================================================

    siguiente_orden = plantilla.detalles.count() + 1

    return render(
        request,
        "gestion/procedimientos/crear_detalle_plantilla.html",
        {
            "plantilla": plantilla,
            "procedimiento": procedimiento,
            "prestaciones": prestaciones,

            "siguiente_orden": siguiente_orden,

            "honorarios_gastos_choices":
                DetalleOrden.HONORARIOS_GASTOS,

            "tipos_honorario_choices":
                DetalleOrden.TIPOS_HONORARIO,
        }
    )


# =========================================================
# VER DETALLE DE PLANTILLA
# =========================================================

@login_required
def detalle_detalle_plantilla(request, detalle_id):

    detalle = get_object_or_404(
        PlantillaDetalleOrden.objects.select_related(
            "plantilla_orden",
            "plantilla_orden__procedimiento",
            "prestacion",
        ),
        id=detalle_id
    )

    plantilla = detalle.plantilla_orden
    procedimiento = plantilla.procedimiento

    return render(
        request,
        "gestion/procedimientos/detalle_detalle_plantilla.html",
        {
            "detalle": detalle,
            "plantilla": plantilla,
            "procedimiento": procedimiento,
        }
    )


# =========================================================
# EDITAR DETALLE DE PLANTILLA
# =========================================================

@login_required
def editar_detalle_plantilla(request, detalle_id):

    detalle = get_object_or_404(
        PlantillaDetalleOrden.objects.select_related(
            "plantilla_orden",
            "plantilla_orden__procedimiento",
            "prestacion",
        ),
        id=detalle_id
    )

    plantilla = detalle.plantilla_orden
    procedimiento = plantilla.procedimiento

    prestaciones = (
        Prestacion.objects
        .all()
        .order_by("codigo", "nombre")
    )

    valores_honorarios_gastos = [
        valor
        for valor, etiqueta
        in DetalleOrden.HONORARIOS_GASTOS
    ]

    valores_tipo_honorario = [
        valor
        for valor, etiqueta
        in DetalleOrden.TIPOS_HONORARIO
    ]

    if request.method == "POST":

        prestacion_id = request.POST.get(
            "prestacion",
            ""
        ).strip()

        cantidad_raw = request.POST.get(
            "cantidad",
            "1"
        ).strip()

        honorarios_gastos = request.POST.get(
            "honorarios_gastos",
            ""
        ).strip()

        tipo_honorario = request.POST.get(
            "tipo_honorario",
            ""
        ).strip()

        orden_raw = request.POST.get(
            "orden",
            ""
        ).strip()

        activo = request.POST.get("activo") == "on"

        # =================================================
        # PRESTACION
        # =================================================

        if not prestacion_id:

            messages.error(
                request,
                "Debe seleccionar una prestación."
            )

            return render(
                request,
                "gestion/procedimientos/editar_detalle_plantilla.html",
                {
                    "detalle": detalle,
                    "plantilla": plantilla,
                    "procedimiento": procedimiento,
                    "prestaciones": prestaciones,

                    "prestacion_seleccionada": prestacion_id,
                    "cantidad_post": cantidad_raw,
                    "honorarios_gastos_post": honorarios_gastos,
                    "tipo_honorario_post": tipo_honorario,
                    "orden_post": orden_raw,
                    "activo_post": activo,

                    "honorarios_gastos_choices":
                        DetalleOrden.HONORARIOS_GASTOS,

                    "tipos_honorario_choices":
                        DetalleOrden.TIPOS_HONORARIO,
                }
            )

        prestacion = get_object_or_404(
            Prestacion,
            id=prestacion_id
        )

        # =================================================
        # CANTIDAD
        # =================================================

        try:
            cantidad = int(cantidad_raw)

            if cantidad < 1:
                raise ValueError

        except (TypeError, ValueError):

            messages.error(
                request,
                "La cantidad debe ser un número mayor o igual a 1."
            )

            return render(
                request,
                "gestion/procedimientos/editar_detalle_plantilla.html",
                {
                    "detalle": detalle,
                    "plantilla": plantilla,
                    "procedimiento": procedimiento,
                    "prestaciones": prestaciones,

                    "prestacion_seleccionada": prestacion_id,
                    "cantidad_post": cantidad_raw,
                    "honorarios_gastos_post": honorarios_gastos,
                    "tipo_honorario_post": tipo_honorario,
                    "orden_post": orden_raw,
                    "activo_post": activo,

                    "honorarios_gastos_choices":
                        DetalleOrden.HONORARIOS_GASTOS,

                    "tipos_honorario_choices":
                        DetalleOrden.TIPOS_HONORARIO,
                }
            )

        # =================================================
        # ORDEN
        # =================================================

        try:
            orden = int(orden_raw)

            if orden < 1:
                raise ValueError

        except (TypeError, ValueError):

            messages.error(
                request,
                "El orden debe ser un número mayor o igual a 1."
            )

            return render(
                request,
                "gestion/procedimientos/editar_detalle_plantilla.html",
                {
                    "detalle": detalle,
                    "plantilla": plantilla,
                    "procedimiento": procedimiento,
                    "prestaciones": prestaciones,

                    "prestacion_seleccionada": prestacion_id,
                    "cantidad_post": cantidad,
                    "honorarios_gastos_post": honorarios_gastos,
                    "tipo_honorario_post": tipo_honorario,
                    "orden_post": orden_raw,
                    "activo_post": activo,

                    "honorarios_gastos_choices":
                        DetalleOrden.HONORARIOS_GASTOS,

                    "tipos_honorario_choices":
                        DetalleOrden.TIPOS_HONORARIO,
                }
            )

        # =================================================
        # CONCEPTO
        # =================================================

        if honorarios_gastos not in valores_honorarios_gastos:

            messages.error(
                request,
                "Debe seleccionar un concepto válido."
            )

            return render(
                request,
                "gestion/procedimientos/editar_detalle_plantilla.html",
                {
                    "detalle": detalle,
                    "plantilla": plantilla,
                    "procedimiento": procedimiento,
                    "prestaciones": prestaciones,

                    "prestacion_seleccionada": prestacion_id,
                    "cantidad_post": cantidad,
                    "honorarios_gastos_post": honorarios_gastos,
                    "tipo_honorario_post": tipo_honorario,
                    "orden_post": orden,
                    "activo_post": activo,

                    "honorarios_gastos_choices":
                        DetalleOrden.HONORARIOS_GASTOS,

                    "tipos_honorario_choices":
                        DetalleOrden.TIPOS_HONORARIO,
                }
            )

        # =================================================
        # REGLAS CONCEPTO / NIVEL
        # =================================================

        if honorarios_gastos == "gastos":

            tipo_honorario = None

        elif honorarios_gastos == "honorarios":

            if not tipo_honorario:

                messages.error(
                    request,
                    (
                        "Cuando el concepto es Honorarios "
                        "debe seleccionar un nivel."
                    )
                )

                return render(
                    request,
                    "gestion/procedimientos/editar_detalle_plantilla.html",
                    {
                        "detalle": detalle,
                        "plantilla": plantilla,
                        "procedimiento": procedimiento,
                        "prestaciones": prestaciones,

                        "prestacion_seleccionada": prestacion_id,
                        "cantidad_post": cantidad,
                        "honorarios_gastos_post": honorarios_gastos,
                        "tipo_honorario_post": tipo_honorario,
                        "orden_post": orden,
                        "activo_post": activo,

                        "honorarios_gastos_choices":
                            DetalleOrden.HONORARIOS_GASTOS,

                        "tipos_honorario_choices":
                            DetalleOrden.TIPOS_HONORARIO,
                    }
                )

            if tipo_honorario not in valores_tipo_honorario:

                messages.error(
                    request,
                    "El nivel de honorario seleccionado no es válido."
                )

                return render(
                    request,
                    "gestion/procedimientos/editar_detalle_plantilla.html",
                    {
                        "detalle": detalle,
                        "plantilla": plantilla,
                        "procedimiento": procedimiento,
                        "prestaciones": prestaciones,

                        "prestacion_seleccionada": prestacion_id,
                        "cantidad_post": cantidad,
                        "honorarios_gastos_post": honorarios_gastos,
                        "tipo_honorario_post": tipo_honorario,
                        "orden_post": orden,
                        "activo_post": activo,

                        "honorarios_gastos_choices":
                            DetalleOrden.HONORARIOS_GASTOS,

                        "tipos_honorario_choices":
                            DetalleOrden.TIPOS_HONORARIO,
                    }
                )

        elif honorarios_gastos == "todo":

            if (
                tipo_honorario
                and tipo_honorario not in valores_tipo_honorario
            ):

                messages.error(
                    request,
                    "El nivel seleccionado no es válido."
                )

                return render(
                    request,
                    "gestion/procedimientos/editar_detalle_plantilla.html",
                    {
                        "detalle": detalle,
                        "plantilla": plantilla,
                        "procedimiento": procedimiento,
                        "prestaciones": prestaciones,

                        "prestacion_seleccionada": prestacion_id,
                        "cantidad_post": cantidad,
                        "honorarios_gastos_post": honorarios_gastos,
                        "tipo_honorario_post": tipo_honorario,
                        "orden_post": orden,
                        "activo_post": activo,

                        "honorarios_gastos_choices":
                            DetalleOrden.HONORARIOS_GASTOS,

                        "tipos_honorario_choices":
                            DetalleOrden.TIPOS_HONORARIO,
                    }
                )

        # =================================================
        # GUARDAR
        # =================================================

        detalle.prestacion = prestacion
        detalle.cantidad = cantidad
        detalle.honorarios_gastos = honorarios_gastos
        detalle.tipo_honorario = tipo_honorario or None
        detalle.orden = orden
        detalle.activo = activo

        if hasattr(detalle, "user_modified"):
            detalle.user_modified = request.user

        detalle.save()

        messages.success(
            request,
            "El detalle de la plantilla fue actualizado correctamente."
        )

        return redirect(
            "gestion_app:detalle_plantilla",
            plantilla.id
        )

    # =====================================================
    # GET
    # =====================================================

    return render(
        request,
        "gestion/procedimientos/editar_detalle_plantilla.html",
        {
            "detalle": detalle,
            "plantilla": plantilla,
            "procedimiento": procedimiento,
            "prestaciones": prestaciones,

            "honorarios_gastos_choices":
                DetalleOrden.HONORARIOS_GASTOS,

            "tipos_honorario_choices":
                DetalleOrden.TIPOS_HONORARIO,
        }
    )


# =========================================================
# ELIMINAR DETALLE DE PLANTILLA
# =========================================================

@login_required
def eliminar_detalle_plantilla(request, detalle_id):

    detalle = get_object_or_404(
        PlantillaDetalleOrden.objects.select_related(
            "plantilla_orden",
            "plantilla_orden__procedimiento",
            "prestacion",
        ),
        id=detalle_id
    )

    plantilla = detalle.plantilla_orden
    procedimiento = plantilla.procedimiento

    if request.method == "POST":

        codigo = detalle.prestacion.codigo
        nombre = detalle.prestacion.nombre

        detalle.delete()

        messages.success(
            request,
            (
                f'La prestación "{codigo} - {nombre}" '
                f'fue eliminada correctamente de la plantilla.'
            )
        )

        return redirect(
            "gestion_app:detalle_plantilla",
            plantilla.id
        )

    return render(
        request,
        "gestion/procedimientos/eliminar_detalle_plantilla.html",
        {
            "detalle": detalle,
            "plantilla": plantilla,
            "procedimiento": procedimiento,
        }
    )