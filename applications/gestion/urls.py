from django.urls import path
from . import views

app_name = 'gestion_app'

urlpatterns = [
    path('', views.home_view, name='core'),  # Formulario para agregar producto
    path("preingresos/", views.lista_preingresos, name="lista_preingresos"),
    path("preingresos/nuevo/", views.agregar_preingreso, name="agregar_preingreso"),
    path("ajax/pacientes/buscar/", views.buscar_pacientes_ajax, name="buscar_pacientes_ajax"),
    path("ajax/pacientes/crear/", views.crear_paciente_ajax, name="crear_paciente_ajax"),
    path("preingresos/<int:preingreso_id>/detalle/", views.detalle_preingreso, name="detalle_preingreso"),
    path("preingresos/<int:preingreso_id>/editar/", views.editar_preingreso, name="editar_preingreso"),

    path("preingresos/<int:preingreso_id>/ordenes/", views.lista_ordenes_preingreso, name="lista_ordenes_preingreso"),
    path("preingresos/<int:preingreso_id>/imprimir/",views.imprimir_preingreso,name="imprimir_preingreso"),
    path("preingresos/<int:preingreso_id>/ordenes/agregar/",views.agregar_orden_preingreso,name="agregar_orden_preingreso"),
    path("ajax/prestaciones/buscar/",views.buscar_prestaciones_ajax,name="buscar_prestaciones_ajax"),
    path("prestaciones/buscar-por-codigo/",views.buscar_prestacion_por_codigo_ajax,name="buscar_prestacion_por_codigo_ajax"),
    path("ordenes/<int:orden_id>/",views.detalle_orden,name="detalle_orden",),
    path("ordenes/preingreso/<int:orden_id>/",views.detalle_orden_preingreso,name="detalle_orden_preingreso",),
    path("ingresos/",views.lista_ingresos,name="lista_ingresos",),
    path("ingresos/agregar_ingreso/",views.agregar_ingreso,name="agregar_ingreso",),
    path("ingresos/programado/agregar/",views.agregar_ingreso_programado,name="agregar_ingreso_programado"),
    path("ajax/buscar-preingresos/",views.buscar_preingresos_ajax,name="buscar_preingresos_ajax"),
    path( "orden/<int:orden_id>/imprimir/",views.imprimir_orden,name="imprimir_orden"), 

    path("ingresos/<int:preingreso_id>/ordenes/agregar/",views.agregar_orden_ingreso,name="agregar_orden_ingreso"),

    path(
    "ingresos/<int:ingreso_id>/editar/",
    views.editar_ingreso,
    name="editar_ingreso"
    ),
    path("ingresos/<int:preingreso_id>/detalle/", views.detalle_ingreso, name="detalle_ingreso"),
    path("ordenes/<int:orden_id>/autorizar/", views.autorizar_orden, name="autorizar_orden"),
    path("ordenes/<int:orden_id>/anular/", views.anular_orden, name="anular_orden"),
    path("ordenes/<int:orden_id>/cambiar-tenencia/", views.cambiar_tenencia_orden, name="cambiar_tenencia_orden"),

    path(
    "entregas/",
    views.lista_planillas_entrega,
    name="lista_planillas_entrega"
    ),

    path(
        "entregas/<int:planilla_id>/anular/",
        views.anular_planilla_entrega,
        name="anular_planilla_entrega"
    ),

    path(
        "entregas/<int:planilla_id>/entregar/",
        views.entregar_planilla_entrega,
        name="entregar_planilla_entrega"
    ),

    path(
        "entregas/<int:planilla_id>/imprimir/",
        views.imprimir_planilla_entrega,
        name="imprimir_planilla_entrega"
    ),
    path(
    "entregas/confeccionar/",
    views.confeccionar_planilla_entrega,
    name="confeccionar_planilla_entrega"
    ),
    path(
        "ingresos/<int:preingreso_id>/cerrar-episodio/",
        views.cerrar_episodio_ajax,
        name="cerrar_episodio_ajax",
    ),    


    path(
        "ordenes/gestion/",
        views.gestion_ordenes,
        name="gestion_ordenes",
    ),

    path(
        "ordenes/gestion/<int:orden_id>/detalle/",
        views.detalle_orden_gestion_ajax,
        name="detalle_orden_gestion_ajax",
    ),

    path(
        "ordenes/gestion/<int:orden_id>/autorizar/",
        views.autorizar_orden_gestion_ajax,
        name="autorizar_orden_gestion_ajax",
    ),

    path(
        "ordenes/gestion/<int:orden_id>/anular/",
        views.anular_orden_gestion_ajax,
        name="anular_orden_gestion_ajax",
    ),

    path(
        "ordenes/gestion/<int:orden_id>/tenencia/",
        views.cambiar_tenencia_gestion_ajax,
        name="cambiar_tenencia_gestion_ajax",
    ),

    path(
        "ordenes/<int:orden_id>/editar/",
        views.editar_orden_ingreso,
        name="editar_orden_ingreso",
    ),
    path(
        "ordenes/<int:orden_id>/historial/",
        views.historial_orden_ajax,
        name="historial_orden_ajax",
    ),
    path(
        "entregas/planillas/<int:planilla_id>/detalle/",
        views.detalle_planilla_entrega,
        name="detalle_planilla_entrega",
    ),

    path(
        "ingresos/erp/nuevo/",
        views.guardar_ingreso_erp,
        name="guardar_ingreso_erp",
    ),

    path(
        "ingresos/erp/buscar/",
        views.buscar_ingreso_erp,
        name="buscar_ingreso_erp",
    ),


      # =====================================================
    # PROCEDIMIENTOS
    # =====================================================

    path(
        "procedimientos/",
        views.lista_procedimientos,
        name="lista_procedimientos",
    ),

    path(
        "procedimientos/nuevo/",
        views.crear_procedimiento,
        name="crear_procedimiento",
    ),

    path(
        "procedimientos/<int:procedimiento_id>/",
        views.detalle_procedimiento,
        name="detalle_procedimiento",
    ),

    path(
        "procedimientos/<int:procedimiento_id>/editar/",
        views.editar_procedimiento,
        name="editar_procedimiento",
    ),

    path(
        "procedimientos/<int:procedimiento_id>/eliminar/",
        views.eliminar_procedimiento,
        name="eliminar_procedimiento",
    ),


    # =====================================================
    # PLANTILLAS DE PROCEDIMIENTOS
    # =====================================================

    path(
        "procedimientos/<int:procedimiento_id>/plantillas/nueva/",
        views.crear_plantilla,
        name="crear_plantilla",
    ),

    path(
        "procedimientos/plantillas/<int:plantilla_id>/",
        views.detalle_plantilla,
        name="detalle_plantilla",
    ),

    path(
        "procedimientos/plantillas/<int:plantilla_id>/editar/",
        views.editar_plantilla,
        name="editar_plantilla",
    ),

    path(
        "procedimientos/plantillas/<int:plantilla_id>/eliminar/",
        views.eliminar_plantilla,
        name="eliminar_plantilla",
    ),
    # =========================================================
    # DETALLES / PRESTACIONES DE LAS PLANTILLAS
    # =========================================================

    path(
        "procedimientos/plantillas/<int:plantilla_id>/detalles/nuevo/",
        views.crear_detalle_plantilla,
        name="crear_detalle_plantilla",
    ),

    path(
        "procedimientos/plantillas/detalles/<int:detalle_id>/",
        views.detalle_detalle_plantilla,
        name="detalle_detalle_plantilla",
    ),

    path(
        "procedimientos/plantillas/detalles/<int:detalle_id>/editar/",
        views.editar_detalle_plantilla,
        name="editar_detalle_plantilla",
    ),

    path(
        "procedimientos/plantillas/detalles/<int:detalle_id>/eliminar/",
        views.eliminar_detalle_plantilla,
        name="eliminar_detalle_plantilla",
    ),

    path(
    "preingresos/<int:preingreso_id>/procedimientos/ajax/",
    views.procedimientos_preingreso_ajax,
    name="procedimientos_preingreso_ajax",
    ),

    path(
        "preingresos/<int:preingreso_id>/procedimientos/generar/ajax/",
        views.generar_ordenes_procedimiento_ajax,
        name="generar_ordenes_procedimiento_ajax",
    ),
    path(
        "preingreso/buscar-paciente-innova/",
        views.buscar_paciente_innova_preingreso,
        name="buscar_paciente_innova_preingreso",
    ),

]
