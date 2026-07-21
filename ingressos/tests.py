import csv
import json
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Evento, Ingresso, Pedido


class ListaEventosAssociadoTests(TestCase):
    def criar_evento(self, beneficio):
        return Evento.objects.create(
            nome='Evento card associado',
            data=timezone.now() + timedelta(days=1),
            local='AMBr',
            valor='90.00',
            valor_associado='83.50',
            valor_nao_associado='90.00',
            quantidade_total=100,
            quantidade_associado=50,
            quantidade_nao_associado=50,
            beneficio_primeira_compra=beneficio,
        )

    def test_card_associado_exibe_valor_dinamico_cesta_e_beneficio(self):
        self.criar_evento(beneficio=True)

        response = self.client.get(reverse('lista_eventos'))

        self.assertContains(response, 'Associado AMBr')
        self.assertContains(response, 'R$ 83.50 ou 1 cesta básica')
        self.assertContains(response, 'por unidade')
        self.assertContains(
            response,
            'Na primeira compra, 1 unidade dá direito a 2 convites.',
        )

    def test_card_sem_beneficio_nao_exibe_aviso(self):
        self.criar_evento(beneficio=False)

        response = self.client.get(reverse('lista_eventos'))

        self.assertContains(response, 'R$ 83.50 ou 1 cesta básica')
        self.assertNotContains(
            response,
            'Na primeira compra, 1 unidade dá direito a 2 convites.',
        )


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
            forma_pagamento='CESTA_BASICA',
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

    def dados_edicao(self, pedido, **alteracoes):
        dados = {
            'evento': pedido.evento_id,
            'nome': pedido.nome,
            'email': pedido.email,
            'telefone': pedido.telefone,
            'cpf': pedido.cpf,
            'associado': 'on' if pedido.associado else '',
            'quantidade': pedido.quantidade,
            'valor_total': pedido.valor_total,
            'asaas_payment_id': pedido.asaas_payment_id or '',
            'status': pedido.status,
            'forma_pagamento': pedido.forma_pagamento or '',
            '_save': 'Salvar',
        }
        dados.update(alteracoes)
        return dados

    def nomes_acoes(self, response):
        action_form = response.context.get('action_form')
        if not action_form:
            return set()
        return {
            valor
            for valor, _rotulo in action_form.fields['action'].choices
            if valor
        }

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
        self.assertEqual(
            self.nomes_acoes(response),
            {'confirmar_pagamento_presencial'},
        )

    def test_usuario_com_apenas_view_pedido_nao_recebe_a_acao(self):
        self.criar_pedido()
        self.client.force_login(self.usuario_somente_visualizacao)

        response = self.client.get(self.lista_pedidos_url)

        self.assertNotContains(response, 'confirmar_pagamento_presencial')
        self.assertEqual(self.nomes_acoes(response), set())

    def test_superusuario_ve_save_e_delete_no_detalhe(self):
        pedido = self.criar_pedido()
        self.client.force_login(self.superusuario)

        response = self.client.get(
            reverse('admin:ingressos_pedido_change', args=[pedido.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="_save"')
        self.assertContains(response, 'class="deletelink"')

    def test_superusuario_consegue_alterar_pedido(self):
        pedido = self.criar_pedido()
        self.client.force_login(self.superusuario)

        response = self.client.post(
            reverse('admin:ingressos_pedido_change', args=[pedido.pk]),
            self.dados_edicao(pedido, nome='Nome alterado pelo superusuário'),
        )

        pedido.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(pedido.nome, 'Nome alterado pelo superusuário')

    def test_superusuario_consegue_excluir_pedido(self):
        pedido = self.criar_pedido()
        self.client.force_login(self.superusuario)
        url = reverse('admin:ingressos_pedido_delete', args=[pedido.pk])

        confirmacao = self.client.get(url)
        response = self.client.post(url, {'post': 'yes'})

        self.assertEqual(confirmacao.status_code, 200)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Pedido.objects.filter(pk=pedido.pk).exists())

    def test_superusuario_recebe_acoes_padrao_e_de_cesta(self):
        self.criar_pedido()
        self.client.force_login(self.superusuario)

        response = self.client.get(self.lista_pedidos_url)

        self.assertIn('delete_selected', self.nomes_acoes(response))
        self.assertIn(
            'confirmar_pagamento_presencial',
            self.nomes_acoes(response),
        )

    def test_operador_detalhe_nao_exibe_save_ou_delete(self):
        pedido = self.criar_pedido()
        self.client.force_login(self.operador)

        response = self.client.get(
            reverse('admin:ingressos_pedido_change', args=[pedido.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')
        self.assertNotContains(response, 'class="deletelink"')

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
            self.dados_edicao(pedido, nome='Nome alterado')
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

    def test_usuario_view_nao_recebe_acoes_de_alteracao(self):
        pedido = self.criar_pedido()
        self.client.force_login(self.usuario_somente_visualizacao)

        lista = self.client.get(self.lista_pedidos_url)
        detalhe = self.client.get(
            reverse('admin:ingressos_pedido_change', args=[pedido.pk])
        )

        self.assertEqual(self.nomes_acoes(lista), set())
        self.assertNotContains(detalhe, 'name="_save"')
        self.assertNotContains(detalhe, 'class="deletelink"')

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
    def test_pix_e_cartao_nao_podem_ser_confirmados_como_cesta(self, enviar_email):
        self.client.force_login(self.operador)
        for forma in ('PIX', 'CREDIT_CARD'):
            with self.subTest(forma=forma):
                pedido = self.criar_pedido()
                pedido.forma_pagamento = forma
                pedido.save(update_fields=['forma_pagamento'])
                self.executar_acao(pedido)
                pedido.refresh_from_db()
                self.assertEqual(pedido.status, 'PENDENTE')
                self.assertFalse(pedido.ingressos.exists())
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

    @patch('ingressos.admin.enviar_email_ingressos')
    def test_cestas_aplicam_beneficio_somente_na_primeira_confirmada(
        self, enviar_email
    ):
        self.evento.exclusivo_associado = True
        self.evento.beneficio_primeira_compra = True
        self.evento.save()
        primeiro = self.criar_pedido(quantidade=2)
        segundo = self.criar_pedido(quantidade=2)
        primeiro.associado = segundo.associado = True
        primeiro.save(update_fields=['associado'])
        segundo.save(update_fields=['associado'])
        self.client.force_login(self.operador)

        self.executar_acao(primeiro)
        self.executar_acao(segundo)

        self.assertEqual(primeiro.ingressos.count(), 3)
        self.assertEqual(segundo.ingressos.count(), 2)
        self.assertEqual(enviar_email.call_count, 2)

    @patch('ingressos.admin.enviar_email_ingressos')
    def test_primeira_cesta_de_uma_unidade_gera_dois_convites(self, enviar_email):
        self.evento.exclusivo_associado = True
        self.evento.beneficio_primeira_compra = True
        self.evento.save()
        pedido = self.criar_pedido(quantidade=1)
        pedido.associado = True
        pedido.save(update_fields=['associado'])
        self.client.force_login(self.operador)

        self.executar_acao(pedido)

        self.assertEqual(pedido.ingressos.count(), 2)
        enviar_email.assert_called_once()

    @patch('ingressos.admin.enviar_email_ingressos')
    def test_beneficio_usado_por_pix_nao_se_repete_em_cesta(self, enviar_email):
        self.evento.exclusivo_associado = True
        self.evento.beneficio_primeira_compra = True
        self.evento.save()
        anterior = self.criar_pedido(status='PAGO')
        anterior.forma_pagamento = 'PIX'
        anterior.associado = True
        anterior.save(update_fields=['forma_pagamento', 'associado'])
        Ingresso.objects.create(
            pedido=anterior, evento=self.evento, nome_comprador=anterior.nome,
            email=anterior.email, telefone=anterior.telefone, cpf=anterior.cpf,
            associado=True, forma_pagamento='PIX',
        )
        cesta = self.criar_pedido(quantidade=2)
        cesta.associado = True
        cesta.save(update_fields=['associado'])
        self.client.force_login(self.operador)

        self.executar_acao(cesta)

        self.assertEqual(cesta.ingressos.count(), 2)


@override_settings(ASAAS_WEBHOOK_TOKEN='token-teste')
class CartaoCreditoPorEventoTests(TestCase):
    def setUp(self):
        self.evento_com_cartao = self.criar_evento(True)
        self.evento_sem_cartao = self.criar_evento(False)
        self.dados = {
            'nome': 'Comprador Teste',
            'email': 'comprador@example.com',
            'telefone': '11999999999',
            'cpf': '12345678901',
            'quantidade': 1,
        }

    def criar_evento(self, aceita_cartao_credito):
        return Evento.objects.create(
            nome=f'Evento cartão {aceita_cartao_credito}',
            data=timezone.now() + timedelta(days=1),
            local='Auditório',
            valor='100.00',
            valor_associado='80.00',
            valor_nao_associado='100.00',
            quantidade_total=100,
            quantidade_associado=50,
            quantidade_nao_associado=50,
            aceita_cartao_credito=aceita_cartao_credito,
        )

    def comprar(self, evento, forma, follow=False):
        return self.client.post(
            reverse('comprar_ingresso', args=[evento.pk]),
            {**self.dados, 'forma_pagamento': forma},
            follow=follow,
        )

    def test_checkout_mostra_cartao_somente_quando_habilitado(self):
        habilitado = self.client.get(reverse(
            'comprar_ingresso', args=[self.evento_com_cartao.pk]
        ))
        desabilitado = self.client.get(reverse(
            'comprar_ingresso', args=[self.evento_sem_cartao.pk]
        ))

        self.assertContains(habilitado, 'value="CREDIT_CARD"')
        self.assertContains(habilitado, 'id="parcelas-box"')
        self.assertNotContains(desabilitado, 'value="CREDIT_CARD"')
        self.assertNotContains(desabilitado, 'id="parcelas-box"')
        for response in (habilitado, desabilitado):
            self.assertContains(response, 'value="PIX"')
            self.assertContains(response, 'value="CESTA_BASICA"')

    @patch('ingressos.views.criar_pagamento_asaas')
    def test_evento_habilitado_aceita_cartao(self, criar_asaas):
        criar_asaas.return_value = {
            'id': 'pay-cartao-habilitado',
            'invoiceUrl': '/fatura/',
        }

        response = self.comprar(self.evento_com_cartao, 'CREDIT_CARD')

        self.assertRedirects(response, '/fatura/', fetch_redirect_response=False)
        self.assertTrue(Pedido.objects.filter(
            evento=self.evento_com_cartao,
            forma_pagamento='CREDIT_CARD',
        ).exists())
        criar_asaas.assert_called_once()

    @patch('ingressos.views.criar_pagamento_asaas')
    def test_post_adulterado_rejeita_cartao_sem_criar_pedido(self, criar_asaas):
        response = self.comprar(
            self.evento_sem_cartao, 'CREDIT_CARD', follow=True
        )

        self.assertContains(
            response,
            'Cartão de crédito não está disponível para este evento.'
        )
        self.assertFalse(Pedido.objects.exists())
        criar_asaas.assert_not_called()

    @patch('ingressos.views.criar_pagamento_asaas')
    def test_pix_funciona_com_cartao_habilitado_ou_desabilitado(self, criar_asaas):
        criar_asaas.side_effect = [
            {'id': 'pay-pix-1', 'invoiceUrl': '/fatura/1/'},
            {'id': 'pay-pix-2', 'invoiceUrl': '/fatura/2/'},
        ]

        for evento in (self.evento_com_cartao, self.evento_sem_cartao):
            with self.subTest(aceita_cartao=evento.aceita_cartao_credito):
                self.comprar(evento, 'PIX')

        self.assertEqual(Pedido.objects.filter(forma_pagamento='PIX').count(), 2)
        self.assertEqual(criar_asaas.call_count, 2)

    @patch('ingressos.views.criar_pagamento_asaas')
    def test_cesta_funciona_nos_dois_tipos_sem_asaas(self, criar_asaas):
        for evento in (self.evento_com_cartao, self.evento_sem_cartao):
            with self.subTest(aceita_cartao=evento.aceita_cartao_credito):
                self.comprar(evento, 'CESTA_BASICA')

        self.assertEqual(Pedido.objects.filter(
            forma_pagamento='CESTA_BASICA'
        ).count(), 2)
        criar_asaas.assert_not_called()

    def test_cartao_historico_permanece_no_dashboard_e_csv(self):
        ingresso = Ingresso.objects.create(
            evento=self.evento_sem_cartao,
            nome_comprador='Compra histórica no cartão',
            email='historico@example.com',
            telefone='11999999999',
            cpf='12345678901',
            forma_pagamento='CREDIT_CARD',
        )
        usuario = get_user_model().objects.create_user(
            username='operador-historico', password='senha'
        )
        self.client.force_login(usuario)

        dashboard = self.client.get(reverse('ingressos_vendidos'))
        csv_response = self.client.get(reverse('exportar_csv'))

        self.assertContains(dashboard, ingresso.nome_comprador)
        self.assertContains(dashboard, 'Cartão de Crédito')
        self.assertIn(
            'Cartão de Crédito', csv_response.content.decode('utf-8')
        )

    @patch('ingressos.views.enviar_email_ingressos')
    def test_webhook_processa_pedido_antigo_de_cartao(self, enviar_email):
        pedido = Pedido.objects.create(
            evento=self.evento_sem_cartao,
            nome='Compra histórica',
            email='historico@example.com',
            telefone='11999999999',
            cpf='12345678901',
            quantidade=1,
            valor_total='100.00',
            asaas_payment_id='pay-cartao-historico',
            status='PENDENTE',
            forma_pagamento='CREDIT_CARD',
        )

        response = self.client.post(
            reverse('webhook_asaas'),
            data=json.dumps({
                'event': 'PAYMENT_CONFIRMED',
                'payment': {'id': pedido.asaas_payment_id},
            }),
            content_type='application/json',
            HTTP_ASAAS_ACCESS_TOKEN='token-teste',
        )

        pedido.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(pedido.status, 'PAGO')
        self.assertEqual(pedido.ingressos.count(), 1)
        self.assertEqual(
            pedido.ingressos.get().forma_pagamento, 'CREDIT_CARD'
        )
        enviar_email.assert_called_once()


@override_settings(ASAAS_WEBHOOK_TOKEN='token-teste')
class FluxoBeneficioPrimeiraCompraTests(TestCase):
    cpf = '12345678901'

    def setUp(self):
        self.evento = Evento.objects.create(
            nome='Evento exclusivo',
            data=timezone.now() + timedelta(days=1),
            local='AMBr',
            valor='77.00',
            valor_associado='77.00',
            valor_nao_associado='77.00',
            quantidade_total=100,
            quantidade_associado=100,
            quantidade_nao_associado=0,
            exclusivo_associado=True,
            beneficio_primeira_compra=True,
        )
        session = self.client.session
        session.update({
            'associado_validado': True,
            'associado_nome': 'Associado Teste',
            'associado_email': 'associado@example.com',
            'associado_telefone': '11999999999',
            'associado_cpf': self.cpf,
        })
        session.save()

    def comprar(self, forma, quantidade, payment_id=None):
        dados = {'forma_pagamento': forma, 'quantidade': quantidade}
        if forma == 'CESTA_BASICA':
            return self.client.post(
                reverse('comprar_ingresso', args=[self.evento.pk]),
                dados,
                follow=True,
            )
        retorno = {
            'id': payment_id or f'pay-{Pedido.objects.count() + 1}',
            'invoiceUrl': '/fatura/',
        }
        with patch('ingressos.views.criar_pagamento_asaas', return_value=retorno):
            return self.client.post(
                reverse('comprar_ingresso', args=[self.evento.pk]), dados
            )

    def webhook(self, pedido):
        return self.client.post(
            reverse('webhook_asaas'),
            data=json.dumps({
                'event': 'PAYMENT_CONFIRMED',
                'payment': {'id': pedido.asaas_payment_id},
            }),
            content_type='application/json',
            HTTP_ASAAS_ACCESS_TOKEN='token-teste',
        )

    def criar_ingresso_confirmado(self, forma='PIX', cpf=None):
        pedido = Pedido.objects.create(
            evento=self.evento, nome='Anterior', email='a@example.com',
            telefone='11999999999', cpf=cpf or self.cpf, associado=True,
            quantidade=1, valor_total='77.00', status='PAGO',
            forma_pagamento=forma,
        )
        return Ingresso.objects.create(
            pedido=pedido, evento=self.evento, nome_comprador=pedido.nome,
            email=pedido.email, telefone=pedido.telefone, cpf=pedido.cpf,
            associado=True, forma_pagamento=forma,
        )

    @patch('ingressos.views.enviar_email_ingressos')
    def test_pix_primeira_e_segunda_compra(self, enviar_email):
        for quantidade, esperados in ((1, 2), (2, 3)):
            with self.subTest(primeira_quantidade=quantidade):
                Ingresso.objects.all().delete()
                Pedido.objects.all().delete()
                self.comprar('PIX', quantidade)
                pedido = Pedido.objects.get()
                self.assertEqual(pedido.valor_total, Decimal('77') * quantidade)
                self.webhook(pedido)
                self.assertEqual(pedido.ingressos.count(), esperados)

        Ingresso.objects.all().delete()
        Pedido.objects.all().delete()
        self.criar_ingresso_confirmado('PIX')
        self.comprar('PIX', 2)
        pedido = Pedido.objects.latest('id')
        self.webhook(pedido)
        self.assertEqual(pedido.ingressos.count(), 2)

    @patch('ingressos.views.enviar_email_ingressos')
    def test_cartao_primeira_e_segunda_compra(self, enviar_email):
        for quantidade, esperados in ((1, 2), (2, 3)):
            with self.subTest(primeira_quantidade=quantidade):
                Ingresso.objects.all().delete()
                Pedido.objects.all().delete()
                self.comprar('CREDIT_CARD', quantidade)
                pedido = Pedido.objects.get()
                self.assertEqual(pedido.valor_total, Decimal('77') * quantidade)
                self.webhook(pedido)
                self.assertEqual(pedido.ingressos.count(), esperados)

        Ingresso.objects.all().delete()
        Pedido.objects.all().delete()
        self.criar_ingresso_confirmado('CREDIT_CARD')
        self.comprar('CREDIT_CARD', 2)
        pedido = Pedido.objects.latest('id')
        self.webhook(pedido)
        self.assertEqual(pedido.ingressos.count(), 2)

    @patch('ingressos.views.criar_pagamento_asaas')
    @patch('ingressos.views.enviar_email_ingressos')
    def test_cesta_fica_pendente_sem_asaas_email_ou_ingresso(
        self, enviar_email, criar_asaas
    ):
        response = self.comprar('CESTA_BASICA', 2)
        pedido = Pedido.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [(reverse('pedido_cesta_basica', args=[pedido.pk]), 302)],
        )
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(pedido.status, 'PENDENTE')
        self.assertEqual(pedido.quantidade, 2)
        self.assertEqual(pedido.valor_total, Decimal('154.00'))
        self.assertFalse(pedido.ingressos.exists())
        criar_asaas.assert_not_called()
        enviar_email.assert_not_called()
        self.assertContains(response, 'Convites previstos:</strong> 3')

    def test_pendente_e_cancelado_nao_consumem_beneficio(self):
        for status in ('PENDENTE', 'CANCELADO'):
            Pedido.objects.create(
                evento=self.evento, nome='Sem benefício', email='a@example.com',
                telefone='1', cpf=self.cpf, associado=True, quantidade=1,
                valor_total='77.00', status=status, forma_pagamento='PIX',
            )
        response = self.comprar('CESTA_BASICA', 1)
        self.assertEqual(Pedido.objects.filter(
            forma_pagamento='CESTA_BASICA'
        ).count(), 1)
        self.assertContains(response, 'Convites previstos:</strong> 2')

    def test_html_previsao_primeira_compra_por_quantidade(self):
        cenarios = (
            (1, 2, None),
            (2, 3, '1 convite adicional'),
            (3, 4, '2 convites adicionais'),
        )
        for quantidade, total, texto_adicional in cenarios:
            with self.subTest(quantidade=quantidade):
                Pedido.objects.all().delete()
                response = self.comprar('CESTA_BASICA', quantidade)
                self.assertContains(response, 'Benefício da primeira compra')
                self.assertContains(
                    response,
                    f'Total previsto: {total} convites.',
                )
                self.assertContains(
                    response,
                    f'Convites previstos:</strong> {total}',
                )
                if texto_adicional:
                    self.assertContains(response, texto_adicional)

    def test_html_compra_seguinte_mostra_quantidade_paga(self):
        self.criar_ingresso_confirmado('PIX')
        response = self.comprar('CESTA_BASICA', 2)
        self.assertContains(response, 'Compra adicional')
        self.assertContains(response, 'benefício da primeira compra já foi utilizado')
        self.assertContains(response, 'Total previsto: 2 convites.')
        self.assertContains(response, 'Convites previstos:</strong> 2')

    def test_html_pedido_que_usou_beneficio_preserva_previsao_original(self):
        response = self.comprar('CESTA_BASICA', 2)
        pedido = Pedido.objects.get()
        pedido.status = 'PAGO'
        pedido.save(update_fields=['status'])
        for _ in range(3):
            Ingresso.objects.create(
                pedido=pedido,
                evento=self.evento,
                nome_comprador=pedido.nome,
                email=pedido.email,
                telefone=pedido.telefone,
                cpf=pedido.cpf,
                associado=True,
                forma_pagamento='CESTA_BASICA',
            )

        response = self.client.get(
            reverse('pedido_cesta_basica', args=[pedido.pk])
        )

        self.assertContains(response, 'Benefício da primeira compra')
        self.assertContains(response, 'Convites previstos:</strong> 3')
        self.assertContains(response, 'Total previsto: 3 convites.')

    @patch('ingressos.views.enviar_email_ingressos')
    def test_webhook_repetido_nao_duplica(self, enviar_email):
        self.comprar('PIX', 1)
        pedido = Pedido.objects.get()
        self.webhook(pedido)
        response = self.webhook(pedido)
        self.assertEqual(pedido.ingressos.count(), 2)
        self.assertEqual(response.json()['status'], 'ja_processado')

    @patch('ingressos.views.enviar_email_ingressos')
    def test_beneficio_usado_por_cesta_nao_se_repete_no_asaas(self, enviar_email):
        self.criar_ingresso_confirmado('CESTA_BASICA')
        for forma in ('PIX', 'CREDIT_CARD'):
            with self.subTest(forma=forma):
                self.comprar(forma, 2)
                pedido = Pedido.objects.latest('id')
                self.webhook(pedido)
                self.assertEqual(pedido.ingressos.count(), 2)

    def test_capacidade_considera_convite_adicional(self):
        self.evento.quantidade_total = 1
        self.evento.quantidade_associado = 1
        self.evento.save()
        response = self.comprar('CESTA_BASICA', 1)
        self.assertContains(response, 'Quantidade indisponível')
        self.assertFalse(Pedido.objects.exists())
