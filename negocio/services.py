from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import CashEntry, Ingredient, ProductionBatch, Receivable, StockMovement


@transaction.atomic
def registrar_entrada_estoque(ingredient, quantity, amount=Decimal("0"), description="Compra de insumo"):
    locked = Ingredient.objects.select_for_update().get(pk=ingredient.pk)
    locked.current_stock += quantity
    locked.save(update_fields=["current_stock"])
    return StockMovement.objects.create(
        ingredient=locked,
        movement_type=StockMovement.Type.PURCHASE,
        quantity=quantity,
        amount=amount,
        description=description,
    )


@transaction.atomic
def registrar_producao(recipe, batches=Decimal("1"), notes=""):
    shortages = []
    requirements = []
    for item in recipe.items.select_related("ingredient"):
        ingredient = Ingredient.objects.select_for_update().get(pk=item.ingredient_id)
        needed = item.quantity * batches
        requirements.append((ingredient, needed))
        if ingredient.current_stock < needed:
            shortages.append(f"{ingredient.name}: precisa {needed} {ingredient.unit}, possui {ingredient.current_stock}")

    if shortages:
        raise ValidationError("Estoque insuficiente: " + "; ".join(shortages))

    batch = ProductionBatch.objects.create(
        recipe=recipe,
        batches=batches,
        units_produced=int(Decimal(recipe.yield_quantity) * batches),
        status=ProductionBatch.Status.COMPLETED,
        notes=notes,
    )
    for ingredient, needed in requirements:
        ingredient.current_stock -= needed
        ingredient.save(update_fields=["current_stock"])
        StockMovement.objects.create(
            ingredient=ingredient,
            movement_type=StockMovement.Type.PRODUCTION,
            quantity=-needed,
            description=f"Produção #{batch.pk}: {recipe.name}",
        )
    return batch


@transaction.atomic
def marcar_recebivel_pago(receivable, paid_at=None):
    locked = Receivable.objects.select_for_update().select_related("order").get(pk=receivable.pk)
    if locked.status == Receivable.Status.PAID:
        return locked

    locked.status = Receivable.Status.PAID
    locked.paid_at = paid_at or timezone.localdate()
    locked.save(update_fields=["status", "paid_at"])
    if locked.order_id:
        locked.order.payment_status = locked.order.PaymentStatus.PAID
        locked.order.save(update_fields=["payment_status", "updated_at"])
    CashEntry.objects.get_or_create(
        receivable=locked,
        defaults={
            "date": locked.paid_at,
            "description": f"Recebimento — {locked.customer.name}: {locked.description}",
            "kind": CashEntry.Kind.INCOME,
            "amount": locked.amount,
            "order": locked.order,
        },
    )
    return locked
