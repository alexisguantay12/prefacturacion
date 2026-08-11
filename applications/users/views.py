# configuracion/views.py

from django.shortcuts import render, redirect,get_object_or_404
from applications.users.forms import CrearUsuarioForm
from applications.users.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.urls import reverse 
 
 
from django.contrib.auth.decorators import (
    login_required,
    user_passes_test,
)
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
)
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages

from django.core.exceptions import ValidationError

from applications.users.forms import CrearUsuarioForm
from applications.users.models import User



def crear_usuario(request):
    if request.method == 'POST':
        form = CrearUsuarioForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('users_app:lista_usuarios')
    else:
        form = CrearUsuarioForm()
    return render(request, 'users/crear_usuario.html', {'form': form})

def lista_usuarios(request):
    usuarios = User.objects.all()
    return render(request, 'users/lista_usuarios.html', {'usuarios': usuarios})



from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash


@login_required
def cambiar_contraseña(request):
    # Limpia mensajes antiguos
    storage = messages.get_messages(request)
    for _ in storage:
        pass

    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, '✅ La contraseña fue actualizada correctamente.')
            return redirect('gestion_app:lista_preingresos')
        else:
            # Traducción manual de errores (modifica el form directamente)
            for field, errors in form.errors.items():
                errores_traducidos = []
                for error in errors:
                    error = str(error)
                    if "too similar" in error:
                        error = "La contraseña es demasiado similar al nombre de usuario."
                    elif "too short" in error or "at least 8 characters" in error:
                        error = "La contraseña debe tener al menos 8 caracteres."
                    elif "too common" in error:
                        error = "La contraseña es demasiado común."
                    elif "didn’t match" in error or "did not match" in error:
                        error = "Las contraseñas nuevas no coinciden."
                    elif "incorrect" in error:
                        error = "La contraseña actual es incorrecta."
                    errores_traducidos.append(error)
                form.errors[field] = errores_traducidos  # sobrescribimos los errores traducidos
            messages.error(request, '❌ Corrige los errores antes de continuar.')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'users/cambiar_contraseña.html', {'form': form})


def login_view(request):
    storage = messages.get_messages(request)
    list(storage)  # consumir completamente los mensajes antiguos
    if request.user.is_authenticated:
        return redirect('gestion_app:lista_preingresos')

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'gestion_app:lista_preingresos')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('users_app:login')





def es_administrador(user):
    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name="administrador").exists()
        )
    )



@login_required
@user_passes_test(
    es_administrador,
    login_url="gestion_app:lista_preingresos"
)
def blanquear_contraseña(request, usuario_id):
    usuario = get_object_or_404(
        User,
        id=usuario_id
    )

    if usuario.is_superuser and not request.user.is_superuser:
        messages.error(
            request,
            "No tiene permisos para modificar "
            "la contraseña de este usuario."
        )

        return redirect("users_app:lista_usuarios")

    if request.method == "POST":
        nueva_contraseña = request.POST.get(
            "nueva_contraseña",
            ""
        ).strip()

        confirmar_contraseña = request.POST.get(
            "confirmar_contraseña",
            ""
        ).strip()

        if not nueva_contraseña:
            messages.error(
                request,
                "Debe ingresar una nueva contraseña."
            )

            return redirect(
                "users_app:blanquear_contraseña",
                usuario_id=usuario.id
            )

        if nueva_contraseña != confirmar_contraseña:
            messages.error(
                request,
                "Las contraseñas ingresadas no coinciden."
            )

            return redirect(
                "users_app:blanquear_contraseña",
                usuario_id=usuario.id
            )

        try:
            validate_password(
                nueva_contraseña,
                user=usuario
            )

        except ValidationError as errores:
            for error in errores.messages:
                messages.error(
                    request,
                    traducir_error_contraseña(error)
                )

            return redirect(
                "users_app:blanquear_contraseña",
                usuario_id=usuario.id
            )

        usuario.set_password(nueva_contraseña)
        usuario.save(update_fields=["password"])

        messages.success(
            request,
            f"La contraseña del usuario "
            f"{usuario.username} fue actualizada correctamente."
        )

        return redirect("users_app:lista_usuarios")

    return render(
        request,
        "users/blanquear_contraseña.html",
        {
            "usuario_objetivo": usuario,
        }
    )
def traducir_error_contraseña(error):
    error = str(error)

    if "too similar" in error:
        return (
            "La contraseña es demasiado similar "
            "a los datos del usuario."
        )

    if "too short" in error or "at least 8 characters" in error:
        return "La contraseña debe tener al menos 8 caracteres."

    if "too common" in error:
        return "La contraseña es demasiado común."

    if "entirely numeric" in error:
        return "La contraseña no puede contener solamente números."

    if "didn’t match" in error or "did not match" in error:
        return "Las contraseñas nuevas no coinciden."

    if "incorrect" in error:
        return "La contraseña actual es incorrecta."

    return error
