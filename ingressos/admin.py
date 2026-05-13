from django.contrib import admin
from django.contrib import admin
from .models import Evento, Ingresso
from .models import Evento, Ingresso, Pedido

admin.site.register(Evento)
admin.site.register(Ingresso)
admin.site.register(Pedido)
# Register your models here.
