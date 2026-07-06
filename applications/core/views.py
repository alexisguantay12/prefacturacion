from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required, user_passes_test

# Create your views here.
@login_required
def home_view(request):
    return redirect("gestion_app:lista_preingresos")