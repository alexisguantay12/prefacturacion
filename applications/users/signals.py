from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def crear_grupos(sender, **kwargs):
    administrador_group, _ = Group.objects.get_or_create(name='administrador')
    admisionista_group, _ = Group.objects.get_or_create(name='admisionista')
    facturista_group, _ = Group.objects.get_or_create(name='facturista')

    permisos_admisionista = [
        'view_preingreso',
        'add_preingreso',
        'change_preingreso',
        'view_ordenautorizacion',
        'add_ordenautorizacion',
        'change_ordenautorizacion',
        'view_detalleorden',
        'add_detalleorden',
        'change_detalleorden',
    ]

    permisos_facturista = [
        'view_preingreso',
        'view_ordenautorizacion',
        'change_ordenautorizacion',
        'view_detalleorden',
        'change_detalleorden',
    ]

    # Administrador: todos los permisos
    administrador_group.permissions.set(Permission.objects.all())

    for codename in permisos_admisionista:
        try:
            permiso = Permission.objects.get(codename=codename)
            admisionista_group.permissions.add(permiso)
        except Permission.DoesNotExist:
            pass

    for codename in permisos_facturista:
        try:
            permiso = Permission.objects.get(codename=codename)
            facturista_group.permissions.add(permiso)
        except Permission.DoesNotExist:
            pass