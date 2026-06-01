from django.urls import path
from .views import *

app_name = 'entidades_app'
# ============================================================
# URLS
# ============================================================

urlpatterns = [
    # Servicios
    path("servicios/", listado_servicios, name="listado_servicios"),
    path("servicios/agregar/", agregar_servicio, name="agregar_servicio"),
    path("servicios/<int:pk>/editar/", editar_servicio, name="editar_servicio"),
    path("servicios/<int:pk>/eliminar/", eliminar_servicio, name="eliminar_servicio"),

    # Pacientes
    path("pacientes/", listado_pacientes, name="listado_pacientes"),
    path("pacientes/agregar/", agregar_paciente, name="agregar_paciente"),
    path("pacientes/<int:pk>/editar/", editar_paciente, name="editar_paciente"),
    path("pacientes/<int:pk>/eliminar/", eliminar_paciente, name="eliminar_paciente"),

    # Médicos
    path("medicos/", listado_medicos, name="listado_medicos"),
    path("medicos/agregar/", agregar_medico, name="agregar_medico"),
    path("medicos/<int:pk>/editar/", editar_medico, name="editar_medico"),
    path("medicos/<int:pk>/eliminar/", eliminar_medico, name="eliminar_medico"),

    # Obras sociales
    path("obras-sociales/", listado_obras_sociales, name="listado_obras_sociales"),
    path("obras-sociales/agregar/", agregar_obra_social, name="agregar_obra_social"),
    path("obras-sociales/<int:pk>/editar/", editar_obra_social, name="editar_obra_social"),
    path("obras-sociales/<int:pk>/eliminar/", eliminar_obra_social, name="eliminar_obra_social"),

    # Prestaciones
    path("prestaciones/", listado_prestaciones, name="listado_prestaciones"),
    path("prestaciones/agregar/", agregar_prestacion, name="agregar_prestacion"),
    path("prestaciones/<int:pk>/editar/", editar_prestacion, name="editar_prestacion"),
    path("prestaciones/<int:pk>/eliminar/", eliminar_prestacion, name="eliminar_prestacion"),

    # Planes
    path("planes/", listado_planes, name="listado_planes"),
    path("planes/agregar/", agregar_plan, name="agregar_plan"),
    path("planes/<int:pk>/editar/", editar_plan, name="editar_plan"),
    path("planes/<int:pk>/eliminar/", eliminar_plan, name="eliminar_plan"),
]