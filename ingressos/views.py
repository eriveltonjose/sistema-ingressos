from django.shortcuts import render, get_object_or_404, redirect
from .models import Evento, Ingresso
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
import base64

def lista_eventos(request):
    eventos = Evento.objects.all()
    return render(request, 'ingressos/lista_eventos.html', {'eventos': eventos})


def comprar_ingresso(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)

    if request.method == 'POST':
        nome = request.POST.get('nome')
        email = request.POST.get('email')
        telefone = request.POST.get('telefone')
        cpf = request.POST.get('cpf')

        ingresso = Ingresso.objects.create(
            evento=evento,
            nome_comprador=nome,
            email=email,
            telefone=telefone,
            cpf=cpf
        )

        return redirect('ingresso_sucesso', ingresso_id=ingresso.id)

    return render(request, 'ingressos/comprar_ingresso.html', {'evento': evento})


def ingresso_sucesso(request, ingresso_id):

    ingresso = get_object_or_404(Ingresso, id=ingresso_id)

    qr = qrcode.make(str(ingresso.codigo))

    buffer = BytesIO()

    qr.save(buffer, format='PNG')

    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, 'ingressos/ingresso_sucesso.html', {
        'ingresso': ingresso,
        'qr_code': qr_base64
    })

def ingressos_vendidos(request):

    ingressos = Ingresso.objects.all().order_by('-criado_em')

    return render(
        request,
        'ingressos/ingressos_vendidos.html',
        {'ingressos': ingressos}
    )

# Create your views here.
