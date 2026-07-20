import csv
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Evento, Ingresso, Pedido


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


class PedidoAdminCestaBasicaPermissionTests(TestCase):
    def setUp(self):
        self.evento = Evento.objects.create(
            nome='Evento para confirmação presencial',
            data=timezone.now() + timedelta(days=1),
            local='Auditório',
            valor='100.00',
            valor_associado='80.00',
            valor_nao_associado='100.00',
            quantidade_total=100,
            quantidade_associado=50,
            quantidade_nao_associado=50,
        )
        self.permissao_visualizar = Permission.objects.get(
            content_type__app_label='ingressos',
            codename='view_pedido'
        )
        self.permissao_cesta_basica = Permission.objects.get(
            content_type__app_label='ingressos',
            codename='confirmar_pagamento_cesta_basica'
        )
        self.operador = get_user_model().objects.create_user(
            username='operador-cesta',
            password='senha-segura',
            is_staff=True,
        )
        self.operador.user_permissions.add(
            self.permissao_visualizar,
            self.permissao_cesta_basica,
        )
        self.usuario_somente_visualizacao = (
            get_user_model().objects.create_user(
                username='somente-visualizacao',
                password='senha-segura',
                is_staff=True,
            )
        )
        self.usuario_somente_visualizacao.user_permissions.add(
            self.permissao_visualizar
        )
        self.superusuario = get_user_model().objects.create_superuser(
            username='superusuario',
            password='senha-segura',
            email='superusuario@example.com',
        )
        self.lista_pedidos_url = reverse('admin:ingressos_pedido_changelist')

    def criar_pedido(self, status='PENDENTE', quantidade=1):
        return Pedido.objects.create(
            evento=self.evento,
            nome='Comprador presencial',
            email='comprador@example.com',
            telefone='11999999999',
            cpf='12345678901',
            quantidade=quantidade,
            valor_total='100.00',
            status=status,
        )

    def executar_acao(self, pedido, follow=False):
        return self.client.post(
            self.lista_pedidos_url,
            {
                'action': 'confirmar_pagamento_presencial',
                '_selected_action': [pedido.pk],
            },
            follow=follow,
        )

    def test_operador_autorizado_visualiza_os_pedidos(self):
        pedido = self.criar_pedido()
        self.client.force_login(self.operador)

        response = self.client.get(self.lista_pedidos_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, pedido.nome)

    def test_operador_autorizado_recebe_a_acao(self):
        self.criar_pedido()
        self.client.force_login(self.operador)

        response = self.client.get(self.lista_pedidos_url)

        self.assertContains(response, 'confirmar_pagamento_presencial')

    def test_usuario_com_apenas_view_pedido_nao_recebe_a_acao(self):
        self.criar_pedido()
        self.client.force_login(self.usuario_somente_visualizacao)

        response = self.client.get(self.lista_pedidos_url)

        self.assertNotContains(response, 'confirmar_pagamento_presencial')

    def test_requisicao_direta_sem_permissao_nao_confirma_pagamento(self):
        pedido = self.criar_pedido()
        self.client.force_login(self.usuario_somente_visualizacao)

        response = self.executar_acao(pedido)

        pedido.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(pedido.status, 'PENDENTE')
        self.assertFalse(
            Ingresso.objects.filter(pedido=pedido).exists()
        )

    def test_operador_nao_pode_editar_adicionar_ou_excluir_pedidos(self):
        pedido = self.criar_pedido()
        self.client.force_login(self.operador)

        resposta_edicao = self.client.post(
            reverse('admin:ingressos_pedido_change', args=[pedido.pk]),
            {'nome': 'Nome alterado'}
        )
        resposta_adicao = self.client.get(
            reverse('admin:ingressos_pedido_add')
        )
        resposta_exclusao = self.client.get(
            reverse('admin:ingressos_pedido_delete', args=[pedido.pk])
        )

        pedido.refresh_from_db()
        self.assertEqual(resposta_edicao.status_code, 403)
        self.assertEqual(resposta_adicao.status_code, 403)
        self.assertEqual(resposta_exclusao.status_code, 403)
        self.assertEqual(pedido.nome, 'Comprador presencial')

    @patch('ingressos.admin.enviar_email_ingressos')
    def test_pedido_pendente_e_confirmado(self, enviar_email):
        pedido = self.criar_pedido(quantidade=2)
        self.client.force_login(self.operador)

        response = self.executar_acao(pedido)

        pedido.refresh_from_db()
        ingressos = Ingresso.objects.filter(pedido=pedido)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(pedido.status, 'PAGO')
        self.assertEqual(pedido.forma_pagamento, 'CESTA_BASICA')
        self.assertEqual(ingressos.count(), 2)
        self.assertEqual(
            ingressos.filter(forma_pagamento='CESTA_BASICA').count(),
            2
        )
        enviar_email.assert_called_once()

    @patch('ingressos.admin.enviar_email_ingressos')
    def test_pedido_pago_e_ignorado(self, enviar_email):
        pedido = self.criar_pedido(status='PAGO')
        self.client.force_login(self.operador)

        response = self.executar_acao(pedido, follow=True)

        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'PAGO')
        self.assertFalse(Ingresso.objects.filter(pedido=pedido).exists())
        self.assertContains(response, 'pedido(s) ignorado(s)')
        enviar_email.assert_not_called()

    @patch('ingressos.admin.enviar_email_ingressos')
    def test_pedido_cancelado_e_ignorado(self, enviar_email):
        pedido = self.criar_pedido(status='CANCELADO')
        self.client.force_login(self.operador)

        response = self.executar_acao(pedido, follow=True)

        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'CANCELADO')
        self.assertFalse(Ingresso.objects.filter(pedido=pedido).exists())
        self.assertContains(response, 'pedido(s) ignorado(s)')
        enviar_email.assert_not_called()

    @patch('ingressos.admin.enviar_email_ingressos')
    def test_nao_cria_ingressos_duplicados(self, enviar_email):
        pedido = self.criar_pedido(quantidade=2)
        self.client.force_login(self.operador)

        self.executar_acao(pedido)
        self.executar_acao(pedido)

        self.assertEqual(Ingresso.objects.filter(pedido=pedido).count(), 2)
        enviar_email.assert_called_once()

    @patch('ingressos.admin.enviar_email_ingressos')
    def test_superusuario_mantem_acesso_a_acao(self, enviar_email):
        pedido = self.criar_pedido()
        self.client.force_login(self.superusuario)

        response = self.client.get(self.lista_pedidos_url)
        self.executar_acao(pedido)

        pedido.refresh_from_db()
        self.assertContains(response, 'confirmar_pagamento_presencial')
        self.assertEqual(pedido.status, 'PAGO')
        enviar_email.assert_called_once()
