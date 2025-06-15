from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import (
    ProfilUtilisateur, Adresse, 
    Abonne, ChargeDeProgrammation, ChargeDeCommunication, Receptionniste,
    CategorieEvenement, Calendrier, Evenement, Reservation, Commentaire, Paiement, Billet
)

# Pour afficher ProfilUtilisateur dans l'admin User
class ProfilUtilisateurInline(admin.StackedInline):
    model = ProfilUtilisateur
    can_delete = False
    verbose_name_plural = "Profils Utilisateur"
    fk_name = "user"

class AdresseInline(admin.StackedInline):
    model = Adresse
    can_delete = False
    verbose_name_plural = "Adresses"
    fk_name = "user"

class UserAdmin(BaseUserAdmin):
    inlines = (ProfilUtilisateurInline, AdresseInline,)
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "get_user_role", # Méthode à ajouter au modèle User ou ici
    )

    def get_user_role(self, instance):
        if hasattr(instance, "abonne_profile_new"): return "Abonné"
        if hasattr(instance, "chargedeprogrammation"): return "Chargé de Programmation"
        if hasattr(instance, "chargedecommunication"): return "Chargé de Communication"
        if hasattr(instance, "receptionniste"): return "Réceptionniste"
        if instance.is_superuser: return "Super Admin"
        if instance.is_staff: return "Admin (Staff)"
        return "Utilisateur Standard"
    get_user_role.short_description = "Rôle"

# Désenregistrer l'admin User par défaut et réenregistrer avec notre UserAdmin personnalisé
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Enregistrement des profils spécifiques
@admin.register(Abonne)
class AbonneAdmin(admin.ModelAdmin):
    list_display = ["user", "type_abonne", "raison_sociale"]
    search_fields = ["user__username", "user__email", "raison_sociale"]
    list_filter = ["type_abonne"]

@admin.register(ChargeDeProgrammation)
class ChargeDeProgrammationAdmin(admin.ModelAdmin):
    list_display = ["user", "matricule", "specialite"]
    search_fields = ["user__username", "matricule", "specialite"]

@admin.register(ChargeDeCommunication)
class ChargeDeCommunicationAdmin(admin.ModelAdmin):
    list_display = ["user", "matricule", "specialite"]
    search_fields = ["user__username", "matricule", "specialite"]

@admin.register(Receptionniste)
class ReceptionnisteAdmin(admin.ModelAdmin):
    list_display = ["user", "matricule", "specialite"]
    search_fields = ["user__username", "matricule", "specialite"]


admin.site.register(CategorieEvenement)
admin.site.register(Calendrier)
admin.site.register(Paiement)
admin.site.register(Billet)

@admin.register(Evenement)
class EvenementAdmin(admin.ModelAdmin):
    list_display = (
        "nom", "categorie", "date_debut", "date_fin", "lieu", "statut", "prix", "capacite", "get_places_disponibles"
    )
    list_filter = ("statut", "categorie", "date_debut", "lieu")
    search_fields = ("nom", "description", "lieu")
    # readonly_fields = (
    #     "get_places_disponibles",
    # ) # Décommenter si la méthode est coûteuse ou purement informative

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "evenement", "abonne", "date_reservation", "nombre_places", "statut_reservation", "montant_total")
    list_filter = ("statut_reservation", "evenement", "abonne", "date_reservation")
    search_fields = ("evenement__nom", "abonne__user__username")

@admin.register(Commentaire)
class CommentaireAdmin(admin.ModelAdmin):
    list_display = ("id", "evenement", "abonne", "date_commentaire", "note")
    list_filter = ("evenement", "abonne", "date_commentaire", "note")
    search_fields = ("texte", "evenement__nom", "abonne__user__username")

