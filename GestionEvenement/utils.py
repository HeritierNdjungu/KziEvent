import qrcode
from io import BytesIO
from django.template.loader import get_template
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from xhtml2pdf import pisa
from .models import Reservation, Billet, Evenement, Abonne

def generer_qr_code(texte):
    """Génère un QR code à partir d'un texte donné"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(texte)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer)
    return buffer.getvalue()

def generer_billet_pdf(request, reservation_id):
    """Génère un billet PDF pour une réservation donnée"""
    # Récupérer la réservation
    reservation = get_object_or_404(Reservation, id=reservation_id)
    
    # Vérifier que l'utilisateur a le droit d'accéder à cette réservation
    if request.user != reservation.abonne.user and not request.user.is_staff:
        return HttpResponse("Accès non autorisé", status=403)
    
    # Récupérer les informations nécessaires
    evenement = reservation.evenement
    abonne = reservation.abonne
    
    # Générer le QR code (contenant les informations de la réservation)
    qr_data = f"RESERVATION:{reservation.id}|EVENEMENT:{evenement.id}|ABONNE:{abonne.user.id}|PLACES:{reservation.nombre_places}|DATE:{reservation.date_reservation}"
    qr_code = generer_qr_code(qr_data)
    qr_code_base64 = f"data:image/png;base64,{base64.b64encode(qr_code).decode('utf-8')}"
    
    # Préparer le contexte pour le template
    context = {
        'reservation': reservation,
        'evenement': evenement,
        'abonne': abonne,
        'qr_code': qr_code_base64,
        'date_emission': timezone.now(),
    }
    
    # Charger le template HTML
    template = get_template('GestionEvenement/billets/billet_template.html')
    html = template.render(context)
    
    # Créer la réponse HTTP avec le PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="billet_{reservation.id}.pdf"'
    
    # Générer le PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    # Retourner le PDF en cas de succès, sinon une erreur
    if pisa_status.err:
        return HttpResponse('Une erreur est survenue lors de la génération du PDF', status=500)
    return response
