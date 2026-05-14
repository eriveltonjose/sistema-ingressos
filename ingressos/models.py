from django.db import models
import uuid


class Evento(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    data = models.DateTimeField()
    local = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=8, decimal_places=2)
    quantidade_total = models.PositiveIntegerField()
    banner = models.ImageField(upload_to='eventos/', blank=True, null=True)
	

    def __str__(self):
        return self.nome


class Ingresso(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE)
    nome_comprador = models.CharField(max_length=200)
    email = models.EmailField()
    telefone = models.CharField(max_length=30)
    cpf = models.CharField(max_length=14)

    codigo = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )

    usado = models.BooleanField(default=False)
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
    quantidade = models.PositiveIntegerField(default=1)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    asaas_payment_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - {self.evento.nome} - {self.status}"
# Create your models here.
