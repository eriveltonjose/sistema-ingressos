from django.contrib import admin
from .models import Evento, Ingresso, Pedido, ValidacaoAssociado

admin.site.register(ValidacaoAssociado)

admin.site.register(Evento)

@admin.register(Ingresso)
class IngressoAdmin(admin.ModelAdmin):
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
