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
    path("ingresos/",views.lista_ingresos,name="lista_ingresos",),
    path("ingresos/agregar_ingreso/",views.agregar_ingreso,name="agregar_ingreso",),
    path("ingresos/programado/agregar/",views.agregar_ingreso_programado,name="agregar_ingreso_programado"),
    path("ajax/buscar-preingresos/",views.buscar_preingresos_ajax,name="buscar_preingresos_ajax"),
]
