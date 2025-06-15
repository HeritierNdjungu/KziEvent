from django.urls import path
from . import views
from .views import profil_abonne
# Noms d_URL pour la redirection et la navigation
app_name = 'GestionEvenement'

urlpatterns = [
    # Pages publiques
    path('', views.home_view, name='accueil'),
    path('evenements/', views.liste_evenements_view, name='liste_evenements'),
    path('evenements/<int:pk>/', views.evenement_detail_view, name='evenement_detail'),
    
    # Authentification
    path('connexion/', views.connexion_view, name='connexion'),
    path('inscription/', views.inscription_view, name='inscription'),
    path('deconnexion/', views.deconnexion_view, name='deconnexion'),
    
    # Dashboard et redirection
    path('dashboard/', views.dispatch_dashboard, name='dispatch_dashboard'),
    path('dashboard/programmation/', views.dashboard_programmation, name='dashboard_programmation'),
    path('dashboard/communication/', views.dashboard_communication, name='dashboard_communication'),
    path('dashboard/receptionniste/', views.dashboard_receptionniste_view, name='dashboard_receptionniste'),
    path('dashboard/abonne/', views.dashboard_abonne_view, name='dashboard_abonne'),
    
    # Gestion des événements
    path('evenements/liste-admin/', views.liste_evenements_admin, name='liste_evenements_admin'),
    path('evenements/archives/', views.evenements_archives, name='evenements_archives'),
    path('evenements/categories/', views.gestion_categories, name='gestion_categories'),
    path('evenements/statistiques/', views.statistiques_evenements, name='statistiques_evenements'),
    
    
    # CRUD Événements
    path('evenements/creer/', views.creer_evenement_view, name='creer_evenement'),
    path('evenements/<int:pk>/modifier/', views.modifier_evenement_view, name='modifier_evenement'),
    path('evenements/<int:pk>/supprimer/', views.supprimer_evenement_view, name='supprimer_evenement'),
    path('evenements/<int:pk>/publier/', views.publier_evenement_view, name='publier_evenement'),
    
    # Gestion des catégories
    path('categories/modifier/<int:pk>/', views.modifier_categorie, name='modifier_categorie'),
    path('categories/supprimer/<int:pk>/', views.supprimer_categorie, name='supprimer_categorie'),
    path('categories/ajouter/', views.ajouter_categorie, name='ajouter_categorie'),
    
    # Profil
    path('profil/abonne/', views.profil_abonne, name='profil_abonne'),
    path('profil/personnel/', views.profil_personnel, name='profil_personnel'),
    path('profil/mon-profil/', views.mon_profil, name='mon_profil'),
    
    # Rapports
    path('rapports/journalier/', views.rapport_journalier_view, name='rapport_journalier'),

    # Gestion des notifications et communication
    path('notifications/gestion/', views.gestion_notifications, name='gestion_notifications'),
    path('notifications/historique/', views.historique_notifications, name='historique_notifications'),
    path('notifications/massive/', views.notification_massive, name='notification_massive'),
    path('notifications/modele/creer/', views.creer_modele_notification, name='creer_modele_notification'),
    path('communication/statistiques/', views.statistiques_communication, name='statistiques_communication'),
    path('abonnes/gestion/', views.gestion_abonnes, name='gestion_abonnes'),
    path('reservations/mes/', views.mes_reservations, name='mes_reservations'),
    path('evenements/favoris/', views.evenements_favoris, name='evenements_favoris'),
    path('paiements/mes/', views.mes_paiements, name='mes_paiements'),
    path('notifications/mes/', views.mes_notifications, name='mes_notifications'),
    path('billets/mes/', views.mes_billets, name='mes_billets'),
    path('carte/ajouter/', views.ajouter_carte, name='ajouter_carte'),
    path('evenements/recherche/', views.recherche_evenements_api, name='recherche_evenements'),
    path('notifications/supprimer/<int:notification_id>/', views.supprimer_notification, name='supprimer_notification'),
]

