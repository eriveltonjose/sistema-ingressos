from django.db.models import Q

from .models import Ingresso


def evento_tem_beneficio(evento, associado):
    return bool(
        evento.exclusivo_associado
        and evento.beneficio_primeira_compra
        and associado
    )


def beneficio_ja_utilizado(evento, cpf, pedido_excluido=None):
    """Considera ingressos válidos de pedidos pagos e ingressos antigos."""
    ingressos = Ingresso.objects.filter(
        Q(pedido__status='PAGO') | Q(pedido__isnull=True),
        evento=evento,
        cpf=cpf,
        associado=True,
        cancelado=False,
    )
    if pedido_excluido is not None:
        ingressos = ingressos.exclude(pedido=pedido_excluido)
    return ingressos.exists()


def calcular_quantidade_convites(
    evento,
    cpf,
    associado,
    quantidade,
    pedido_excluido=None,
):
    primeira_compra = (
        evento_tem_beneficio(evento, associado)
        and not beneficio_ja_utilizado(evento, cpf, pedido_excluido)
    )
    return quantidade + (1 if primeira_compra else 0), primeira_compra


def detalhar_previsao_convites(
    evento,
    cpf,
    associado,
    quantidade,
    pedido_excluido=None,
):
    quantidade_convites, primeira_compra = calcular_quantidade_convites(
        evento,
        cpf,
        associado,
        quantidade,
        pedido_excluido=pedido_excluido,
    )
    return {
        'quantidade_convites': quantidade_convites,
        'primeira_compra': primeira_compra,
        'convites_adicionais': max(0, quantidade_convites - 2),
    }


def calcular_disponibilidade(evento, associado):
    ingressos_validos = Ingresso.objects.filter(
        evento=evento,
        cancelado=False,
    )
    total_disponivel = evento.quantidade_total - ingressos_validos.count()
    limite_modalidade = (
        evento.quantidade_associado
        if associado
        else evento.quantidade_nao_associado
    )
    vendidos_modalidade = ingressos_validos.filter(
        associado=associado
    ).count()
    return max(0, min(
        total_disponivel,
        limite_modalidade - vendidos_modalidade,
    ))
