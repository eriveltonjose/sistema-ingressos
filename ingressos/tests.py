import csv
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Evento, Ingresso


class IngressosVendidosCestaBasicaTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='operador',
            password='senha-segura'
        )
        self.client.force_login(self.usuario)
        self.evento = self.criar_evento('Evento principal')
        self.outro_evento = self.criar_evento('Outro evento')

    def criar_evento(self, nome):
        return Evento.objects.create(
            nome=nome,
            data=timezone.now() + timedelta(days=1),
            local='Auditório',
            valor='100.00',
            valor_associado='80.00',
            valor_nao_associado='100.00',
            quantidade_total=100,
            quantidade_associado=50,
            quantidade_nao_associado=50,
        )

    def criar_ingresso(self, evento=None, **campos):
        valores_padrao = {
            'evento': evento or self.evento,
            'nome_comprador': 'Pessoa Teste',
            'email': 'pessoa@example.com',
            'telefone': '11999999999',
            'cpf': '12345678901',
            'forma_pagamento': 'CESTA_BASICA',
        }
        valores_padrao.update(campos)
        return Ingresso.objects.create(**valores_padrao)

    def test_conta_ingressos_de_cesta_basica(self):
        self.criar_ingresso()
        self.criar_ingresso(nome_comprador='Outra pessoa', cpf='98765432100')
        self.criar_ingresso(
            nome_comprador='Pagamento Pix',
            cpf='11122233344',
            forma_pagamento='PIX'
        )

        response = self.client.get(reverse('ingressos_vendidos'))

        self.assertEqual(response.context['total_cesta_basica'], 2)

    def test_nao_conta_ingressos_de_cesta_basica_cancelados(self):
        self.criar_ingresso()
        self.criar_ingresso(
            nome_comprador='Cancelado',
            cpf='98765432100',
            cancelado=True
        )

        response = self.client.get(reverse('ingressos_vendidos'))

        self.assertEqual(response.context['total_cesta_basica'], 1)

    def test_filtra_ingressos_por_cesta_basica(self):
        cesta_basica = self.criar_ingresso()
        self.criar_ingresso(
            nome_comprador='Pagamento Pix',
            cpf='98765432100',
            forma_pagamento='PIX'
        )

        response = self.client.get(
            reverse('ingressos_vendidos'),
            {'filtro': 'cesta_basica'}
        )

        self.assertEqual(list(response.context['ingressos']), [cesta_basica])

    def test_preserva_evento_no_link_do_filtro_cesta_basica(self):
        response = self.client.get(
            reverse('ingressos_vendidos'),
            {'evento': self.evento.id}
        )

        self.assertContains(
            response,
            f'?evento={self.evento.id}&filtro=cesta_basica'
        )

    def test_exibe_cesta_basica_na_coluna_pagamento(self):
        self.criar_ingresso(nome_comprador='Comprador da cesta básica')

        response = self.client.get(reverse('ingressos_vendidos'))

        self.assertContains(response, 'Comprador da cesta básica')
        self.assertContains(response, 'Cesta Básica')


class ExportarCsvPagamentoTests(TestCase):
    def setUp(self):
        self.evento = self.criar_evento('Evento CSV')
        self.outro_evento = self.criar_evento('Outro evento CSV')

    def criar_evento(self, nome):
        return Evento.objects.create(
            nome=nome,
            data=timezone.now() + timedelta(days=1),
            local='Auditório',
            valor='100.00',
            valor_associado='80.00',
            valor_nao_associado='100.00',
            quantidade_total=100,
            quantidade_associado=50,
            quantidade_nao_associado=50,
        )

    def criar_ingresso(self, nome, forma_pagamento, evento=None):
        return Ingresso.objects.create(
            evento=evento or self.evento,
            nome_comprador=nome,
            email='pessoa@example.com',
            telefone='11999999999',
            cpf='12345678901',
            forma_pagamento=forma_pagamento,
        )

    def linhas_csv(self, response):
        conteudo = response.content.decode('utf-8')
        return list(csv.reader(StringIO(conteudo)))

    def test_exporta_cabecalho_e_rotulos_de_pagamento(self):
        self.criar_ingresso('Compra Pix', 'PIX')
        self.criar_ingresso('Compra Cartão', 'CREDIT_CARD')
        self.criar_ingresso('Compra Cesta', 'CESTA_BASICA')
        self.criar_ingresso('Compra Antiga', None)

        response = self.client.get(reverse('exportar_csv'))
        linhas = self.linhas_csv(response)
        cabecalho = linhas[8]
        pagamentos_por_nome = {
            linha[1]: linha[9]
            for linha in linhas[9:]
        }

        self.assertIn('Pagamento', cabecalho)
        self.assertEqual(pagamentos_por_nome['Compra Pix'], 'Pix')
        self.assertEqual(
            pagamentos_por_nome['Compra Cartão'],
            'Cartão de Crédito'
        )
        self.assertEqual(pagamentos_por_nome['Compra Cesta'], 'Cesta Básica')
        self.assertEqual(pagamentos_por_nome['Compra Antiga'], 'Não informado')

    def test_preserva_filtro_por_evento_na_exportacao(self):
        self.criar_ingresso('Ingresso do evento selecionado', 'PIX')
        self.criar_ingresso(
            'Ingresso de outro evento',
            'CESTA_BASICA',
            evento=self.outro_evento
        )

        response = self.client.get(
            reverse('exportar_csv'),
            {'evento': self.evento.id}
        )
        linhas = self.linhas_csv(response)
        nomes_exportados = [linha[1] for linha in linhas[9:]]

        self.assertEqual(nomes_exportados, ['Ingresso do evento selecionado'])
