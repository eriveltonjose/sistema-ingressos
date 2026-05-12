from django.db import models
import uuid


class Evento(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    data = models.DateTimeField()
    local = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=8, decimal_places=2)
    quantidade_total = models.PositiveIntegerField()

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
# Create your models here.
