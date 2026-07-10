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
from .models import Evento, Ingresso, Pedido, ValidacaoAssociado
import random
import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import datetime
from django.shortcuts import render, get_object_or_404
import requests
from django.db import transaction

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

def mascarar_email(email):
    if not email or "@" not in email:
        return "Não informado"

    usuario, dominio = email.split("@", 1)

    if len(usuario) <= 4:
        usuario_masc = usuario[:1] + "***"
    else:
        usuario_masc = usuario[:4] + "***"

    return f"{usuario_masc}@{dominio}"


def mascarar_telefone(telefone):
    if not telefone:
        return "Não informado"

    telefone = ''.join(filter(str.isdigit, str(telefone)))

    if len(telefone) < 4:
        return "Não informado"

    return telefone[:4] + "****" + telefone[-2:]

def lista_eventos(request):
    eventos = Evento.objects.filter(ativo=True).order_by('data')
    return render(request, 'ingressos/lista_eventos.html', {'eventos': eventos})

def consultar_associado_wbc(cpf):
    url = "http://189.90.139.178:2020/AMBR/wsCpfValidos.rule?sys=WBC"

    payload = {
        "cpf": cpf,
        "tipo": "01"
    }

    resposta = requests.get(url, json=payload, timeout=30)

    try:
        return resposta.json()
    except Exception:
        return {
            "situacao": "Erro",
            "mensagem": "Não foi possível interpretar a resposta da WBC.",
            "json": {}
        }

def validar_associado(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)

    list(messages.get_messages(request))

    if request.method == "POST":
        cpf = request.POST.get("cpf", "").replace(".", "").replace("-", "").strip()

        try:
            dados = consultar_associado_wbc(cpf)

        except Exception:
            messages.error(
                request,
                "Não foi possível consultar o cadastro no momento. Tente novamente."
            )

            return render(
                request,
                "ingressos/validar_associado.html",
                {
                    "evento": evento
                }
            )

        if not dados.get("associado"):
            messages.error(
                request,
                dados.get(
                    "mensagem",
                    "CPF não localizado no quadro de associados da AMBr."
                )
            )

            return render(
                request,
                "ingressos/validar_associado.html",
                {
                    "evento": evento
                }
            )

        if dados.get("pendencias"):
            messages.error(
                request,
                dados.get(
                    "mensagem",
                    "Identificamos pendência no cadastro. Procure a secretaria da AMBr."
                )
            )

            return render(
                request,
                "ingressos/validar_associado.html",
                {
                    "evento": evento
                }
            )

        email = dados.get("email") or ""
        telefone = dados.get("celular") or ""
        associado = {
            "nome": dados.get("nome", ""),
            "crm": dados.get("tipo", ""),
            "email": mascarar_email(email),
            "telefone": mascarar_telefone(telefone),
            "cpf": dados.get("cpf", cpf),
        }

        request.session['wbc_nome'] = associado['nome']
        request.session['wbc_tipo'] = associado['crm']

        request.session['wbc_email'] = email
        request.session['wbc_telefone'] = telefone

        request.session['wbc_cpf'] = associado['cpf']

        return render(
            request,
            "ingressos/validar_associado.html",
            {
                "evento": evento,
                "associado": associado
            }
        )

    return render(
        request,
        "ingressos/validar_associado.html",
        {
            "evento": evento
        }
    )

def enviar_codigo(request, evento_id):

    evento = get_object_or_404(Evento, id=evento_id)

    codigo = str(random.randint(100000, 999999))

    validacao = ValidacaoAssociado.objects.create(
        cpf=request.session.get('wbc_cpf', ''),
        nome=request.session.get('wbc_nome', ''),
        crm=request.session.get('wbc_tipo', ''),
        email=request.session.get('wbc_email', ''),
        telefone=request.session.get('wbc_telefone', ''),
        codigo=codigo,
        confirmado=False
    )
    

    print(f'CODIGO GERADO: {codigo}')
    send_mail(
        'Código de validação - Compra de ingresso AMBr',
        f'''
    Olá, {validacao.nome}.

    Seu código de validação é:

    {codigo}

    Digite este código na tela de confirmação para continuar sua compra.

    AMBr
    ''',
        settings.DEFAULT_FROM_EMAIL,
        [validacao.email],
        fail_silently=False,
    )

    return render(
        request,
        'ingressos/confirmar_codigo.html',
        {
            'evento': evento,
            'validacao_id': validacao.id
        }
    )


def confirmar_codigo(request, evento_id):

    evento = get_object_or_404(Evento, id=evento_id)

    if request.method == "POST":

        codigo_digitado = request.POST.get("codigo")

        validacao = ValidacaoAssociado.objects.filter(
            codigo=codigo_digitado,
            confirmado=False
        ).first()

        if validacao:

            validacao.confirmado = True
            validacao.save()

            request.session['associado_validado'] = True
            request.session['associado_nome'] = validacao.nome
            request.session['associado_email'] = validacao.email
            request.session['associado_telefone'] = validacao.telefone
            request.session['associado_cpf'] = validacao.cpf
            request.session['associado_crm'] = validacao.crm

            messages.success(
                request,
                "Código validado com sucesso."
            )

            return redirect(f"/comprar/{evento.id}/")

        else:

            messages.error(
                request,
                "Código inválido ou já utilizado."
            )

    return render(
        request,
        "ingressos/confirmar_codigo.html",
        {
            "evento": evento
        }
    )

def comprar_ingresso(request, evento_id):

    evento = get_object_or_404(Evento, id=evento_id)

    if not evento.ativo:
        messages.error(
            request,
            'As vendas deste evento foram encerradas.'
        )
        return redirect('lista_eventos')

    associado_validado = request.session.get(
        'associado_validado',
        False
    )

    # Evento exclusivo: exige validação de associado
    if evento.exclusivo_associado and not associado_validado:
        messages.error(
            request,
            'Este evento é exclusivo para associados. '
            'Valide seu cadastro antes de continuar.'
        )
        return redirect(f'/associado/{evento.id}/')

    # Limpa a validação somente nos eventos comuns
    if (
        not evento.exclusivo_associado
        and request.GET.get('tipo') == 'nao_associado'
    ):
        request.session.pop('associado_validado', None)
        request.session.pop('associado_nome', None)
        request.session.pop('associado_email', None)
        request.session.pop('associado_telefone', None)
        request.session.pop('associado_cpf', None)
        request.session.pop('associado_crm', None)

        associado_validado = False

    if associado_validado:
        valor_unitario = evento.valor_associado
        limite_ingressos = evento.quantidade_associado

        vendidos_tipo = Ingresso.objects.filter(
            evento=evento,
            associado=True,
            cancelado=False
        ).count()

    else:
        valor_unitario = evento.valor_nao_associado
        limite_ingressos = evento.quantidade_nao_associado

        vendidos_tipo = Ingresso.objects.filter(
            evento=evento,
            associado=False,
            cancelado=False
        ).count()

    disponiveis = limite_ingressos - vendidos_tipo

    if (
        request.GET.get('tipo') == 'associado'
        and not associado_validado
    ):
        messages.error(
            request,
            'Valide seu cadastro antes de comprar como associado.'
        )
        return redirect(f'/associado/{evento.id}/')

    # Define quantos ingressos serão gerados no evento especial
    quantidade_prevista = 1
    primeira_compra = False

    if (
        evento.exclusivo_associado
        and evento.beneficio_primeira_compra
        and associado_validado
    ):
        cpf_validado = request.session.get('associado_cpf', '')

        ja_comprou = Pedido.objects.filter(
            evento=evento,
            cpf=cpf_validado,
            associado=True,
            status='PAGO'
        ).exists()

        primeira_compra = not ja_comprou

        if primeira_compra:
            quantidade_prevista = evento.quantidade_primeira_compra
        else:
            quantidade_prevista = evento.quantidade_compras_seguintes

    if request.method == 'POST':

        # Em evento exclusivo, utiliza os dados validados da sessão
        if evento.exclusivo_associado:
            nome = request.session.get('associado_nome', '')
            email = request.session.get('associado_email', '')
            telefone = request.session.get('associado_telefone', '')
            cpf = request.session.get('associado_cpf', '')

            # Cada operação representa uma compra
            quantidade = 1

        else:
            nome = request.POST.get('nome')
            email = request.POST.get('email')
            telefone = request.POST.get('telefone')
            cpf = request.POST.get('cpf')

            try:
                quantidade = int(
                    request.POST.get('quantidade', 1)
                )
            except (TypeError, ValueError):
                quantidade = 1

        forma_pagamento = request.POST.get(
            'forma_pagamento',
            'PIX'
        )

        try:
            parcelas = int(request.POST.get('parcelas', 1))
        except (TypeError, ValueError):
            parcelas = 1

        # No evento especial, verifica o número real de convites
        quantidade_para_estoque = (
            quantidade_prevista
            if evento.exclusivo_associado
            else quantidade
        )

        if quantidade_para_estoque > disponiveis:
            messages.error(
                request,
                f'Quantidade indisponível. Restam apenas '
                f'{disponiveis} ingresso(s) para esta modalidade.'
            )

            return render(
                request,
                'ingressos/comprar_ingresso.html',
                {
                    'evento': evento,
                    'disponiveis': disponiveis,
                    'associado_validado': associado_validado,
                    'nome_associado': request.session.get(
                        'associado_nome',
                        ''
                    ),
                    'email_associado': request.session.get(
                        'associado_email',
                        ''
                    ),
                    'telefone_associado': request.session.get(
                        'associado_telefone',
                        ''
                    ),
                    'cpf_associado': request.session.get(
                        'associado_cpf',
                        ''
                    ),
                    'valor_unitario': valor_unitario,
                    'quantidade_prevista': quantidade_prevista,
                    'primeira_compra': primeira_compra,
                }
            )

        # Evento exclusivo cobra uma unidade,
        # embora possa gerar dois convites na primeira compra
        valor_total = valor_unitario * quantidade

        dados_pagamento = criar_pagamento_asaas(
            nome=nome,
            cpf=cpf,
            email=email,
            telefone=telefone,
            valor_total=valor_total,
            descricao=evento.nome,
            forma_pagamento=forma_pagamento,
            parcelas=parcelas
        )

        Pedido.objects.create(
            evento=evento,
            nome=nome,
            email=email,
            telefone=telefone,
            cpf=cpf,
            associado=associado_validado,
            quantidade=quantidade,
            valor_total=valor_total,
            asaas_payment_id=dados_pagamento['id'],
            forma_pagamento=forma_pagamento,
            status='PENDENTE'
        )

        return redirect(dados_pagamento['invoiceUrl'])

    return render(
        request,
        'ingressos/comprar_ingresso.html',
        {
            'evento': evento,
            'disponiveis': disponiveis,
            'associado_validado': associado_validado,
            'nome_associado': request.session.get(
                'associado_nome',
                ''
            ),
            'email_associado': request.session.get(
                'associado_email',
                ''
            ),
            'telefone_associado': request.session.get(
                'associado_telefone',
                ''
            ),
            'cpf_associado': request.session.get(
                'associado_cpf',
                ''
            ),
            'valor_unitario': valor_unitario,
            'quantidade_prevista': quantidade_prevista,
            'primeira_compra': primeira_compra,
        }
    )

@login_required
def ingresso_sucesso(request, ingresso_id):

    ingresso = get_object_or_404(Ingresso, id=ingresso_id)

    url_validacao = request.build_absolute_uri(
    f"/validar/{ingresso.codigo}/"
    )

    qr = qrcode.make(url_validacao)

    buffer = BytesIO()

    qr.save(buffer, format='PNG')

    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, 'ingressos/ingresso_sucesso.html', {
        'ingresso': ingresso,
        'qr_code': qr_base64
    })

@login_required
def ingressos_vendidos(request):

    evento_id = request.GET.get('evento')
    filtro = request.GET.get('filtro')

    eventos = Evento.objects.all()

    ingressos = Ingresso.objects.all().order_by('-criado_em')

    if evento_id:
        ingressos = ingressos.filter(evento_id=evento_id)

    total_vendidos = ingressos.count()

    total_associados = ingressos.filter(
        associado=True,
        cancelado=False
    ).count()

    total_nao_associados = ingressos.filter(
        associado=False,
        cancelado=False
    ).count()

    total_utilizados = ingressos.filter(usado=True).count()
    total_cancelados = ingressos.filter(cancelado=True).count()
    total_validos = total_vendidos - total_cancelados

    total_pix = ingressos.filter(
        forma_pagamento='PIX',
        cancelado=False
    ).count()

    total_cartao = ingressos.filter(
        forma_pagamento='CREDIT_CARD',
        cancelado=False
    ).count()

    if filtro == 'associados':
        ingressos = ingressos.filter(associado=True)

    elif filtro == 'nao_associados':
        ingressos = ingressos.filter(associado=False)

    elif filtro == 'utilizados':
        ingressos = ingressos.filter(usado=True)

    elif filtro == 'cancelados':
        ingressos = ingressos.filter(cancelado=True)

    elif filtro == 'validos':
        ingressos = ingressos.filter(cancelado=False)

    elif filtro == 'pix':
        ingressos = ingressos.filter(
            forma_pagamento='PIX'
        )

    elif filtro == 'cartao':
        ingressos = ingressos.filter(
            forma_pagamento='CREDIT_CARD'
        )    

    # ANONIMIZAR DADOS
    for ingresso in ingressos:
        ingresso.telefone_anonimo = anonimizar_telefone(ingresso.telefone)
        ingresso.cpf_anonimo = anonimizar_cpf(ingresso.cpf)

    return render(
        request,
        'ingressos/ingressos_vendidos.html',
        {
            'ingressos': ingressos,
            'eventos': eventos,
            'evento_id': evento_id,
            'filtro': filtro,
            'total_vendidos': total_vendidos,
            'total_associados': total_associados,
            'total_nao_associados': total_nao_associados,
            'total_pix': total_pix,
            'total_cartao': total_cartao,
            'total_utilizados': total_utilizados,
            'total_cancelados': total_cancelados,
            'total_validos': total_validos
        }
    )


@login_required
def validar_ingresso(request, codigo):

    ingresso = get_object_or_404(
        Ingresso,
        codigo=codigo
    )

    if ingresso.cancelado:

        return render(
            request,
            'ingressos/checkin_resultado.html',
            {
                'status': 'cancelado',
                'ingresso': ingresso
            }
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

    ingressos = Ingresso.objects.all().order_by('-criado_em')

    if evento_id and evento_id != 'Nome':
        ingressos = ingressos.filter(evento_id=evento_id)

    total_vendidos = ingressos.count()
    total_associados = ingressos.filter(associado=True).count()
    total_nao_associados = ingressos.filter(associado=False).count()
    total_utilizados = ingressos.filter(usado=True).count()
    total_cancelados = ingressos.filter(cancelado=True).count()
    total_validos = total_vendidos - total_cancelados

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="ingressos.csv"'

    writer = csv.writer(response)

    writer.writerow(['Resumo'])
    writer.writerow(['Total Vendidos', total_vendidos])
    writer.writerow(['Total Associados', total_associados])
    writer.writerow(['Total Não Associados', total_nao_associados])
    writer.writerow(['Total Utilizados', total_utilizados])
    writer.writerow(['Total Cancelados', total_cancelados])
    writer.writerow(['Total Válidos', total_validos])
    writer.writerow([])

    writer.writerow([
        'Evento',
        'Nome',
        'Associado',
        'Email',
        'Telefone',
        'CPF',
        'Status',
        'Data Compra',
        'Hora Compra'
    ])

    for ingresso in ingressos:
        if ingresso.cancelado:
            status = 'Cancelado'
        elif ingresso.usado:
            status = 'Utilizado'
        else:
            status = 'Valido'

        data_local = timezone.localtime(ingresso.criado_em)

        writer.writerow([
            ingresso.evento.nome,
            ingresso.nome_comprador,
            'S' if ingresso.associado else 'N',
            ingresso.email,
            ingresso.telefone,
            ingresso.cpf,
            status,
            data_local.strftime('%d/%m/%Y'),
            data_local.strftime('%H:%M')
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

def criar_pagamento_asaas(
    nome,
    cpf,
    email,
    telefone,
    valor_total,
    descricao,
    forma_pagamento='PIX',
    parcelas=1
):

    headers = {
        'accept': 'application/json',
        'content-type': 'application/json',
        'access_token': settings.ASAAS_API_KEY
    }

    cliente = {
        "name": nome,
        "cpfCnpj": cpf,
        "email": email,
        "mobilePhone": telefone
    }

    response_cliente = requests.post(
        f'{settings.ASAAS_BASE_URL}/customers',
        json=cliente,
        headers=headers
    )

    dados_cliente = response_cliente.json()

    if 'id' not in dados_cliente:
        raise Exception(f"Erro ao criar cliente no Asaas: {dados_cliente}")

    customer_id = dados_cliente['id']

    cobranca = {
        "customer": customer_id,
        "billingType": forma_pagamento,
        "value": float(valor_total),
        "dueDate": datetime.now().strftime('%Y-%m-%d'),
        "description": descricao
    }

    if forma_pagamento == 'CREDIT_CARD' and parcelas > 1:
        cobranca["installmentCount"] = parcelas
        cobranca["installmentValue"] = round(float(valor_total) / parcelas, 2)

    response_pagamento = requests.post(
        f'{settings.ASAAS_BASE_URL}/payments',
        json=cobranca,
        headers=headers
    )

    dados_pagamento = response_pagamento.json()

    if 'id' not in dados_pagamento:
        raise Exception(f"Erro ao criar pagamento no Asaas: {dados_pagamento}")

    return dados_pagamento
@login_required
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

    if evento_asaas not in ['PAYMENT_CONFIRMED', 'PAYMENT_RECEIVED']:
        return JsonResponse({
            'status': 'ignorado',
            'motivo': 'evento do Asaas nao processado'
        })

    ingressos_criados = []

    with transaction.atomic():

        pedido = Pedido.objects.select_for_update().filter(
            asaas_payment_id=payment_id
        ).first()

        # Ignora pagamentos que não pertencem ao sistema
        if not pedido:
            print(
                f'Webhook Asaas ignorado. '
                f'Pagamento não pertence ao sistema: {payment_id}'
            )

            return JsonResponse({
                'status': 'ignorado',
                'motivo': 'pagamento nao pertence ao sistema de ingressos'
            })

        # Evita gerar ingressos novamente caso o Asaas repita o webhook
        if pedido.status == 'PAGO':
            return JsonResponse({
                'status': 'ja_processado',
                'pedido': pedido.id
            })

        evento = pedido.evento

        # Regra especial do evento exclusivo para associados
        if (
            evento.exclusivo_associado
            and evento.beneficio_primeira_compra
            and pedido.associado
        ):

            ja_comprou = Pedido.objects.filter(
                evento=evento,
                cpf=pedido.cpf,
                associado=True,
                status='PAGO'
            ).exclude(
                pk=pedido.pk
            ).exists()

            if ja_comprou:
                quantidade_ingressos = (
                    evento.quantidade_compras_seguintes
                )
            else:
                quantidade_ingressos = (
                    evento.quantidade_primeira_compra
                )

        else:
            # Mantém o funcionamento normal dos outros eventos
            quantidade_ingressos = pedido.quantidade

        for i in range(quantidade_ingressos):

            ingresso = Ingresso.objects.create(
                pedido=pedido,
                evento=evento,
                nome_comprador=pedido.nome,
                email=pedido.email,
                telefone=pedido.telefone,
                cpf=pedido.cpf,
                associado=pedido.associado,
                forma_pagamento=pedido.forma_pagamento,
            )

            ingressos_criados.append(ingresso.id)

        pedido.status = 'PAGO'
        pedido.save(update_fields=['status'])

    # O e-mail é enviado somente depois de salvar tudo no banco
    ingressos_para_email = Ingresso.objects.filter(
        id__in=ingressos_criados
    )

    enviar_email_ingressos(
        ingressos_para_email,
        pedido.email
    )

    return JsonResponse({
        'status': 'sucesso',
        'pedido': pedido.id,
        'quantidade_ingressos': len(ingressos_criados)
    })

    

# Create your views here.


