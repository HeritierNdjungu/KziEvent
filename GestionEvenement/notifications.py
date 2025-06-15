from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

# Modèle pour les notifications
class Notification(models.Model):
    TYPE_CHOICES = [
        ('NOUVEL_EVENEMENT', 'Nouvel événement'),
        ('MODIFICATION_EVENEMENT', 'Modification d\'événement'),
        ('ANNULATION_EVENEMENT', 'Annulation d\'événement'),
        ('RAPPEL_EVENEMENT', 'Rappel d\'événement'),
        ('INFORMATION_GENERALE', 'Information générale'),
    ]
    
    titre = models.CharField(max_length=200)
    contenu = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)
    type_notification = models.CharField(max_length=50, choices=TYPE_CHOICES)
    evenement = models.ForeignKey('Evenement', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    
    def __str__(self):
        return self.titre

# Modèle pour les notifications des abonnés
class NotificationAbonne(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='notifications_abonnes')
    abonne = models.ForeignKey('Abonne', on_delete=models.CASCADE, related_name='notifications_recues')
    lu = models.BooleanField(default=False)
    date_lecture = models.DateTimeField(null=True, blank=True)
    
    def marquer_comme_lu(self):
        self.lu = True
        self.date_lecture = timezone.now()
        self.save()
    
    def __str__(self):
        return f"{self.notification.titre} pour {self.abonne.user.username}"

# Signal pour envoyer des notifications lors de la publication d'un événement
@receiver(post_save, sender='GestionEvenement.Evenement')
def envoyer_notification_evenement(sender, instance, created, **kwargs):
    # Vérifier si l'événement vient d'être publié
    if instance.statut == 'PUBLIE' and (created or instance._original_statut != 'PUBLIE'):
        # Créer une notification
        notification = Notification.objects.create(
            titre=f"Nouvel événement : {instance.nom}",
            contenu=f"Un nouvel événement '{instance.nom}' a été publié. Il aura lieu le {instance.date_debut.strftime('%d/%m/%Y à %H:%M')} à {instance.lieu}.",
            type_notification='NOUVEL_EVENEMENT',
            evenement=instance
        )
        
        # Envoyer la notification à tous les abonnés
        abonnes = sender.objects.get_model('Abonne').objects.all()
        for abonne in abonnes:
            # Créer une notification pour l'abonné
            NotificationAbonne.objects.create(
                notification=notification,
                abonne=abonne
            )
            
            # Envoyer un email si l'abonné a activé les notifications par email
            if abonne.preferences_notifications and 'email' in abonne.preferences_notifications:
                try:
                    # Préparer le contenu de l'email
                    html_message = render_to_string('GestionEvenement/emails/notification_evenement.html', {
                        'abonne': abonne,
                        'evenement': instance,
                        'notification': notification
                    })
                    
                    # Envoyer l'email
                    send_mail(
                        subject=notification.titre,
                        message=notification.contenu,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[abonne.user.email],
                        html_message=html_message,
                        fail_silently=True
                    )
                except Exception as e:
                    # Gérer les erreurs d'envoi d'email
                    print(f"Erreur lors de l'envoi de l'email à {abonne.user.email}: {str(e)}")
