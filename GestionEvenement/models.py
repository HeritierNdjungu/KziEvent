from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Profil Utilisateur pour étendre le modèle User de Django
class ProfilUtilisateur(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil')
    photo = models.ImageField(upload_to='photos_profil/', null=True, blank=True)
    # D'autres champs communs pourraient être ajoutés ici si nécessaire

    def __str__(self):
        return self.user.username

# Modèle Adresse (lié à Utilisateur)
class Adresse(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='adresse_user', null=True, blank=True)
    rue = models.CharField(max_length=255)
    numero = models.CharField(max_length=20, blank=True, null=True)
    ville = models.CharField(max_length=100)
    code_postal = models.CharField(max_length=20)
    pays = models.CharField(max_length=100, default='République Démocratique du Congo')

    def __str__(self):
        return f"{self.numero} {self.rue}, {self.ville}"

# Modèles pour les rôles spécifiques
class Abonne(models.Model):
    TYPE_ABONNE_CHOICES = [
        ('SIMPLE', 'Simple'),
        ('RESPONSABLE_ECOLE', 'Responsable d\_école'),
        ('ENTREPRISE', 'Entreprise'),
        ('AUTRE', 'Autre'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE,primary_key=True, related_name='abonne_profile_new') # Renommé related_name
    type_abonne = models.CharField(max_length=50, choices=TYPE_ABONNE_CHOICES, default='SIMPLE')
    raison_sociale = models.CharField(max_length=255, blank=True, null=True, help_text="Raison sociale si applicable (pour écoles, entreprises)")
    preferences_notifications = models.TextField(blank=True, help_text="Préférences de notification de l'abonné (ex: format JSON ou champs spécifiques)")
    evenements_interesses = models.ManyToManyField('Evenement', blank=True, related_name='abonnes_interesses_new') # Renommé related_name

    def __str__(self):
        return self.user.username

class PersonnelBase(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    matricule = models.CharField(max_length=50, unique=True)
    specialite = models.CharField(max_length=150)

    class Meta:
        abstract = True # Pour ne pas créer de table pour PersonnelBase

    def __str__(self):
        return f"{self.user.username} ({self.matricule})"

class ChargeDeProgrammation(PersonnelBase):
    # related_name pour user sera charge_de_programmation_profile implicitement
    pass

class ChargeDeCommunication(PersonnelBase):
    # related_name pour user sera charge_de_communication_profile implicitement
    pass

class Receptionniste(PersonnelBase):
    # related_name pour user sera receptionniste_profile implicitement
    pass 

# Modèle CategorieEvenement
class CategorieEvenement(models.Model):
    nom_categorie = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.nom_categorie

# Modèle Calendrier
class Calendrier(models.Model):
    nom_calendrier = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, null=True)
    # Les relations ManyToMany seront définies sur Evenement ou gérées par permissions

    def __str__(self):
        return self.nom_calendrier

# Modèle Evenement
class Evenement(models.Model):
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('PUBLIE', 'Publié'),
        ('ANNULE', 'Annulé'),
        ('TERMINE', 'Terminé'),
    ]
    nom = models.CharField(max_length=200)
    description = models.TextField()
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField()
    lieu = models.CharField(max_length=255)
    capacite = models.PositiveIntegerField()
    prix = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    image = models.ImageField(upload_to='evenements/', null=True, blank=True)
    categorie = models.ForeignKey(CategorieEvenement, on_delete=models.SET_NULL, null=True, blank=True, related_name='evenements_cat')
    calendrier = models.ForeignKey(Calendrier, on_delete=models.SET_NULL, null=True, blank=True, related_name='evenements_cal')
    
    # Qui a créé/géré l'événement
    responsable_programmation = models.ForeignKey(ChargeDeProgrammation, on_delete=models.SET_NULL, null=True, blank=True, related_name='evenements_programmes')
    responsable_communication = models.ForeignKey(ChargeDeCommunication, on_delete=models.SET_NULL, null=True, blank=True, related_name='evenements_communiques')

    def __str__(self):
        return self.nom

    def get_places_disponibles(self):
        reservations_valides = self.reservations_evt.filter(statut_reservation__in=['CONFIRMEE', 'PAYEE_CASH_ATTENTE_VALIDATION']).aggregate(total_places=models.Sum('nombre_places'))['total_places'] or 0
        return self.capacite - reservations_valides

# Modèle Reservation
class Reservation(models.Model):
    STATUT_RESERVATION_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('CONFIRMEE', 'Confirmée'),
        ('ANNULEE', 'Annulée'),
        ('PAYEE_CASH_ATTENTE_VALIDATION', 'Payée cash (attente validation)'),
    ]
    evenement = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name='reservations_evt') # Renommé related_name
    abonne = models.ForeignKey(Abonne, on_delete=models.CASCADE, related_name='reservations_abonne') # Renommé related_name
    date_reservation = models.DateTimeField(auto_now_add=True)
    nombre_places = models.PositiveIntegerField(default=1)
    statut_reservation = models.CharField(max_length=30, choices=STATUT_RESERVATION_CHOICES, default='EN_ATTENTE')
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Réservation pour {self.evenement.nom} par {self.abonne.user.username}"

# Modèle Commentaire
class Commentaire(models.Model):
    evenement = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name='commentaires_evt')
    abonne = models.ForeignKey(Abonne, on_delete=models.CASCADE, related_name='commentaires_abonne')
    texte = models.TextField()
    date_commentaire = models.DateTimeField(auto_now_add=True)
    note = models.PositiveIntegerField(null=True, blank=True, help_text="Note de 1 à 5 étoiles, optionnelle")
    modere = models.BooleanField(default=False, help_text="Indique si le commentaire a été modéré")

    def __str__(self):
        return f"Commentaire de {self.abonne.user.username} sur {self.evenement.nom}"

# Modèle Paiement
class Paiement(models.Model):
    METHODE_PAIEMENT_CHOICES = [
        ('EN_LIGNE', 'En ligne'),
        ('CASH', 'Cash'),
    ]
    STATUT_PAIEMENT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('REUSSI', 'Réussi'),
        ('ECHOUE', 'Échoué'),
    ]
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name='paiement_res') # Renommé related_name
    date_paiement = models.DateTimeField(default=timezone.now)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    methode_paiement = models.CharField(max_length=20, choices=METHODE_PAIEMENT_CHOICES)
    statut_paiement = models.CharField(max_length=20, choices=STATUT_PAIEMENT_CHOICES, default='EN_ATTENTE')
    reference_transaction = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Paiement pour la réservation {self.reservation.id} - Statut: {self.statut_paiement}"

# Modèle Billet
class Billet(models.Model):
    paiement = models.ForeignKey(Paiement, on_delete=models.CASCADE, related_name='billets_paiement') # Renommé related_name
    code_unique = models.CharField(max_length=100, unique=True)
    type_billet = models.CharField(max_length=50, blank=True, help_text="Ex: Adulte, Enfant, VIP")
    nom_detenteur = models.CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return f"Billet {self.code_unique} pour paiement {self.paiement.id}"

# Signal pour créer/mettre à jour ProfilUtilisateur lors de la création/modification de User
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        ProfilUtilisateur.objects.create(user=instance)
    else:
        # Vérifier si un profil existe déjà
        try:
            # Tenter de récupérer le profil existant
            profile = ProfilUtilisateur.objects.get(user=instance)
            profile.save()
        except ProfilUtilisateur.DoesNotExist:
            # Si aucun profil n'existe, en créer un nouveau
            ProfilUtilisateur.objects.create(user=instance)
        except ProfilUtilisateur.MultipleObjectsReturned:
            # En cas de profils multiples, garder le premier et supprimer les autres
            profiles = ProfilUtilisateur.objects.filter(user=instance)
            first_profile = profiles.first()
            profiles.exclude(id=first_profile.id).delete()
            first_profile.save()

class Notification(models.Model):
    titre = models.CharField(max_length=200)
    contenu = models.TextField()
    date_envoi = models.DateTimeField(auto_now_add=True)
    expediteur = models.ForeignKey(ChargeDeCommunication, on_delete=models.CASCADE)
    destinataires = models.ManyToManyField(Abonne)
    lu = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date_envoi']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.titre} - {self.date_envoi.strftime('%d/%m/%Y %H:%M')}"

    @property
    def destinataires_count(self):
        return self.destinataires.count()

class ModeleNotification(models.Model):
    nom = models.CharField(max_length=100)
    contenu = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)
    createur = models.ForeignKey(ChargeDeCommunication, on_delete=models.CASCADE)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Modèle de notification"
        verbose_name_plural = "Modèles de notification"

    def __str__(self):
        return self.nom

