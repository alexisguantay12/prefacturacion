from django import forms
from .models import User
from django.contrib.auth.models import Group

class CrearUsuarioForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Contraseña'
    )

    rol = forms.ChoiceField(
        choices=[
            ('administrador', 'Administrador'),
            ('admisionista', 'Admisionista'),
            ('facturista', 'Facturista'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Rol'
    )

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'password',
            'rol',
        ]

        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Usuario'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apellido'
            }),
        }

        labels = {
            'username': 'Usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])

        if commit:
            user.save()

            group_name = self.cleaned_data['rol']
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)

        return user