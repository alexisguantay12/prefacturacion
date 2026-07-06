from django.shortcuts import render


def home_view(request):
    return render(request, "gestion/preingreso/lista_preingresos.html")