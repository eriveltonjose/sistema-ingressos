from django.contrib import admin
from .models import Evento, Ingresso, Pedido, ValidacaoAssociado
from .views import enviar_email_ingressos

admin.site.register(ValidacaoAssociado)

admin.site.register(Evento)

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

admin.site.register(Pedido)
# Register your models here.
