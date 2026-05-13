from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import tempfile
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
        quantidade = int(request.POST.get('quantidade', 1))

        ingressos_criados = []

        for i in range(quantidade):
            ingresso = Ingresso.objects.create(
                evento=evento,
                nome_comprador=nome,
                email=email,
                telefone=telefone,
                cpf=cpf
            )

            ingressos_criados.append(ingresso.id)

        ids = ",".join(str(id) for id in ingressos_criados)

        return redirect(f'/sucesso-compra/?ids={ids}')

    return render(request, 'ingressos/comprar_ingresso.html', {'evento': evento})


def ingresso_sucesso(request, ingresso_id):

    ingresso = get_object_or_404(Ingresso, id=ingresso_id)

    url_validacao = f"http://192.168.15.3:8000/validar/{ingresso.codigo}/"

    qr = qrcode.make(url_validacao)

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
def validar_ingresso(request, codigo):

    ingresso = get_object_or_404(Ingresso, codigo=codigo)

    ja_usado = ingresso.usado

    if ja_usado:
        status = 'INGRESSO JA UTILIZADO'
        tipo = 'erro'
    else:
        ingresso.usado = True
        ingresso.save()
        status = 'INGRESSO VALIDADO COM SUCESSO'
        tipo = 'ok'

    return render(
        request,
        'ingressos/validar_ingresso.html',
        {
            'ingresso': ingresso,
            'status': status,
            'tipo': tipo
        }
    )
def sucesso_compra(request):

    ids = request.GET.get('ids', '')
    lista_ids = ids.split(',')

    ingressos = Ingresso.objects.filter(id__in=lista_ids)

    ingressos_com_qr = []

    for ingresso in ingressos:
        url_validacao = f"http://192.168.15.3:8000/validar/{ingresso.codigo}/"

        qr = qrcode.make(url_validacao)

        buffer = BytesIO()
        qr.save(buffer, format='PNG')

        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        ingressos_com_qr.append({
            'ingresso': ingresso,
            'qr_code': qr_base64
        })

    return render(
        request,
        'ingressos/sucesso_compra.html',
        {'ingressos_com_qr': ingressos_com_qr}
    )
def baixar_pdf_ingressos(request):

    ids = request.GET.get('ids', '')
    lista_ids = ids.split(',')

    ingressos = Ingresso.objects.filter(id__in=lista_ids)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="ingressos.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    largura, altura = A4

    for ingresso in ingressos:

        url_validacao = f"http://192.168.15.3:8000/validar/{ingresso.codigo}/"

        qr = qrcode.make(url_validacao)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        qr.save(temp_file.name)

        p.setFont("Helvetica-Bold", 22)
        p.drawCentredString(largura / 2, altura - 80, "INGRESSO DO EVENTO")

        p.setFont("Helvetica-Bold", 18)
        p.drawCentredString(largura / 2, altura - 130, ingresso.evento.nome)

        p.setFont("Helvetica", 13)
        p.drawCentredString(largura / 2, altura - 180, f"Comprador: {ingresso.nome_comprador}")
        p.drawCentredString(largura / 2, altura - 205, f"CPF: {ingresso.cpf}")
        p.drawCentredString(largura / 2, altura - 230, f"Codigo: {ingresso.codigo}")

        p.drawImage(
            ImageReader(temp_file.name),
            largura / 2 - 90,
            altura - 460,
            width=180,
            height=180
        )

        p.setFont("Helvetica", 10)
        p.drawCentredString(largura / 2, altura - 500, "Apresente este QR Code na entrada do evento.")

        p.showPage()

    p.save()

    return response
# Create your views here.
