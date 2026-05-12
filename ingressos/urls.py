from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_eventos, name='lista_eventos'),
    path('comprar/<int:evento_id>/', views.comprar_ingresso, name='comprar_ingresso'),
    path('sucesso/<int:ingresso_id>/', views.ingresso_sucesso, name='ingresso_sucesso'),
    path('vendidos/', views.ingressos_vendidos, name='ingressos_vendidos'),
]