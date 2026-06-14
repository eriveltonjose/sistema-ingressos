from django.db import models
from django.core.exceptions import ValidationError
import uuid


class Evento(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    data = models.DateTimeField()
    local = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=8, decimal_places=2)

    valor_associado = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )

    valor_nao_associado = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )

    quantidade_total = models.PositiveIntegerField()

    quantidade_associado = models.PositiveIntegerField(default=0)

    quantidade_nao_associado = models.PositiveIntegerField(default=0)

    ativo = models.BooleanField(
        default=True,
        verbose_name="Evento aberto para vendas"
    )

    banner = models.ImageField(upload_to='eventos/', blank=True, null=True)
	

    def __str__(self):
        return self.nome
    
    def clean(self):
        total_cotas = self.quantidade_associado + self.quantidade_nao_associado

        if total_cotas > self.quantidade_total:
            raise ValidationError(
                'A soma de Quantidade associado + Quantidade não associado não pode ser maior que a Quantidade total.'
            )


class Ingresso(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE)
    nome_comprador = models.CharField(max_length=200)
    email = models.EmailField()
    telefone = models.CharField(max_length=30)
    cpf = models.CharField(max_length=14)
    associado = models.BooleanField(default=False)
    forma_pagamento = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    codigo = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )

    usado = models.BooleanField(default=False)
    data_checkin = models.DateTimeField(null=True, blank=True)
    cancelado = models.BooleanField(default=False)
    data_cancelamento = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome_comprador} - {self.evento.nome}"

class Pedido(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('PAGO', 'Pago'),
        ('CANCELADO', 'Cancelado'),
    ]

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE)
    nome = models.CharField(max_length=200)
    email = models.EmailField()
    telefone = models.CharField(max_length=30)
    cpf = models.CharField(max_length=14)
    associado = models.BooleanField(default=False)
    quantidade = models.PositiveIntegerField(default=1)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    asaas_payment_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    forma_pagamento = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - {self.evento.nome} - {self.status}"
class ValidacaoAssociado(models.Model):
    cpf = models.CharField(max_length=14)
    nome = models.CharField(max_length=200)
    crm = models.CharField(max_length=30, blank=True)
    email = models.EmailField()
    telefone = models.CharField(max_length=30, blank=True)
    codigo = models.CharField(max_length=6)
    confirmado = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - {self.cpf}"
