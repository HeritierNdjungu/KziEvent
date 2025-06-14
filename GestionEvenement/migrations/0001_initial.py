# Generated by Django 5.2.1 on 2025-05-27 13:08

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Abonne',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='abonne_profile_new', serialize=False, to=settings.AUTH_USER_MODEL)),
                ('type_abonne', models.CharField(choices=[('SIMPLE', 'Simple'), ('RESPONSABLE_ECOLE', 'Responsable d\\_école'), ('ENTREPRISE', 'Entreprise'), ('AUTRE', 'Autre')], default='SIMPLE', max_length=50)),
                ('raison_sociale', models.CharField(blank=True, help_text='Raison sociale si applicable (pour écoles, entreprises)', max_length=255, null=True)),
                ('preferences_notifications', models.TextField(blank=True, help_text="Préférences de notification de l'abonné (ex: format JSON ou champs spécifiques)")),
            ],
        ),
        migrations.CreateModel(
            name='Calendrier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom_calendrier', models.CharField(max_length=150, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='CategorieEvenement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom_categorie', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='ChargeDeCommunication',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL)),
                ('matricule', models.CharField(max_length=50, unique=True)),
                ('specialite', models.CharField(max_length=150)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ChargeDeProgrammation',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL)),
                ('matricule', models.CharField(max_length=50, unique=True)),
                ('specialite', models.CharField(max_length=150)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Paiement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_paiement', models.DateTimeField(default=django.utils.timezone.now)),
                ('montant', models.DecimalField(decimal_places=2, max_digits=10)),
                ('methode_paiement', models.CharField(choices=[('EN_LIGNE', 'En ligne'), ('CASH', 'Cash')], max_length=20)),
                ('statut_paiement', models.CharField(choices=[('EN_ATTENTE', 'En attente'), ('REUSSI', 'Réussi'), ('ECHOUE', 'Échoué')], default='EN_ATTENTE', max_length=20)),
                ('reference_transaction', models.CharField(blank=True, max_length=100, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Receptionniste',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL)),
                ('matricule', models.CharField(max_length=50, unique=True)),
                ('specialite', models.CharField(max_length=150)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Adresse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rue', models.CharField(max_length=255)),
                ('numero', models.CharField(blank=True, max_length=20, null=True)),
                ('ville', models.CharField(max_length=100)),
                ('code_postal', models.CharField(max_length=20)),
                ('pays', models.CharField(default='République Démocratique du Congo', max_length=100)),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='adresse_user', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Evenement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('date_debut', models.DateTimeField()),
                ('date_fin', models.DateTimeField()),
                ('lieu', models.CharField(max_length=255)),
                ('capacite', models.PositiveIntegerField()),
                ('prix', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('statut', models.CharField(choices=[('BROUILLON', 'Brouillon'), ('PUBLIE', 'Publié'), ('ANNULE', 'Annulé'), ('TERMINE', 'Terminé')], default='BROUILLON', max_length=20)),
                ('calendrier', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evenements_cal', to='GestionEvenement.calendrier')),
                ('categorie', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evenements_cat', to='GestionEvenement.categorieevenement')),
                ('responsable_communication', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evenements_communiques', to='GestionEvenement.chargedecommunication')),
                ('responsable_programmation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evenements_programmes', to='GestionEvenement.chargedeprogrammation')),
            ],
        ),
        migrations.CreateModel(
            name='Commentaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texte', models.TextField()),
                ('date_commentaire', models.DateTimeField(auto_now_add=True)),
                ('note', models.PositiveIntegerField(blank=True, help_text='Note de 1 à 5 étoiles, optionnelle', null=True)),
                ('abonne', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='commentaires_abonne', to='GestionEvenement.abonne')),
                ('evenement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='commentaires_evt', to='GestionEvenement.evenement')),
            ],
        ),
        migrations.AddField(
            model_name='abonne',
            name='evenements_interesses',
            field=models.ManyToManyField(blank=True, related_name='abonnes_interesses_new', to='GestionEvenement.evenement'),
        ),
        migrations.CreateModel(
            name='Billet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code_unique', models.CharField(max_length=100, unique=True)),
                ('type_billet', models.CharField(blank=True, help_text='Ex: Adulte, Enfant, VIP', max_length=50)),
                ('nom_detenteur', models.CharField(blank=True, max_length=150, null=True)),
                ('paiement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='billets_paiement', to='GestionEvenement.paiement')),
            ],
        ),
        migrations.CreateModel(
            name='ProfilUtilisateur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('photo', models.ImageField(blank=True, null=True, upload_to='photos_profil/')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profil', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Reservation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_reservation', models.DateTimeField(auto_now_add=True)),
                ('nombre_places', models.PositiveIntegerField(default=1)),
                ('statut_reservation', models.CharField(choices=[('EN_ATTENTE', 'En attente'), ('CONFIRMEE', 'Confirmée'), ('ANNULEE', 'Annulée'), ('PAYEE_CASH_ATTENTE_VALIDATION', 'Payée cash (attente validation)')], default='EN_ATTENTE', max_length=30)),
                ('montant_total', models.DecimalField(decimal_places=2, max_digits=10)),
                ('abonne', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reservations_abonne', to='GestionEvenement.abonne')),
                ('evenement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reservations_evt', to='GestionEvenement.evenement')),
            ],
        ),
        migrations.AddField(
            model_name='paiement',
            name='reservation',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='paiement_res', to='GestionEvenement.reservation'),
        ),
    ]
