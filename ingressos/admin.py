from django.contrib import admin
from django.contrib import admin
from .models import Evento, Ingresso
from .models import Evento, Ingresso, Pedido

admin.site.register(Evento)

@admin.register(Ingresso)
class IngressoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'nome_comprador',
        'evento',
        'codigo',
        'usado',
        'criado_em'
    )

    search_fields = (
        'nome_comprador',
        'cpf',
        'codigo'
    )

admin.site.register(Pedido)
# Register your models here.
