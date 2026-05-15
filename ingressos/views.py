from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import tempfile
from django.shortcuts import render, get_object_or_404, redirect
from .models import Evento, Ingresso, Pedido
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
import base64
from django.contrib import messages
import csv
from django.http import HttpResponse
from django.core.mail import EmailMessage
from django.core.mail import send_mail
from django.conf import settings
import requests
from django.conf import settings
from .models import Evento, Ingresso, Pedido
import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone

def anonimizar_telefone(telefone):
    telefone = str(telefone or '')

    if len(telefone) >= 6:
        return telefone[:4] + '*****' + telefone[-2:]

    return telefone


def anonimizar_cpf(cpf):
    cpf = str(cpf or '')

    if len(cpf) >= 6:
        return cpf[:3] + '*****' + cpf[-3:]

    return cpf

def lista_eventos(request):
    eventos = Evento.objects.all()
    return render(request, 'ingressos/lista_eventos.html', {'eventos': eventos})


def comprar_ingresso(request, evento_id):

    evento = get_object_or_404(Evento, id=evento_id)

    vendidos = Ingresso.objects.filter(evento=evento).count()
    disponiveis = evento.quantidade_total - vendidos

    if request.method == 'POST':

        nome = request.POST.get('nome')
        email = request.POST.get('email')
        telefone = request.POST.get('telefone')
        cpf = request.POST.get('cpf')
        quantidade = int(request.POST.get('quantidade', 1))

        if quantidade > disponiveis:
            messages.error(
                request,
                f'Quantidade indisponivel. Restam apenas {disponiveis} ingresso(s).'
            )

            return render(
                request,
                'ingressos/comprar_ingresso.html',
                {
                    'evento': evento,
                    'disponiveis': disponiveis
                }
            )


        return render(
            request,
            'ingressos/comprar_ingresso.html',
            {
                'evento': evento,
                'disponiveis': disponiveis
            }
        )

    return render(
        request,
        'ingressos/comprar_ingresso.html',
        {
            'evento': evento,
            'disponiveis': disponiveis
        }
    )

def comprar_ingresso(request, evento_id):

    evento = get_object_or_404(Evento, id=evento_id)

    vendidos = Ingresso.objects.filter(evento=evento).count()
    disponiveis = evento.quantidade_total - vendidos

    if request.method == 'POST':

        nome = request.POST.get('nome')
        email = request.POST.get('email')
        telefone = request.POST.get('telefone')
        cpf = request.POST.get('cpf')
        quantidade = int(request.POST.get('quantidade', 1))

        if quantidade > disponiveis:
            messages.error(
                request,
                f'Quantidade indisponivel. Restam apenas {disponiveis} ingresso(s).'
            )

            return render(
                request,
                'ingressos/comprar_ingresso.html',
                {
                    'evento': evento,
                    'disponiveis': disponiveis
                }
            )

        valor_total = evento.valor * quantidade

        pagamento = criar_pagamento_asaas(
            nome,
            email,
            cpf,
            valor_total
        )

        Pedido.objects.create(
            evento=evento,
            nome=nome,
            email=email,
            telefone=telefone,
            cpf=cpf,
            quantidade=quantidade,
            valor_total=valor_total,
            asaas_payment_id=pagamento['payment_id'],
            status='PENDENTE'
        )

        return redirect(pagamento['invoiceUrl'])

    return render(
        request,
        'ingressos/comprar_ingresso.html',
        {
            'evento': evento,
            'disponiveis': disponiveis
        }
    )
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

    evento_id = request.GET.get('evento')

    eventos = Evento.objects.all()

    ingressos = Ingresso.objects.all().order_by('-criado_em')

    if evento_id:
        ingressos = ingressos.filter(evento_id=evento_id)

    # ANONIMIZAR DADOS
    for ingresso in ingressos:
        ingresso.telefone_anonimo = anonimizar_telefone(ingresso.telefone)
        ingresso.cpf_anonimo = anonimizar_cpf(ingresso.cpf)

    total_vendidos = ingressos.count()

    total_utilizados = ingressos.filter(usado=True).count()

    total_validos = ingressos.filter(usado=False).count()

    return render(
        request,
        'ingressos/ingressos_vendidos.html',
        {
            'ingressos': ingressos,
            'eventos': eventos,
            'evento_id': evento_id,
            'total_vendidos': total_vendidos,
            'total_utilizados': total_utilizados,
            'total_validos': total_validos
        }
    )


def validar_ingresso(request, codigo):

    ingresso = get_object_or_404(
        Ingresso,
        codigo=codigo
    )

    if ingresso.usado:

        return render(
            request,
            'ingressos/checkin_resultado.html',
            {
                'status': 'usado',
                'ingresso': ingresso
            }
        )

    ingresso.usado = True
    ingresso.data_checkin = timezone.now()
    ingresso.save()

    return render(
        request,
        'ingressos/checkin_resultado.html',
        {
            'status': 'ok',
            'ingresso': ingresso
        }
    )

def sucesso_compra(request):

    ids = request.GET.get('ids', '')
    lista_ids = ids.split(',')

    ingressos = Ingresso.objects.filter(id__in=lista_ids)

    ingressos_com_qr = []

    for ingresso in ingressos:

        url_validacao = f"https://ingressos.e-especialista.org.br/validar/{ingresso.codigo}/"

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
        ingresso.telefone_anonimo = anonimizar_telefone(ingresso.telefone)
        ingresso.cpf_anonimo = anonimizar_cpf(ingresso.cpf)

        # URL validação
        url_validacao = f"https://ingressos.e-especialista.org.br/validar/{ingresso.codigo}/"

        # QRCode
        qr = qrcode.make(url_validacao)

        temp_qr = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        qr.save(temp_qr.name)

        # =========================
        # BANNER DO EVENTO
        # =========================
        if ingresso.evento.banner:

            try:
                banner_path = ingresso.evento.banner.path

                p.drawImage(
                    ImageReader(banner_path),
                    40,
                    altura - 240,
                    width=largura - 80,
                    height=170,
                    preserveAspectRatio=True
                )

            except Exception:
                pass

        # =========================
        # TITULO
        # =========================
        p.setFont("Helvetica-Bold", 24)
        p.drawCentredString(
            largura / 2,
            altura - 280,
            "INGRESSO DO EVENTO"
        )

        # =========================
        # NOME EVENTO
        # =========================
        p.setFont("Helvetica-Bold", 18)
        p.drawCentredString(
            largura / 2,
            altura - 320,
            ingresso.evento.nome
        )

        # =========================
        # LINHA
        # =========================
        p.line(60, altura - 340, largura - 60, altura - 340)

        # =========================
        # DADOS
        # =========================
        p.setFont("Helvetica", 13)

        p.drawString(
            80,
            altura - 390,
            f"Comprador: {ingresso.nome_comprador}"
        )

        p.drawString(
            80,
            altura - 420,
            f"CPF: {ingresso.cpf}"
        )

        p.drawString(
            80,
            altura - 450,
            f"Código: {ingresso.codigo}"
        )

        # =========================
        # QR CODE
        # =========================
        p.drawImage(
            ImageReader(temp_qr.name),
            largura / 2 - 90,
            altura - 700,
            width=180,
            height=180
        )

        # =========================
        # TEXTO RODAPÉ
        # =========================
        p.setFont("Helvetica", 10)

        p.drawCentredString(
            largura / 2,
            altura - 720,
            "Apresente este QR Code na entrada do evento."
        )

        p.drawCentredString(
            largura / 2,
            altura - 740,
            "Ingresso válido somente após confirmação do pagamento."
        )

        p.showPage()

    p.save()

    return response
        

def exportar_csv(request):

    evento_id = request.GET.get('evento')

    ingressos = Ingresso.objects.all()

    if evento_id and evento_id != 'Nome':
        ingressos = ingressos.filter(evento_id=evento_id)

    response = HttpResponse(content_type='text/csv')

    response['Content-Disposition'] = 'attachment; filename="ingressos.csv"'

    writer = csv.writer(response)

    writer.writerow([
        'Evento',
        'Nome',
        'Email',
        'Telefone',
        'CPF',
        'Status'
    ])

    for ingresso in ingressos:

        status = 'Utilizado' if ingresso.usado else 'Valido'

        writer.writerow([
            ingresso.evento.nome,
            ingresso.nome_comprador,
            ingresso.email,
            ingresso.telefone,
            ingresso.cpf,
            status
        ])

    return response
def testar_email(request):

    send_mail(
        'Teste Sistema de Ingressos',
        'Seu sistema de envio de e-mail esta funcionando!',
        settings.EMAIL_HOST_USER,
        ['erivelton.jose@ambr.org.br'],
        fail_silently=False,
    )

    return HttpResponse('E-mail enviado com sucesso!')

def gerar_pdf_ingressos_bytes(ingressos):

    buffer_pdf = BytesIO()

    p = canvas.Canvas(buffer_pdf, pagesize=A4)
    largura, altura = A4

    for ingresso in ingressos:

        # =========================
        # URL DE VALIDACAO
        # =========================
        url_validacao = f"https://ingressos.e-especialista.org.br/validar/{ingresso.codigo}/"

        # =========================
        # QR CODE
        # =========================
        qr = qrcode.make(url_validacao)

        buffer_qr = BytesIO()
        qr.save(buffer_qr, format='PNG')
        buffer_qr.seek(0)

        # =========================
        # BANNER DO EVENTO
        # =========================
        if ingresso.evento.banner:

            try:

                banner_path = ingresso.evento.banner.path

                p.drawImage(
                    ImageReader(banner_path),
                    40,
                    altura - 240,
                    width=largura - 80,
                    height=170,
                    preserveAspectRatio=True
                )

            except Exception:
                pass

        # =========================
        # TITULO
        # =========================
        p.setFont("Helvetica-Bold", 24)

        p.drawCentredString(
            largura / 2,
            altura - 280,
            ingresso.evento.nome
        )

        # =========================
        # LINHA DIVISORIA
        # =========================
        p.line(
            60,
            altura - 300,
            largura - 60,
            altura - 300
        )

        # =========================
        # DADOS COMPRADOR
        # =========================
        p.setFont("Helvetica", 14)

        p.drawCentredString(
            largura / 2,
            altura - 360,
            f"Comprador: {ingresso.nome_comprador}"
        )

        p.drawCentredString(
            largura / 2,
            altura - 395,
            f"CPF: {ingresso.cpf}"
        )

        p.setFont("Helvetica", 12)

        p.drawCentredString(
            largura / 2,
            altura - 435,
            f"Codigo: {ingresso.codigo}"
        )

        # =========================
        # QR CODE
        # =========================
        p.drawImage(
            ImageReader(buffer_qr),
            largura / 2 - 110,
            altura - 700,
            width=220,
            height=220
        )

        # =========================
        # TEXTO RODAPE
        # =========================
        p.setFont("Helvetica-Bold", 12)

        p.drawCentredString(
            largura / 2,
            altura - 735,
            "Apresente este QR Code na entrada do evento."
        )

        p.setFont("Helvetica", 10)

        p.drawCentredString(
            largura / 2,
            altura - 755,
            "Ingresso individual e valido para uma unica entrada."
        )

        p.showPage()

    p.save()

    buffer_pdf.seek(0)

    return buffer_pdf.getvalue()

def enviar_email_ingressos(ingressos, email_destino):

    pdf = gerar_pdf_ingressos_bytes(ingressos)

    assunto = 'Seus ingressos foram gerados'

    mensagem = '''
Olá!

Sua compra foi registrada com sucesso.

Segue em anexo o PDF com seus ingressos e QR Codes.

Apresente o QR Code na entrada do evento.

Obrigado!
'''

    email = EmailMessage(
        assunto,
        mensagem,
        settings.DEFAULT_FROM_EMAIL,
        [email_destino],
    )

    email.attach('ingressos.pdf', pdf, 'application/pdf')

    email.send()

def criar_pagamento_asaas(nome, email, cpf, valor):

    headers = {
        'accept': 'application/json',
        'content-type': 'application/json',
        'access_token': settings.ASAAS_API_KEY
    }

    cliente = {
        "name": nome,
        "email": email,
        "cpfCnpj": cpf
    }

    resposta_cliente = requests.post(
        f"{settings.ASAAS_BASE_URL}/customers",
        json=cliente,
        headers=headers
    )

    dados_cliente = resposta_cliente.json()

    if 'id' not in dados_cliente:
        raise Exception(f"Erro ao criar cliente no Asaas: {dados_cliente}")

    customer_id = dados_cliente['id']

    cobranca = {
        "customer": customer_id,
        "billingType": "CREDIT_CARD",
        "value": float(valor),
        "dueDate": "2026-12-30",
        "description": "Ingresso Evento"
    }

    resposta_pagamento = requests.post(
        f"{settings.ASAAS_BASE_URL}/payments",
        json=cobranca,
        headers=headers
    )

    dados_pagamento = resposta_pagamento.json()

    if 'invoiceUrl' not in dados_pagamento or 'id' not in dados_pagamento:
        raise Exception(f"Erro ao criar cobrança no Asaas: {dados_pagamento}")

    return {
        'invoiceUrl': dados_pagamento['invoiceUrl'],
        'payment_id': dados_pagamento['id']
    }

@csrf_exempt
def webhook_asaas(request):

    if request.method != 'POST':
        return JsonResponse({'status': 'webhook ativo'})

    token_recebido = request.headers.get('asaas-access-token')

    if token_recebido != settings.ASAAS_WEBHOOK_TOKEN:
        return JsonResponse({'erro': 'token invalido'}, status=403)

    dados = json.loads(request.body)

    evento_asaas = dados.get('event')
    pagamento = dados.get('payment', {})
    payment_id = pagamento.get('id')

    if evento_asaas in ['PAYMENT_CONFIRMED', 'PAYMENT_RECEIVED']:

        pedido = Pedido.objects.filter(asaas_payment_id=payment_id).first()

        if pedido and pedido.status != 'PAGO':

            ingressos_criados = []

            for i in range(pedido.quantidade):
                ingresso = Ingresso.objects.create(
                    evento=pedido.evento,
                    nome_comprador=pedido.nome,
                    email=pedido.email,
                    telefone=pedido.telefone,
                    cpf=pedido.cpf
                )

                ingressos_criados.append(ingresso.id)

            pedido.status = 'PAGO'
            pedido.save()

            ingressos_para_email = Ingresso.objects.filter(id__in=ingressos_criados)
            enviar_email_ingressos(ingressos_para_email, pedido.email)

    return JsonResponse({'status': 'ok'})  


def checkin_scanner(request):
    return render(request, 'ingressos/checkin_scanner.html')

def anonimizar_telefone(telefone):
    telefone = str(telefone)
    if len(telefone) >= 4:
        return telefone[:4] + '*****' + telefone[-2:]
    return telefone


def anonimizar_cpf(cpf):
    cpf = str(cpf)
    if len(cpf) >= 6:
        return cpf[:3] + '*****' + cpf[-3:]
    return cpf



# Create your views here.


