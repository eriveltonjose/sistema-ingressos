from datetime import timedelta

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
