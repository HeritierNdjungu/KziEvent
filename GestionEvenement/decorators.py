from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect
from django.http import HttpResponse
from functools import wraps
from .models import Abonne, ChargeDeProgrammation, ChargeDeCommunication, Receptionniste


# Vérification si l'utilisateur est un abonné
def is_abonne(user):
    return hasattr(user, 'abonne_profile_new')

# Vérification si l'utilisateur est un chargé de programmation
def is_charge_programmation(user):
    return hasattr(user, 'charge_de_programmation_profile')

# Vérification si l'utilisateur est un chargé de communication
def is_charge_communication(user):
    return hasattr(user, 'chargedecommunication')

# Vérification si l'utilisateur est un réceptionniste
def is_receptionniste(user):
    return hasattr(user, 'receptionniste_profile')

# Décorateur pour restreindre l'accès aux abonnés
def abonne_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('GestionEvenement:connexion')
        if not is_abonne(request.user):
            return HttpResponse("Accès non autorisé. Vous devez être un abonné pour accéder à cette page.", status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Décorateur pour restreindre l'accès aux chargés de programmation
def charge_programmation_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('GestionEvenement:connexion')
        if not is_charge_programmation(request.user):
            return HttpResponse("Accès non autorisé. Vous devez être un chargé de programmation pour accéder à cette page.", status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Décorateur pour restreindre l'accès aux chargés de communication
def charge_communication_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('GestionEvenement:connexion')
        if not is_charge_communication(request.user):
            return HttpResponse("Accès non autorisé. Vous devez être un chargé de communication pour accéder à cette page.", status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Décorateur pour restreindre l'accès aux réceptionnistes
def receptionniste_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('GestionEvenement:connexion')
        if not is_receptionniste(request.user):
            return HttpResponse("Accès non autorisé. Vous devez être un réceptionniste pour accéder à cette page.", status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Décorateur pour restreindre l'accès au personnel (tous les rôles sauf abonné)
def personnel_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('GestionEvenement:connexion')
        if not (is_charge_programmation(request.user) or is_charge_communication(request.user) or is_receptionniste(request.user) or request.user.is_staff):
            return HttpResponse("Accès non autorisé. Vous devez être un membre du personnel pour accéder à cette page.", status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Vérification si l'utilisateur est un administrateur ou personnel
def is_admin_staff(user):
    return user.is_authenticated and user.is_staff  # Vérifie si l'utilisateur a le statut "staff"

# Décorateur pour restreindre l'accès aux administrateurs et personnel
def admin_staff_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not is_admin_staff(request.user):
            return HttpResponse("Accès non autorisé. Vous devez être un administrateur ou membre du personnel.", status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

