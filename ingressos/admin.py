from django.contrib import admin, messages
from django.db import transaction

from .models import Evento, Ingresso, Pedido, ValidacaoAssociado
from .views import enviar_email_ingressos

admin.site.register(ValidacaoAssociado)

@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'nome',
        'data',
        'local',
        'ativo',
        'exclusivo_associado',
        'beneficio_primeira_compra',
    )

    list_filter = (
        'ativo',
        'exclusivo_associado',
        'beneficio_primeira_compra',
    )

    search_fields = (
        'nome',
        'local',
    )

    fieldsets = (
        (
            'Informações do evento',
            {
                'fields': (
                    'nome',
                    'descricao',
                    'data',
                    'local',
                    'banner',
                )
            }
        ),
        (
            'Valores',
            {
                'fields': (
                    'valor',
                    'valor_associado',
                    'valor_nao_associado',
                )
            }
        ),
        (
            'Quantidade de ingressos',
            {
                'fields': (
                    'quantidade_total',
                    'quantidade_associado',
                    'quantidade_nao_associado',
                )
            }
        ),
        (
            'Regra especial para associados',
            {
                'fields': (
                    'exclusivo_associado',
                    'beneficio_primeira_compra',
                    'quantidade_primeira_compra',
                    'quantidade_compras_seguintes',
                )
            }
        ),
        (
            'Situação',
            {
                'fields': (
                    'ativo',
                )
            }
        ),
    )

def reenviar_ingresso(modeladmin, request, queryset):

    enviados = 0

    for ingresso in queryset:

        try:
            enviar_email_ingressos(
                [ingresso],
                ingresso.email
            )

            enviados += 1

        except Exception as erro:

            modeladmin.message_user(
                request,
                f'Erro ao enviar para {ingresso.email}: {erro}'
            )

    modeladmin.message_user(
        request,
        f'{enviados} ingresso(s) reenviado(s) com sucesso.'
    )


reenviar_ingresso.short_description = '📧 Reenviar ingresso por e-mail'
@admin.register(Ingresso)
class IngressoAdmin(admin.ModelAdmin):

    actions = [reenviar_ingresso]

    list_display = (
        'id',
        'pedido',
        'nome_comprador',
        'evento',
        'cpf',
        'associado',
        'usado',
        'cancelado',
        'criado_em',
    )

    list_filter = (
        'evento',
        'associado',
        'usado',
        'cancelado',
        'criado_em',
    )

    search_fields = (
        'nome_comprador',
        'cpf',
        'email',
        'codigo',
        'evento__nome',
    )

    ordering = (
        '-criado_em',
    )

    list_select_related = (
        'evento',
        'pedido',
    )

    date_hierarchy = 'criado_em'



def confirmar_pagamento_presencial(modeladmin, request, queryset):

    processados = 0
    reenviados = 0
    erros = 0

    for pedido_id in queryset.values_list('id', flat=True):

        try:
            with transaction.atomic():

                pedido = (
                    Pedido.objects
                    .select_for_update()
                    .select_related('evento')
                    .get(pk=pedido_id)
                )

                # Evita criar ingressos duplicados
                ingressos_existentes = list(
                    pedido.ingressos.filter(cancelado=False)
                )

                if ingressos_existentes:
                    ingressos_para_email = ingressos_existentes
                    reenviados += 1

                else:
                    evento = pedido.evento

                    # Regra especial do evento exclusivo
                    if (
                        evento.exclusivo_associado
                        and evento.beneficio_primeira_compra
                        and pedido.associado
                    ):

                        ja_comprou = Ingresso.objects.filter(
                            evento=evento,
                            cpf=pedido.cpf,
                            associado=True,
                            cancelado=False
                        ).exclude(
                            pedido=pedido
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
                        quantidade_ingressos = pedido.quantidade

                    ingressos_para_email = []

                    for _ in range(quantidade_ingressos):

                        ingresso = Ingresso.objects.create(
                            pedido=pedido,
                            evento=evento,
                            nome_comprador=pedido.nome,
                            email=pedido.email,
                            telefone=pedido.telefone,
                            cpf=pedido.cpf,
                            associado=pedido.associado,
                            forma_pagamento='CESTA_BASICA',
                        )

                        ingressos_para_email.append(ingresso)

                    pedido.status = 'PAGO'
                    pedido.forma_pagamento = 'CESTA_BASICA'

                    pedido.save(
                        update_fields=[
                            'status',
                            'forma_pagamento',
                        ]
                    )

                    processados += 1

            # Envia depois que os registros foram salvos
            enviar_email_ingressos(
                ingressos_para_email,
                pedido.email
            )

        except Exception as erro:
            erros += 1

            modeladmin.message_user(
                request,
                f'Erro no pedido {pedido_id}: {erro}',
                level=messages.ERROR
            )

    if processados:
        modeladmin.message_user(
            request,
            f'{processados} pagamento(s) presencial(is) confirmado(s), '
            f'com ingressos gerados e enviados.',
            level=messages.SUCCESS
        )

    if reenviados:
        modeladmin.message_user(
            request,
            f'{reenviados} pedido(s) já possuíam ingressos. '
            f'Os ingressos existentes foram reenviados.',
            level=messages.WARNING
        )

    if erros:
        modeladmin.message_user(
            request,
            f'{erros} pedido(s) apresentaram erro.',
            level=messages.ERROR
        )


confirmar_pagamento_presencial.short_description = (
    '🎁 Confirmar pagamento presencial e enviar ingressos'
)    

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):

    actions = [
        confirmar_pagamento_presencial,
    ]

    list_display = (
        'id',
        'nome',
        'evento',
        'cpf',
        'associado',
        'quantidade',
        'valor_total',
        'status',
        'forma_pagamento',
        'criado_em',
    )

    list_filter = (
        'evento',
        'status',
        'associado',
        'forma_pagamento',
        'criado_em',
    )

    search_fields = (
        'nome',
        'cpf',
        'email',
        'asaas_payment_id',
        'evento__nome',
    )

    ordering = (
        '-criado_em',
    )

    list_select_related = (
        'evento',
    )

    date_hierarchy = 'criado_em'
# Register your models here.
