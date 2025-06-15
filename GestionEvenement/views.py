from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.core.mail import send_mass_mail
from django.core.paginator import Paginator
from django.db.models import Q, Count, Prefetch
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse
from reportlab.pdfgen import canvas
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from datetime import datetime, timedelta
import json

from .models import (
    ProfilUtilisateur, Adresse,
    Abonne, ChargeDeProgrammation, ChargeDeCommunication, Receptionniste,
    Evenement, Reservation, Commentaire, CategorieEvenement, Paiement, Billet,
    Notification, ModeleNotification
)
from .decorators import (
    abonne_required, charge_programmation_required,
    charge_communication_required, receptionniste_required,
    admin_staff_required, is_charge_programmation,
    is_charge_communication, is_admin_staff
)

# Vue de dispatch après connexion
@login_required
def dispatch_dashboard(request):
    """Vue pour rediriger vers le dashboard approprié selon le rôle de l'utilisateur"""
    if hasattr(request.user, "chargedeprogrammation"):
        return redirect('GestionEvenement:dashboard_programmation')
    elif hasattr(request.user, "chargedecommunication"):
        return redirect('GestionEvenement:dashboard_communication')
    elif hasattr(request.user, "receptionniste"):
        return redirect('GestionEvenement:dashboard_receptionniste')
    elif hasattr(request.user, "abonne_profile_new"):
        return redirect('GestionEvenement:dashboard_abonne')
    else:
        messages.warning(request, "Votre rôle n'est pas clairement défini. Veuillez contacter l'administrateur.")
        return redirect('GestionEvenement:accueil')

# Dashboards par rôle
@login_required
def dashboard_abonne_view(request):
    if not hasattr(request.user, "abonne_profile_new"):
        messages.error(request, "Accès non autorisé. Cette page est réservée aux abonnés.")
        return redirect("GestionEvenement:accueil")
    return render(request, "GestionEvenement/dashboards/dashboard_abonne.html")

@login_required
def dashboard_programmation(request):
    """Vue principale du tableau de bord du chargé de programmation"""
    evenements_publies = Evenement.objects.filter(statut='PUBLIE').count()
    evenements_brouillon = Evenement.objects.filter(statut='BROUILLON').count()
    evenements_termines = Evenement.objects.filter(
        date_fin__lt=timezone.now()
    ).count()
    
    evenements_recents = Evenement.objects.all().order_by('-date_debut')[:5]
    evenements_a_venir = Evenement.objects.filter(
        date_debut__gt=timezone.now()
    ).order_by('date_debut')[:5]
    
    context = {
        'evenements_publies_count': evenements_publies,
        'evenements_brouillon_count': evenements_brouillon,
        'evenements_termines_count': evenements_termines,
        'evenements_recents': evenements_recents,
        'evenements_a_venir': evenements_a_venir,
    }
    return render(request, 'GestionEvenement/dashboards/dashboard_programmation.html', context)

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedecommunication") or is_admin_staff(u))
def dashboard_communication(request):
    if not hasattr(request.user, "chargedecommunication"):
        messages.error(request, "Accès non autorisé. Cette page est réservée aux chargés de communication.")
        return redirect("GestionEvenement:accueil")
    context = {
        'evenements_a_publier_count': Evenement.objects.filter(statut='BROUILLON').count(),
        'notifications_mois_count': Notification.objects.filter(
            date_envoi__month=timezone.now().month,
            date_envoi__year=timezone.now().year
        ).count(),
        'evenements_a_publier': Evenement.objects.filter(statut='BROUILLON').order_by('date_debut')[:5],
        'dernieres_notifications': Notification.objects.all().order_by('-date_envoi')[:5]
    }
    return render(request, "GestionEvenement/dashboards/dashboard_communication.html", context)

@login_required
def dashboard_receptionniste_view(request):
    if not hasattr(request.user, "receptionniste"):
        messages.error(request, "Accès non autorisé. Cette page est réservée aux réceptionnistes.")
        return redirect("GestionEvenement:accueil")
    return render(request, "GestionEvenement/dashboards/dashboard_receptionniste.html")

# Vue d_accueil
def home_view(request):
    """Vue pour la page d'accueil"""
    # Événements à la une (les plus récents publiés)
    evenements_a_la_une = Evenement.objects.filter(
        statut='PUBLIE'
    ).order_by('-date_debut')[:3]
    
    # Événements à venir (publiés et dont la date de début est dans le futur)
    evenements_a_venir = Evenement.objects.filter(
        statut='PUBLIE',
        date_debut__gt=timezone.now()
    ).order_by('date_debut')

    # Récupérer les catégories avec leurs événements publiés
    categories = CategorieEvenement.objects.prefetch_related(
        Prefetch(
            'evenements_cat',
            queryset=Evenement.objects.filter(statut='PUBLIE'),
            to_attr='evenements_publies'
        )
    ).all()

    context = {
        'evenements_a_la_une': evenements_a_la_une,
        'evenements_a_venir': evenements_a_venir,
        'categories': categories,
    }
    return render(request, 'GestionEvenement/home.html', context)

# Vue d'inscription
def inscription_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        # Validation des données
        if not all([username, email, password1, password2, first_name, last_name]):
            messages.error(request, 'Tous les champs sont obligatoires.')
            return render(request, "GestionEvenement/auth/inscription.html")
        
        if password1 != password2:
            messages.error(request, 'Les mots de passe ne correspondent pas.')
            return render(request, "GestionEvenement/auth/inscription.html")
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Ce nom d\'utilisateur est déjà pris.')
            return render(request, "GestionEvenement/auth/inscription.html")
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Cette adresse email est déjà utilisée.')
            return render(request, "GestionEvenement/auth/inscription.html")
        
        try:
            # Création de l'utilisateur
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name
            )
            
            # Création de l'adresse
            Adresse.objects.create(
                user=user,
                rue=request.POST.get('rue'),
                numero=request.POST.get('numero'),
                ville=request.POST.get('ville'),
                code_postal=request.POST.get('code_postal'),
                pays=request.POST.get('pays', 'République Démocratique du Congo')
            )
            
            # Création du profil abonné
            Abonne.objects.create(
                user=user,
                type_abonne=request.POST.get('type_abonne', 'SIMPLE'),
                raison_sociale=request.POST.get('raison_sociale'),
                preferences_notifications=request.POST.get('preferences_notifications', True)
            )
            
            # Connexion de l'utilisateur
            login(request, user)
            messages.success(request, 'Inscription réussie !')
            return redirect('GestionEvenement:accueil')
            
        except Exception as e:
            messages.error(request, f'Erreur lors de l\'inscription : {str(e)}')
            return render(request, "GestionEvenement/auth/inscription.html")
    
    return render(request, "GestionEvenement/auth/inscription.html")

# Vue de connexion
def connexion_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if not all([username, password]):
            messages.error(request, 'Veuillez remplir tous les champs.')
            return render(request, "GestionEvenement/auth/connexion.html")
        
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Connexion réussie !')
            return redirect('GestionEvenement:accueil')
        else:
            messages.error(request, 'Nom d\'utilisateur ou mot de passe incorrect.')
    
    return render(request, "GestionEvenement/auth/connexion.html")

@login_required
@abonne_required
def profil_abonne(request):
    abonne = request.user.abonne_profile_new
    reservations_recentes = Reservation.objects.filter(abonne=abonne).order_by('-date_reservation')[:5]
    evenements_favoris = abonne.evenements_favoris.all()[:5]
    
    context = {
        'abonne': abonne,
        'reservations_recentes': reservations_recentes,
        'evenements_favoris': evenements_favoris,
        'notifications_non_lues': Notification.objects.filter(destinataire=request.user, lu=False).count()
    }
    
    return render(request, 'GestionEvenement/profil/profil_abonne.html', context)

@login_required
def deconnexion_view(request):
    logout(request)
    messages.success(request, 'Vous avez été déconnecté.')
    return redirect('GestionEvenement:accueil')

# Vue pour la création d_événement
@login_required
@user_passes_test(lambda u: hasattr(u, "chargedeprogrammation") or is_admin_staff(u))
def creer_evenement_view(request):
    categories = CategorieEvenement.objects.all()
    if request.method == "POST":
        nom = request.POST.get("nom")
        description = request.POST.get("description")
        date_debut_str = request.POST.get("date_debut")
        date_fin_str = request.POST.get("date_fin")
        lieu = request.POST.get("lieu")
        capacite = request.POST.get("capacite")
        prix = request.POST.get("prix")
        categorie_id = request.POST.get("categorie")
        statut = request.POST.get("statut", "BROUILLON")  # Par défaut en brouillon
        image = request.FILES.get("image")

        errors = []
        if not nom: errors.append("Le nom de l'événement est requis.")
        if not description: errors.append("La description est requise.")
        if not date_debut_str: errors.append("La date de début est requise.")
        if not date_fin_str: errors.append("La date de fin est requise.")
        if not lieu: errors.append("Le lieu est requis.")
        if not capacite or not capacite.isdigit() or int(capacite) <= 0:
            errors.append("La capacité doit être un nombre positif.")
        if not prix:
            errors.append("Le prix est requis.")
        else:
            try:
                prix_float = float(prix)
                if prix_float < 0:
                    errors.append("Le prix ne peut pas être négatif.")
            except ValueError:
                errors.append("Le prix doit être un nombre valide.")

        if errors:
            for error_msg in errors:
                messages.error(request, error_msg)
            return render(request, "GestionEvenement/evenements/creer_evenement.html", {
                "categories": categories,
                "form_data": request.POST,
                "errors": errors
            })
        
        try:
            categorie = CategorieEvenement.objects.get(id=categorie_id) if categorie_id else None
            evenement = Evenement.objects.create(
                nom=nom,
                description=description,
                date_debut=date_debut_str,
                date_fin=date_fin_str,
                lieu=lieu,
                capacite=int(capacite),
                prix=float(prix),
                categorie=categorie,
                image=image,
                responsable_programmation=request.user.chargedeprogrammation,
                statut=statut
            )
            messages.success(request, f"L'événement \"{evenement.nom}\" a été créé avec succès.")
            return redirect("GestionEvenement:liste_evenements_admin")
        except Exception as e:
            messages.error(request, f"Erreur lors de la création de l'événement : {str(e)}")
            return render(request, "GestionEvenement/evenements/creer_evenement.html", {
                "categories": categories,
                "form_data": request.POST
            })

    return render(request, "GestionEvenement/evenements/creer_evenement.html", {"categories": categories})

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedeprogrammation") or is_admin_staff(u))
def ajouter_categorie(request):
    if request.method == "POST":
        nom_categorie = request.POST.get("nom_categorie")
        description = request.POST.get("description")

        errors = []
        if not nom_categorie:
            errors.append("Le nom de la catégorie est requis.")
        if not description:
            errors.append("La description est requise.")

        if errors:
            for error_msg in errors:
                messages.error(request, error_msg)
            return render(request, "GestionEvenement/evenements/ajouter_categorie.html", {
                "form_data": request.POST,
                "errors": errors
            })

        try:
            categorie = CategorieEvenement.objects.create(
                nom_categorie=nom_categorie,
                description=description
            )
            messages.success(request, f"La catégorie \"{categorie.nom_categorie}\" a été ajoutée avec succès.")
            return redirect("GestionEvenement:creer_evenement")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'ajout de la catégorie : {str(e)}")
            return render(request, "GestionEvenement/evenements/ajouter_categorie.html", {
                "form_data": request.POST
            })

    return render(request, "GestionEvenement/evenements/ajouter_categorie.html")

# Vue pour publier un événement et notifier les abonnés
@login_required
@user_passes_test(lambda u: is_charge_communication(u) or is_admin_staff(u))
def publier_evenement_view(request, pk):
    evenement = get_object_or_404(Evenement, pk=pk)
    if request.method == "POST":
        if evenement.statut == "BROUILLON":
            # Mise à jour du statut
            evenement.statut = "PUBLIE"
            evenement.date_publication = timezone.now()
            evenement.save()
            
            # Création d'une notification pour les abonnés
            notification = Notification.objects.create(
                titre=f"Nouvel événement : {evenement.nom}",
                contenu=f"Un nouvel événement vient d'être publié : {evenement.nom}. Ne manquez pas cette occasion !",
                expediteur=request.user.chargedecommunication
            )
            
            # Envoi des emails aux abonnés
            abonnes_a_notifier = Abonne.objects.filter(user__is_active=True).select_related("user")
            datatuple = []
            site_url = request.build_absolute_uri(reverse("GestionEvenement:evenement_detail", args=[evenement.id]))

            for abonne in abonnes_a_notifier:
                if abonne.user.email:
                    sujet = f"Nouvel événement publié : {evenement.nom}"
                    message_text = f"""Bonjour {abonne.user.first_name or abonne.user.username},

Un nouvel événement vient d'être publié : {evenement.nom}.
Description : {evenement.description}
Date : du {evenement.date_debut.strftime("%d/%m/%Y %H:%M")} au {evenement.date_fin.strftime("%d/%m/%Y %H:%M")}.
Lieu : {evenement.lieu}.

Pour plus de détails et pour réserver, visitez : {site_url}

Cordialement,
L'équipe du MuséeEvent"""
                    datatuple.append((sujet, message_text, settings.DEFAULT_FROM_EMAIL, [abonne.user.email]))
                    notification.destinataires.add(abonne)
            
            if datatuple:
                try:
                    send_mass_mail(datatuple, fail_silently=False)
                    messages.success(request, f"L'événement a été publié et {len(datatuple)} notifications ont été envoyées aux abonnés.")
                except Exception as e:
                    messages.warning(request, f"L'événement a été publié mais il y a eu une erreur lors de l'envoi des notifications : {e}")
            else:
                messages.success(request, "L'événement a été publié avec succès.")
        else:
            messages.warning(request, f"L'événement \"{evenement.nom}\" n'est pas un brouillon ou est déjà publié.")
        return redirect("GestionEvenement:dashboard_communication")
    
    return render(request, "GestionEvenement/evenements/confirmer_publication.html", {"evenement": evenement})

@login_required
def evenement_detail_view(request, pk):
    evenement = get_object_or_404(Evenement, pk=pk)
    commentaires = evenement.commentaires_evt.all().order_by('-date_commentaire')
    places_disponibles = evenement.get_places_disponibles()
    
    # Vérifier si l'utilisateur a déjà réservé cet événement
    a_reserve = False
    if hasattr(request.user, 'abonne_profile_new'):
        a_reserve = Reservation.objects.filter(
            evenement=evenement,
            abonne=request.user.abonne_profile_new
        ).exists()
    
    # Vérifications des profils pour le template
    est_abonne = hasattr(request.user, 'abonne_profile_new')
    est_charge_programmation = hasattr(request.user, 'chargedeprogrammation')
    est_charge_communication = hasattr(request.user, 'chargedecommunication')
    
    context = {
        'evenement': evenement,
        'commentaires': commentaires,
        'places_disponibles': places_disponibles,
        'a_reserve': a_reserve,
        'est_abonne': est_abonne,
        'est_charge_programmation': est_charge_programmation,
        'est_charge_communication': est_charge_communication,
        'peut_modifier': est_charge_programmation and evenement.responsable_programmation == request.user.chargedeprogrammation,
        'peut_publier': est_charge_communication and evenement.statut == 'BROUILLON'
    }
    
    return render(request, 'GestionEvenement/evenements/detail_evenement.html', context)

def liste_evenements_view(request):
    # Récupération des filtres depuis les paramètres GET
    categorie_id = request.GET.get('categorie')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    prix_min = request.GET.get('prix_min')
    prix_max = request.GET.get('prix_max')
    recherche = request.GET.get('recherche')

    # Query de base pour les événements publiés et à venir
    evenements = Evenement.objects.filter(
        statut='PUBLIE',
        date_debut__gte=timezone.now()
    )

    # Application des filtres
    if categorie_id:
        evenements = evenements.filter(categorie_id=categorie_id)
    if date_debut:
        evenements = evenements.filter(date_debut__gte=date_debut)
    if date_fin:
        evenements = evenements.filter(date_fin__lte=date_fin)
    if prix_min:
        evenements = evenements.filter(prix__gte=float(prix_min))
    if prix_max:
        evenements = evenements.filter(prix__lte=float(prix_max))
    if recherche:
        evenements = evenements.filter(
            Q(nom__icontains=recherche) |
            Q(description__icontains=recherche) |
            Q(lieu__icontains=recherche)
        )

    # Tri des événements
    tri = request.GET.get('tri', 'date_debut')  # Par défaut, tri par date
    if tri == 'prix_asc':
        evenements = evenements.order_by('prix')
    elif tri == 'prix_desc':
        evenements = evenements.order_by('-prix')
    elif tri == 'nom':
        evenements = evenements.order_by('nom')
    else:  # tri par date par défaut
        evenements = evenements.order_by('date_debut')

    # Pagination
    paginator = Paginator(evenements, 9)  # 9 événements par page
    page = request.GET.get('page')
    evenements_page = paginator.get_page(page)

    # Récupération des catégories pour le filtre
    categories = CategorieEvenement.objects.all()

    context = {
        'evenements': evenements_page,
        'categories': categories,
        'filtres': {
            'categorie': categorie_id,
            'date_debut': date_debut,
            'date_fin': date_fin,
            'prix_min': prix_min,
            'prix_max': prix_max,
            'recherche': recherche,
            'tri': tri
        }
    }

    return render(request, 'GestionEvenement/evenements/liste.html', context)

@login_required
def modifier_profil(request):
    if request.method == "POST":
        # Mise à jour des informations de l'utilisateur
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name = request.POST.get('last_name', request.user.last_name)
        request.user.email = request.POST.get('email', request.user.email)
        request.user.save()

        # Mise à jour du profil
        profil = request.user.profil
        profil.telephone = request.POST.get('telephone', profil.telephone)
        if 'photo' in request.FILES:
            profil.photo = request.FILES['photo']
        profil.save()

        # Si c'est un abonné, mise à jour des informations spécifiques
        if hasattr(request.user, 'abonne_profile_new'):
            abonne = request.user.abonne_profile_new
            abonne.raison_sociale = request.POST.get('raison_sociale', abonne.raison_sociale)
            abonne.save()

        messages.success(request, "Votre profil a été mis à jour avec succès!")
        return redirect('GestionEvenement:profil_abonne')

    context = {
        'user': request.user,
        'profil': request.user.profil,
        'abonne': request.user.abonne_profile_new if hasattr(request.user, 'abonne_profile_new') else None
    }
    return render(request, 'GestionEvenement/profil/modifier_profil.html', context)

# Vues pour la gestion des événements
@login_required
@user_passes_test(lambda u: is_charge_programmation(u) or is_admin_staff(u))
def modifier_evenement_view(request, evenement_id):
    evenement = get_object_or_404(Evenement, pk=evenement_id)
    if request.method == "POST":
        # Récupération des données du formulaire
        nom = request.POST.get("nom")
        description = request.POST.get("description")
        date_debut = request.POST.get("date_debut")
        date_fin = request.POST.get("date_fin")
        lieu = request.POST.get("lieu")
        capacite = request.POST.get("capacite")
        prix = request.POST.get("prix")
        categorie_id = request.POST.get("categorie")

        # Validation des données
        if not all([nom, description, date_debut, date_fin, lieu, capacite, prix]):
            messages.error(request, "Tous les champs sont requis.")
            return render(request, "GestionEvenement/evenements/modifier_evenement.html", {"evenement": evenement})

        try:
            # Mise à jour de l'événement
            evenement.nom = nom
            evenement.description = description
            evenement.date_debut = date_debut
            evenement.date_fin = date_fin
            evenement.lieu = lieu
            evenement.capacite = int(capacite)
            evenement.prix = float(prix)
            if categorie_id:
                evenement.categorie = get_object_or_404(CategorieEvenement, id=categorie_id)
            evenement.save()

            messages.success(request, f"L'événement {evenement.nom} a été modifié avec succès.")
            return redirect("evenement_detail", evenement_id=evenement.id)
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification : {str(e)}")
    
    categories = CategorieEvenement.objects.all()
    return render(request, "GestionEvenement/evenements/modifier_evenement.html", {
        "evenement": evenement,
        "categories": categories
    })

@login_required
@user_passes_test(lambda u: is_charge_programmation(u) or is_admin_staff(u))
def supprimer_evenement_view(request, evenement_id):
    evenement = get_object_or_404(Evenement, pk=evenement_id)
    if request.method == "POST":
        try:
            nom = evenement.nom
            evenement.delete()
            messages.success(request, f"L'événement {nom} a été supprimé avec succès.")
            return redirect("liste_evenements")
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression : {str(e)}")
    return render(request, "GestionEvenement/evenements/supprimer_evenement_confirmation.html", {"evenement": evenement})

# Vues pour les réservations
@login_required
def creer_reservation_view(request, evenement_id):
    evenement = get_object_or_404(Evenement, pk=evenement_id)
    if request.method == "POST":
        nombre_billets = int(request.POST.get("nombre_billets", 1))
        if nombre_billets <= 0:
            messages.error(request, "Le nombre de billets doit être positif.")
            return redirect("evenement_detail", evenement_id=evenement_id)

        try:
            with transaction.atomic():
                # Création de la réservation
                reservation = Reservation.objects.create(
                    evenement=evenement,
                    utilisateur=request.user,
                    nombre_billets=nombre_billets,
                    montant_total=evenement.prix * nombre_billets
                )
                
                # Création des billets associés
                for _ in range(nombre_billets):
                    Billet.objects.create(reservation=reservation)

            messages.success(request, "Votre réservation a été créée avec succès.")
            return redirect("effectuer_paiement", reservation_id=reservation.id)
        except Exception as e:
            messages.error(request, f"Erreur lors de la création de la réservation : {str(e)}")
            return redirect("evenement_detail", evenement_id=evenement_id)

    return render(request, "GestionEvenement/reservations/creer_reservation.html", {"evenement": evenement})

@login_required
def detail_reservation_view(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id)
    if request.user != reservation.utilisateur and not request.user.is_staff:
        messages.error(request, "Vous n'avez pas accès à cette réservation.")
        return redirect("mes_reservations")
    return render(request, "GestionEvenement/reservations/detail_reservation.html", {"reservation": reservation})

@login_required
def mes_reservations_view(request):
    reservations = Reservation.objects.filter(utilisateur=request.user).order_by("-date_reservation")
    return render(request, "GestionEvenement/reservations/mes_reservations.html", {"reservations": reservations})

@login_required
def annuler_reservation_view(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id)
    if request.user != reservation.utilisateur and not request.user.is_staff:
        messages.error(request, "Vous n'avez pas l'autorisation d'annuler cette réservation.")
        return redirect("mes_reservations")

    if request.method == "POST":
        try:
            reservation.statut = "ANNULEE"
            reservation.save()
            messages.success(request, "Votre réservation a été annulée avec succès.")
            return redirect("mes_reservations")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'annulation : {str(e)}")

    return render(request, "GestionEvenement/reservations/annuler_reservation_confirmation.html", {"reservation": reservation})

# Vues pour les paiements
@login_required
def effectuer_paiement_view(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id)
    if request.user != reservation.utilisateur:
        messages.error(request, "Vous n'avez pas accès à ce paiement.")
        return redirect("GestionEvenement:mes_reservations")

    if request.method == "POST":
        mode_paiement = request.POST.get("mode_paiement")
        if not mode_paiement:
            messages.error(request, "Veuillez sélectionner un mode de paiement.")
            return render(request, "GestionEvenement/paiements/effectuer_paiement.html", {"reservation": reservation})

        try:
            paiement = Paiement.objects.create(
                reservation=reservation,
                montant=reservation.montant_total,
                mode_paiement=mode_paiement
            )
            if mode_paiement == "CASH":
                return redirect("GestionEvenement:confirmation_paiement", paiement_id=paiement.id)
            else:
                # Redirection vers le processeur de paiement en ligne
                pass
        except Exception as e:
            messages.error(request, f"Erreur lors du paiement : {str(e)}")

    return render(request, "GestionEvenement/paiements/effectuer_paiement.html", {"reservation": reservation})

@login_required
def confirmation_paiement_view(request, paiement_id):
    paiement = get_object_or_404(Paiement, pk=paiement_id)
    if request.user != paiement.reservation.utilisateur and not request.user.is_staff:
        messages.error(request, "Vous n'avez pas accès à cette confirmation.")
        return redirect("GestionEvenement:mes_reservations")
    return render(request, "GestionEvenement/paiements/confirmation_paiement.html", {"paiement": paiement})

@login_required
@receptionniste_required
def valider_paiement_cash_view(request, paiement_id):
    paiement = get_object_or_404(Paiement, pk=paiement_id)
    if request.method == "POST":
        try:
            paiement.statut = "VALIDE"
            paiement.date_validation = timezone.now()
            paiement.receptionniste = request.user.receptionniste
            paiement.save()
            
            # Mise à jour du statut de la réservation
            reservation = paiement.reservation
            reservation.statut = "CONFIRMEE"
            reservation.save()
            
            messages.success(request, "Le paiement a été validé avec succès.")
            return redirect("GestionEvenement:dashboard_receptionniste")
        except Exception as e:
            messages.error(request, f"Erreur lors de la validation : {str(e)}")
    
    return render(request, "GestionEvenement/paiements/valider_paiement_cash.html", {"paiement": paiement})

# Vues pour les commentaires
@login_required
def ajouter_commentaire_view(request, evenement_id):
    evenement = get_object_or_404(Evenement, pk=evenement_id)
    if request.method == "POST":
        contenu = request.POST.get("contenu")
        if not contenu:
            messages.error(request, "Le commentaire ne peut pas être vide.")
            return redirect("evenement_detail", evenement_id=evenement_id)

        try:
            Commentaire.objects.create(
                evenement=evenement,
                utilisateur=request.user,
                contenu=contenu
            )
            messages.success(request, "Votre commentaire a été ajouté avec succès.")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'ajout du commentaire : {str(e)}")
        
        return redirect("evenement_detail", evenement_id=evenement_id)

@login_required
def modifier_commentaire_view(request, commentaire_id):
    commentaire = get_object_or_404(Commentaire, pk=commentaire_id)
    if request.user != commentaire.utilisateur:
        messages.error(request, "Vous n'avez pas l'autorisation de modifier ce commentaire.")
        return redirect("evenement_detail", evenement_id=commentaire.evenement.id)

    if request.method == "POST":
        contenu = request.POST.get("contenu")
        if not contenu:
            messages.error(request, "Le commentaire ne peut pas être vide.")
        else:
            try:
                commentaire.contenu = contenu
                commentaire.date_modification = timezone.now()
                commentaire.save()
                messages.success(request, "Votre commentaire a été modifié avec succès.")
            except Exception as e:
                messages.error(request, f"Erreur lors de la modification : {str(e)}")
        
        return redirect("evenement_detail", evenement_id=commentaire.evenement.id)

    return render(request, "GestionEvenement/commentaires/modifier_commentaire.html", {"commentaire": commentaire})

@login_required
def supprimer_commentaire_view(request, commentaire_id):
    commentaire = get_object_or_404(Commentaire, pk=commentaire_id)
    if request.user != commentaire.utilisateur and not request.user.is_staff:
        messages.error(request, "Vous n'avez pas l'autorisation de supprimer ce commentaire.")
        return redirect("evenement_detail", evenement_id=commentaire.evenement.id)

    if request.method == "POST":
        evenement_id = commentaire.evenement.id
        try:
            commentaire.delete()
            messages.success(request, "Le commentaire a été supprimé avec succès.")
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression : {str(e)}")
        return redirect("evenement_detail", evenement_id=evenement_id)

    return render(request, "GestionEvenement/commentaires/supprimer_commentaire_confirmation.html", {"commentaire": commentaire})

# Vue pour les billets
@login_required
def telecharger_billet_view(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id)
    if request.user != reservation.utilisateur and not request.user.is_staff:
        messages.error(request, "Vous n'avez pas accès à ce billet.")
        return redirect("mes_reservations")

    # Logique pour générer et télécharger le billet
    try:
        # Code pour générer le PDF du billet
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="billet_{reservation.id}.pdf"'
        
        # Utilisation de ReportLab pour générer le PDF
        p = canvas.Canvas(response)
        # Ajout du contenu du billet
        p.drawString(100, 800, f"Billet pour {reservation.evenement.nom}")
        p.drawString(100, 780, f"Réservation #{reservation.id}")
        p.drawString(100, 760, f"Date : {reservation.evenement.date_debut.strftime('%d/%m/%Y %H:%M')}")
        p.drawString(100, 740, f"Lieu : {reservation.evenement.lieu}")
        p.save()
        
        return response
    except Exception as e:
        messages.error(request, f"Erreur lors de la génération du billet : {str(e)}")
        return redirect("detail_reservation", reservation_id=reservation_id)

# API Views
@login_required
def recherche_evenements_api(request):
    query = request.GET.get('q', '')
    evenements = Evenement.objects.filter(
        Q(nom__icontains=query) |
        Q(description__icontains=query) |
        Q(lieu__icontains=query)
    ).values('id', 'nom', 'date_debut', 'lieu', 'prix')
    return JsonResponse(list(evenements), safe=False)

@login_required
def notifications_non_lues_api(request):
    # À implémenter selon votre système de notifications
    return JsonResponse({"count": 0})  # Placeholder

@login_required
def preferences_view(request):
    if request.method == "POST":
        user = request.user
        if hasattr(user, "abonne_profile_new"):
            abonne = user.abonne_profile_new
            abonne.preferences_notifications = request.POST.get("preferences_notifications", "")
            abonne.save()
            messages.success(request, "Vos préférences ont été mises à jour avec succès.")
        return redirect("GestionEvenement:dashboard_abonne")
    return render(request, "GestionEvenement/profil/preferences.html")

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedecommunication") or is_admin_staff(u))
def creer_newsletter_view(request):
    if request.method == "POST":
        titre = request.POST.get("titre")
        contenu = request.POST.get("contenu")
        destinataires = request.POST.getlist("destinataires")
        
        if not all([titre, contenu, destinataires]):
            messages.error(request, "Tous les champs sont requis.")
            return render(request, "GestionEvenement/communication/creer_newsletter.html")
        
        try:
            # Logique d'envoi de newsletter
            messages.success(request, "La newsletter a été créée et envoyée avec succès.")
            return redirect("GestionEvenement:dashboard_communication")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'envoi de la newsletter : {str(e)}")
    
    return render(request, "GestionEvenement/communication/creer_newsletter.html")

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedecommunication") or is_admin_staff(u))
def moderation_commentaires_view(request):
    commentaires = Commentaire.objects.filter(modere=False).order_by("-date_commentaire")
    if request.method == "POST":
        commentaire_id = request.POST.get("commentaire_id")
        action = request.POST.get("action")
        
        if commentaire_id and action:
            commentaire = get_object_or_404(Commentaire, id=commentaire_id)
            if action == "approuver":
                commentaire.modere = True
                commentaire.save()
                messages.success(request, "Le commentaire a été approuvé.")
            elif action == "supprimer":
                commentaire.delete()
                messages.success(request, "Le commentaire a été supprimé.")
    
    return render(request, "GestionEvenement/communication/moderation_commentaires.html", {
        "commentaires": commentaires
    })

@login_required
@charge_communication_required
def statistiques_communication(request):
    # Statistiques des événements
    total_evenements = Evenement.objects.count()
    evenements_publies = Evenement.objects.filter(statut='PUBLIE').count()
    evenements_brouillon = Evenement.objects.filter(statut='BROUILLON').count()
    evenements_annules = Evenement.objects.filter(statut='ANNULE').count()
    
    # Statistiques des abonnés
    total_abonnes = Abonne.objects.count()
    abonnes_actifs = Abonne.objects.filter(user__is_active=True).count()
    
    # Statistiques des commentaires
    total_commentaires = Commentaire.objects.count()
    commentaires_actifs = Commentaire.objects.filter(abonne__user__is_active=True).count()
    
    # Statistiques des notifications
    total_notifications = Notification.objects.count()
    notifications_envoyees = Notification.objects.filter(date_envoi__isnull=False).count()
    
    # Statistiques des catégories
    categories = CategorieEvenement.objects.annotate(
        nb_evenements=Count('evenements_cat'),
        nb_evenements_publies=Count('evenements_cat', filter=Q(evenements_cat__statut='PUBLIE'))
    )
    
    # Statistiques des événements par mois
    evenements_par_mois = Evenement.objects.annotate(
        mois=TruncMonth('date_debut')
    ).values('mois').annotate(
        total=Count('id'),
        publies=Count('id', filter=Q(statut='PUBLIE')),
        brouillons=Count('id', filter=Q(statut='BROUILLON')),
        annules=Count('id', filter=Q(statut='ANNULE'))
    ).order_by('mois')
    
    # Statistiques des abonnements par mois
    abonnements_par_mois = Abonne.objects.annotate(
        mois=TruncMonth('user__date_joined')
    ).values('mois').annotate(
        total=Count('user')
    ).order_by('mois')
    
    # Statistiques des commentaires par mois
    commentaires_par_mois = Commentaire.objects.annotate(
        mois=TruncMonth('date_commentaire')
    ).values('mois').annotate(
        total=Count('id')
    ).order_by('mois')
    
    # Statistiques des notifications par mois
    notifications_par_mois = Notification.objects.annotate(
        mois=TruncMonth('date_envoi')
    ).values('mois').annotate(
        total=Count('id')
    ).order_by('mois')
    
    context = {
        'total_evenements': total_evenements,
        'evenements_publies': evenements_publies,
        'evenements_brouillon': evenements_brouillon,
        'evenements_annules': evenements_annules,
        'total_abonnes': total_abonnes,
        'abonnes_actifs': abonnes_actifs,
        'total_commentaires': total_commentaires,
        'commentaires_actifs': commentaires_actifs,
        'total_notifications': total_notifications,
        'notifications_envoyees': notifications_envoyees,
        'categories': categories,
        'evenements_par_mois': list(evenements_par_mois),
        'abonnements_par_mois': list(abonnements_par_mois),
        'commentaires_par_mois': list(commentaires_par_mois),
        'notifications_par_mois': list(notifications_par_mois),
    }
    
    return render(request, 'GestionEvenement/communication/statistiques.html', context)

@login_required
@user_passes_test(lambda u: hasattr(u, "receptionniste") or is_admin_staff(u))
def rapport_journalier_view(request):
    today = timezone.now().date()
    
    # Récupération des données du jour
    evenements_jour = Evenement.objects.filter(
        date_debut__date=today
    ).order_by("date_debut")
    
    reservations_jour = Reservation.objects.filter(
        date_reservation__date=today
    ).order_by("-date_reservation")
    
    paiements_jour = Paiement.objects.filter(
        date_paiement__date=today
    ).order_by("-date_paiement")
    
    context = {
        "date": today,
        "evenements": evenements_jour,
        "reservations": reservations_jour,
        "paiements": paiements_jour,
        "total_entrees": reservations_jour.aggregate(total=Count('nombre_billets'))["total"] or 0,
        "total_recettes": paiements_jour.aggregate(total=Count('montant'))["total"] or 0,
    }
    
    return render(request, "GestionEvenement/rapports/rapport_journalier.html", context)

@login_required
def liste_reservations_view(request):
    reservations = Reservation.objects.all().order_by("-date_reservation")
    
    # Filtres
    statut = request.GET.get("statut")
    date_debut = request.GET.get("date_debut")
    date_fin = request.GET.get("date_fin")
    recherche = request.GET.get("recherche")
    
    if statut:
        reservations = reservations.filter(statut=statut)
    if date_debut:
        reservations = reservations.filter(date_reservation__gte=date_debut)
    if date_fin:
        reservations = reservations.filter(date_reservation__lte=date_fin)
    if recherche:
        reservations = reservations.filter(
            Q(utilisateur__first_name__icontains=recherche) |
            Q(utilisateur__last_name__icontains=recherche) |
            Q(evenement__nom__icontains=recherche)
        )
    
    # Pagination
    paginator = Paginator(reservations, 10)
    page = request.GET.get("page")
    reservations_page = paginator.get_page(page)
    
    return render(request, "GestionEvenement/reservations/liste_reservations.html", {
        "reservations": reservations_page
    })

@login_required
@user_passes_test(lambda u: hasattr(u, "receptionniste") or is_admin_staff(u))
def scanner_billet_view(request):
    if not hasattr(request.user, 'receptionniste'):
        messages.error(request, "Accès non autorisé.")
        return redirect('GestionEvenement:accueil')
    
    if request.method == "POST":
        code_billet = request.POST.get("code_billet")
        if not code_billet:
            messages.error(request, "Veuillez fournir un code de billet.")
            return render(request, "GestionEvenement/billets/scanner_billet.html")
        
        try:
            billet = Billet.objects.get(code=code_billet)
            
            # Vérification si le billet a déjà été utilisé
            if billet.utilise:
                messages.error(request, "Ce billet a déjà été utilisé.")
                return render(request, "GestionEvenement/billets/scanner_billet.html", {
                    "billet": billet,
                    "statut": "deja_utilise"
                })
            
            # Vérification si l'événement est bien aujourd'hui
            today = timezone.now().date()
            if billet.reservation.evenement.date_debut.date() != today:
                messages.error(request, "Ce billet n'est pas valide pour aujourd'hui.")
                return render(request, "GestionEvenement/billets/scanner_billet.html", {
                    "billet": billet,
                    "statut": "mauvaise_date"
                })
            
            # Validation du billet
            billet.utilise = True
            billet.date_utilisation = timezone.now()
            billet.receptionniste = request.user.receptionniste
            billet.save()
            
            messages.success(request, "Billet validé avec succès.")
            return render(request, "GestionEvenement/billets/scanner_billet.html", {
                "billet": billet,
                "statut": "valide"
            })
            
        except Billet.DoesNotExist:
            messages.error(request, "Billet non trouvé.")
            return render(request, "GestionEvenement/billets/scanner_billet.html", {
                "statut": "non_trouve"
            })
        except Exception as e:
            messages.error(request, f"Erreur lors de la validation du billet : {str(e)}")
            return render(request, "GestionEvenement/billets/scanner_billet.html")
    
    return render(request, "GestionEvenement/billets/scanner_billet.html")

def mes_reservations(request):
    reservations = Reservation.objects.filter(abonne__user=request.user).order_by('-date_reservation')
    return render(request, 'GestionEvenement/reservations/mes_reservations.html', {'reservations': reservations})

def receptionniste_dashboard(request):
    if not hasattr(request.user, 'receptionniste'):
        messages.error(request, "Accès non autorisé.")
        return redirect('GestionEvenement:accueil')
        
    context = {
        'reservations_aujourdhui_count': Reservation.objects.filter(date_reservation__date=timezone.now().date()).count(),
        'paiements_cash_attente_count': Paiement.objects.filter(methode_paiement='CASH', statut_paiement='EN_ATTENTE').count(),
        'dernieres_reservations': Reservation.objects.all().order_by('-date_reservation')[:10],
        'evenements_jour': Evenement.objects.filter(date_debut__date=timezone.now().date())
    }
    return render(request, 'GestionEvenement/dashboards/dashboard_receptionniste.html', context)

def liste_reservations(request):
    if not hasattr(request.user, 'receptionniste'):
        messages.error(request, "Accès non autorisé.")
        return redirect('GestionEvenement:accueil')
    
    reservations = Reservation.objects.all().order_by('-date_reservation')
    return render(request, 'GestionEvenement/reservations/liste_reservations.html', {'reservations': reservations})

def detail_reservation(request, pk):
    if not hasattr(request.user, 'receptionniste'):
        messages.error(request, "Accès non autorisé.")
        return redirect('GestionEvenement:accueil')
    
    reservation = get_object_or_404(Reservation, pk=pk)
    return render(request, 'GestionEvenement/reservations/detail_reservation.html', {'reservation': reservation})

def liste_rapports(request):
    if not hasattr(request.user, 'receptionniste'):
        messages.error(request, "Accès non autorisé.")
        return redirect('GestionEvenement:accueil')
    
    return render(request, 'GestionEvenement/rapports/liste_rapports.html')

def liste_paiements_cash(request):
    if not hasattr(request.user, 'receptionniste'):
        messages.error(request, "Accès non autorisé.")
        return redirect('GestionEvenement:accueil')
    
    paiements = Paiement.objects.filter(methode_paiement='CASH', statut_paiement='EN_ATTENTE')
    return render(request, 'GestionEvenement/paiements/liste_paiements_cash.html', {'paiements': paiements})

def scanner_billets(request):
    if not hasattr(request.user, 'receptionniste'):
        messages.error(request, "Accès non autorisé.")
        return redirect('GestionEvenement:accueil')
    
    return render(request, 'GestionEvenement/billets/scanner_billets.html')

def valider_paiement(request, pk):
    if not hasattr(request.user, 'receptionniste'):
        messages.error(request, "Accès non autorisé.")
        return redirect('GestionEvenement:accueil')
    
    paiement = get_object_or_404(Paiement, pk=pk)
    paiement.statut_paiement = 'REUSSI'
    paiement.date_validation = timezone.now()
    paiement.receptionniste = request.user.receptionniste
    paiement.save()
    
    # Mise à jour du statut de la réservation
    reservation = paiement.reservation
    reservation.statut_reservation = 'CONFIRMEE'
    reservation.save()
    
    messages.success(request, "Paiement validé avec succès.")
    return redirect('GestionEvenement:liste_paiements_cash')

def imprimer_reservation(request, pk):
    if not hasattr(request.user, 'receptionniste'):
        messages.error(request, "Accès non autorisé.")
        return redirect('GestionEvenement:accueil')
    
    reservation = get_object_or_404(Reservation, pk=pk)
    return render(request, 'GestionEvenement/reservations/imprimer_reservation.html', {'reservation': reservation})

def recherche_avancee(request):
    if not hasattr(request.user, 'receptionniste'):
        messages.error(request, "Accès non autorisé.")
        return redirect('GestionEvenement:accueil')
    
    return render(request, 'GestionEvenement/recherche/recherche_avancee.html')

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedeprogrammation") or hasattr(u, "chargedecommunication") or is_admin_staff(u))
def liste_evenements_admin(request):
    """Vue pour afficher la liste des événements pour l'administrateur"""
    statut = request.GET.get('statut', None)
    evenements = Evenement.objects.all().order_by('-date_debut')
    
    if statut:
        evenements = evenements.filter(statut=statut)
    
    # Ajout des informations sur les places disponibles
    for evenement in evenements:
        evenement.places_disponibles = evenement.get_places_disponibles()
    
    context = {
        'evenements': evenements,
        'statut_actuel': statut,
        'est_charge_programmation': hasattr(request.user, 'chargedeprogrammation'),
        'est_charge_communication': hasattr(request.user, 'chargedecommunication')
    }
    return render(request, 'GestionEvenement/evenements/liste_evenements_admin.html', context)

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedecommunication") or is_admin_staff(u))
def gestion_notifications(request):
    notifications = Notification.objects.all().order_by('-date_envoi')
    return render(request, 'GestionEvenement/notifications/gestion_notifications.html', {'notifications': notifications})

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedecommunication") or is_admin_staff(u))
def historique_notifications(request):
    notifications = Notification.objects.all().order_by('-date_envoi')
    return render(request, 'GestionEvenement/notifications/historique_notifications.html', {'notifications': notifications})

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedecommunication") or is_admin_staff(u))
def gestion_abonnes(request):
    abonnes = Abonne.objects.all().order_by('user__last_name', 'user__first_name')
    return render(request, 'GestionEvenement/abonnes/gestion_abonnes.html', {'abonnes': abonnes})

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedecommunication") or is_admin_staff(u))
def notification_massive(request):
    if request.method == 'POST':
        titre = request.POST.get('titre')
        contenu = request.POST.get('contenu')
        destinataires = request.POST.getlist('destinataires')
        
        if not all([titre, contenu, destinataires]):
            messages.error(request, "Tous les champs sont requis.")
            return render(request, 'GestionEvenement/notifications/notification_massive.html')
        
        try:
            notification = Notification.objects.create(
                titre=titre,
                contenu=contenu,
                expediteur=request.user.chargedecommunication
            )
            notification.destinataires.set(destinataires)
            messages.success(request, "La notification a été envoyée avec succès.")
            return redirect('GestionEvenement:dashboard_communication')
        except Exception as e:
            messages.error(request, f"Erreur lors de l'envoi : {str(e)}")
    
    abonnes = Abonne.objects.filter(user__is_active=True)
    return render(request, 'GestionEvenement/notifications/notification_massive.html', {'abonnes': abonnes})

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedecommunication") or is_admin_staff(u))
def creer_modele_notification(request):
    if request.method == 'POST':
        nom = request.POST.get('nom')
        contenu = request.POST.get('contenu')
        
        if not all([nom, contenu]):
            messages.error(request, "Tous les champs sont requis.")
            return render(request, 'GestionEvenement/notifications/creer_modele.html')
        
        try:
            ModeleNotification.objects.create(
                nom=nom,
                contenu=contenu,
                createur=request.user.chargedecommunication
            )
            messages.success(request, "Le modèle a été créé avec succès.")
            return redirect('GestionEvenement:gestion_notifications')
        except Exception as e:
            messages.error(request, f"Erreur lors de la création : {str(e)}")
    
    return render(request, 'GestionEvenement/notifications/creer_modele.html')

# Vues pour le dashboard programmation
@login_required
@user_passes_test(lambda u: hasattr(u, "chargedeprogrammation") or is_admin_staff(u))
def evenements_archives(request):
    """Vue pour afficher les événements archivés"""
    evenements = Evenement.objects.filter(
        date_fin__lt=timezone.now()
    ).order_by('-date_fin')
    
    context = {
        'evenements': evenements
    }
    return render(request, 'GestionEvenement/evenements/evenements_archives.html', context)

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedeprogrammation") or is_admin_staff(u))
def gestion_categories(request):
    """Vue pour gérer les catégories d'événements"""
    if request.method == 'POST':
        try:
            categorie = CategorieEvenement(
                nom_categorie=request.POST['nom'],
                description=request.POST.get('description', '')
            )
            categorie.save()
            messages.success(request, 'Catégorie créée avec succès.')
        except Exception as e:
            messages.error(request, f'Erreur lors de la création : {str(e)}')
        return redirect('GestionEvenement:gestion_categories')
    
    categories = CategorieEvenement.objects.all()
    
    # Préparation des statistiques pour les graphiques
    categories_stats = []
    for categorie in categories:
        stats = {
            'name': categorie.nom_categorie,
            'count': categorie.evenements_cat.count(),
            'published': categorie.evenements_cat.filter(statut='PUBLIE').count(),
            'draft': categorie.evenements_cat.filter(statut='BROUILLON').count(),
            'cancelled': categorie.evenements_cat.filter(statut='ANNULE').count()
        }
        categories_stats.append(stats)
    
    context = {
        'categories': categories,
        'categories_stats': categories_stats
    }
    return render(request, 'GestionEvenement/categories/gestion_categories.html', context)

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedeprogrammation") or is_admin_staff(u))
def statistiques_evenements(request):
    """Vue pour afficher les statistiques des événements"""
    # Statistiques par catégorie
    categories = CategorieEvenement.objects.all()
    stats_categories = []
    
    for categorie in categories:
        evenements = Evenement.objects.filter(categorie=categorie)
        stats = {
            'nom_categorie': categorie.nom_categorie,
            'nombre_evenements': evenements.count(),
            'evenements_publies': evenements.filter(statut='PUBLIE').count(),
            'evenements_brouillons': evenements.filter(statut='BROUILLON').count(),
            'evenements_annules': evenements.filter(statut='ANNULE').count()
        }
        stats_categories.append(stats)

    # Statistiques mensuelles
    aujourd_hui = timezone.now()
    six_mois = aujourd_hui - timedelta(days=180)
    
    evenements = Evenement.objects.filter(
        date_debut__gte=six_mois
    ).order_by('date_debut')
    
    stats_mensuelles = {}
    for evenement in evenements:
        mois_cle = evenement.date_debut.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if mois_cle not in stats_mensuelles:
            stats_mensuelles[mois_cle] = {
                'mois': mois_cle,
                'total': 0,
                'publies': 0,
                'brouillons': 0,
                'annules': 0
            }
        stats_mensuelles[mois_cle]['total'] += 1
        if evenement.statut == 'PUBLIE':
            stats_mensuelles[mois_cle]['publies'] += 1
        elif evenement.statut == 'BROUILLON':
            stats_mensuelles[mois_cle]['brouillons'] += 1
        elif evenement.statut == 'ANNULE':
            stats_mensuelles[mois_cle]['annules'] += 1
    
    stats_mensuelles = sorted(stats_mensuelles.values(), key=lambda x: x['mois'], reverse=True)

    # Statistiques globales
    total_evenements = Evenement.objects.count()
    evenements_publies = Evenement.objects.filter(statut='PUBLIE').count()
    evenements_brouillons = Evenement.objects.filter(statut='BROUILLON').count()
    evenements_annules = Evenement.objects.filter(statut='ANNULE').count()

    # Données pour les graphiques
    categories_stats = [{
        'name': cat['nom_categorie'],
        'count': cat['nombre_evenements'],
        'published': cat['evenements_publies'],
        'draft': cat['evenements_brouillons'],
        'cancelled': cat['evenements_annules']
    } for cat in stats_categories]

    monthly_stats = [{
        'mois': stat['mois'].strftime('%B %Y'),
        'total': stat['total'],
        'published': stat['publies'],
        'draft': stat['brouillons'],
        'cancelled': stat['annules']
    } for stat in stats_mensuelles]

    context = {
        'stats_categories': stats_categories,
        'stats_mensuelles': stats_mensuelles,
        'total_evenements': total_evenements,
        'evenements_publies': evenements_publies,
        'evenements_brouillons': evenements_brouillons,
        'evenements_annules': evenements_annules,
        'categories_stats': json.dumps(categories_stats),
        'monthly_stats': json.dumps(monthly_stats)
    }
    
    return render(request, 'GestionEvenement/statistiques/statistiques_evenements.html', context)

@login_required
def profil_personnel(request):
    """Vue pour afficher et modifier le profil personnel"""
    if request.method == 'POST':
        # Mise à jour des informations de base
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name = request.POST.get('last_name', request.user.last_name)
        request.user.email = request.POST.get('email', request.user.email)
        
        # Mise à jour du mot de passe si fourni
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        if current_password and new_password:
            if request.user.check_password(current_password):
                request.user.set_password(new_password)
                messages.success(request, 'Votre mot de passe a été mis à jour.')
            else:
                messages.error(request, 'Le mot de passe actuel est incorrect.')
        
        request.user.save()
        messages.success(request, 'Votre profil a été mis à jour avec succès.')
        return redirect('GestionEvenement:profil_personnel')
    
    context = {
        'user': request.user
    }
    return render(request, 'GestionEvenement/profil/profil_personnel.html', context)

@login_required
@abonne_required
def evenements_favoris(request):
    favoris = request.user.abonne_profile_new.evenements_favoris.all()
    return render(request, 'GestionEvenement/evenements/favoris.html', {'favoris': favoris})

@login_required
@abonne_required
def mes_notifications(request):
    notifications = Notification.objects.filter(destinataire=request.user).order_by('-date_envoi')
    return render(request, 'GestionEvenement/notifications/mes_notifications.html', {'notifications': notifications})

@login_required
@abonne_required
def mes_paiements(request):
    paiements = Paiement.objects.filter(reservation__abonne=request.user.abonne_profile_new).order_by('-date')
    return render(request, 'GestionEvenement/paiements/mes_paiements.html', {'paiements': paiements})

@login_required
@abonne_required
def ajouter_carte(request):
    if request.method == "POST":
        # Logique pour ajouter une carte
        messages.success(request, "Votre carte a été ajoutée avec succès.")
        return redirect('GestionEvenement:mes_paiements')
    return render(request, 'GestionEvenement/paiements/ajouter_carte.html')

@login_required
def recherche_evenements(request):
    query = request.GET.get('q', '')
    evenements = Evenement.objects.filter(
        Q(titre__icontains=query) | 
        Q(description__icontains=query) |
        Q(categorie__nom__icontains=query)
    ).filter(statut='PUBLIE')
    return render(request, 'GestionEvenement/evenements/recherche.html', {'evenements': evenements, 'query': query})

@login_required
@abonne_required
def telecharger_billet_pdf(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, abonne=request.user.abonne_profile_new)
    # Logique pour générer le PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="billet_{reservation.id}.pdf"'
    # Utiliser ReportLab pour générer le PDF
    return response

@login_required
@abonne_required
def envoyer_billet_email(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, abonne=request.user.abonne_profile_new)
    # Logique pour envoyer le billet par email
    messages.success(request, "Le billet a été envoyé à votre adresse email.")
    return redirect('GestionEvenement:mes_reservations')

@login_required
@abonne_required
def ajouter_calendrier(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, abonne=request.user.abonne_profile_new)
    # Logique pour générer le fichier iCal
    response = HttpResponse(content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="evenement_{reservation.evenement.id}.ics"'
    # Générer le fichier iCal
    return response

@login_required
@abonne_required
def mes_billets(request):
    # Récupérer toutes les réservations de l'abonné qui ont été payées
    reservations = Reservation.objects.filter(
        abonne=request.user.abonne_profile_new,
        statut='PAYE'
    ).order_by('-date_reservation')
    
    # Compter les billets disponibles
    billets_count = reservations.count()
    
    # Récupérer les événements à venir avec des billets
    evenements_a_venir = Evenement.objects.filter(
        reservations__in=reservations,
        date_debut__gt=timezone.now()
    ).distinct()
    
    context = {
        'reservations': reservations,
        'billets_count': billets_count,
        'evenements_a_venir': evenements_a_venir
    }
    
    return render(request, 'GestionEvenement/billets/mes_billets.html', context)

@login_required
def modifier_categorie(request, pk):
    """Vue pour modifier une catégorie"""
    categorie = get_object_or_404(CategorieEvenement, pk=pk)
    if request.method == 'POST':
        try:
            categorie.nom_categorie = request.POST['nom']
            categorie.description = request.POST.get('description', '')
            categorie.save()
            messages.success(request, 'Catégorie modifiée avec succès.')
        except Exception as e:
            messages.error(request, f'Erreur lors de la modification : {str(e)}')
    return redirect('GestionEvenement:gestion_categories')

@login_required
def supprimer_categorie(request, pk):
    """Vue pour supprimer une catégorie"""
    categorie = get_object_or_404(CategorieEvenement, pk=pk)
    if request.method == 'POST':
        try:
            if categorie.evenements_cat.exists():
                messages.error(request, 'Impossible de supprimer une catégorie contenant des événements.')
            else:
                categorie.delete()
                messages.success(request, 'Catégorie supprimée avec succès.')
        except Exception as e:
            messages.error(request, f'Erreur lors de la suppression : {str(e)}')
    return redirect('GestionEvenement:gestion_categories')

def accueil_view(request):
    """Vue pour la page d'accueil"""
    evenements_a_venir = Evenement.objects.filter(
        statut='PUBLIE',
        date_debut__gt=timezone.now()
    ).order_by('date_debut')[:6]
    
    evenements_en_cours = Evenement.objects.filter(
        statut='PUBLIE',
        date_debut__lte=timezone.now(),
        date_fin__gte=timezone.now()
    )
    
    categories = CategorieEvenement.objects.all()
    
    context = {
        'evenements_a_venir': evenements_a_venir,
        'evenements_en_cours': evenements_en_cours,
        'categories': categories
    }
    return render(request, 'GestionEvenement/accueil.html', context)

def liste_evenements_view(request):
    """Vue pour la liste publique des événements"""
    evenements = Evenement.objects.filter(statut='PUBLIE')
    categorie_id = request.GET.get('categorie')
    recherche = request.GET.get('recherche')
    
    if categorie_id:
        evenements = evenements.filter(categorie_id=categorie_id)
    
    if recherche:
        evenements = evenements.filter(
            Q(nom__icontains=recherche) |
            Q(description__icontains=recherche)
        )
    
    categories = CategorieEvenement.objects.all()
    
    context = {
        'evenements': evenements,
        'categories': categories,
        'categorie_selectionnee': categorie_id,
        'recherche': recherche
    }
    return render(request, 'GestionEvenement/evenements/liste_evenements.html', context)

@login_required
def mon_profil(request):
    user = request.user
    context = {
        'user': user,
        'profil': None
    }
    
    # Récupérer le profil spécifique selon le type d'utilisateur
    if hasattr(user, 'chargedeprogrammation'):
        context['profil'] = user.chargedeprogrammation
    elif hasattr(user, 'chargedecommunication'):
        context['profil'] = user.chargedecommunication
    elif hasattr(user, 'receptionniste'):
        context['profil'] = user.receptionniste
    elif hasattr(user, 'abonne_profile_new'):
        context['profil'] = user.abonne_profile_new
    
    if request.method == 'POST':
        # Mise à jour des informations de base
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        
        # Mise à jour du mot de passe si fourni
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        if current_password and new_password:
            if user.check_password(current_password):
                user.set_password(new_password)
                messages.success(request, 'Votre mot de passe a été mis à jour.')
            else:
                messages.error(request, 'Le mot de passe actuel est incorrect.')
        
        user.save()
        messages.success(request, 'Votre profil a été mis à jour avec succès.')
        return redirect('GestionEvenement:mon_profil')
    
    return render(request, 'GestionEvenement/profil/mon_profil.html', context)

@login_required
@user_passes_test(lambda u: hasattr(u, "chargedecommunication") or is_admin_staff(u))
def supprimer_notification(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id)
    if request.method == "POST":
        notification.delete()
        messages.success(request, "Notification supprimée avec succès.")
        return redirect('GestionEvenement:gestion_notifications')
    return render(request, 'GestionEvenement/notifications/confirmer_suppression.html', {'notification': notification})


