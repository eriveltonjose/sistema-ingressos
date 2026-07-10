from django.contrib import admin
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
        'codigo',
        'usado',
        'cancelado',
        'criado_em'
    )

    search_fields = (
        'nome_comprador',
        'cpf',
        'codigo'
    )

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):

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
        'status',
        'associado',
        'evento',
        'forma_pagamento',
    )

    search_fields = (
        'nome',
        'cpf',
        'email',
        'asaas_payment_id',
    )
# Register your models here.
