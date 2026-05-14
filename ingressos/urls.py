from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_eventos, name='lista_eventos'),
    path('comprar/<int:evento_id>/', views.comprar_ingresso, name='comprar_ingresso'),
    path('sucesso/<int:ingresso_id>/', views.ingresso_sucesso, name='ingresso_sucesso'),
    path('vendidos/', views.ingressos_vendidos, name='ingressos_vendidos'),
    path('validar/<uuid:codigo>/', views.validar_ingresso, name='validar_ingresso'),
    path('sucesso-compra/', views.sucesso_compra, name='sucesso_compra'), 
    path('baixar-pdf/', views.baixar_pdf_ingressos, name='baixar_pdf_ingressos'),
    path('exportar-csv/', views.exportar_csv, name='exportar_csv'),
    path('testar-email/', views.testar_email, name='testar_email'),
    path('webhook/asaas/', views.webhook_asaas, name='webhook_asaas'),
    path('checkin/', views.checkin_scanner, name='checkin_scanner'),
]
