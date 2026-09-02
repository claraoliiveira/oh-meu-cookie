from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Ingredient(models.Model):
    class Unit(models.TextChoices):
        GRAM = "g", "Grama"
        MILLILITER = "ml", "Mililitro"
        UNIT = "un", "Unidade"

    name = models.CharField("ingrediente", max_length=120, unique=True)
    unit = models.CharField("unidade", max_length=4, choices=Unit.choices, default=Unit.GRAM)
    package_quantity = models.DecimalField("quantidade da embalagem", max_digits=12, decimal_places=3, default=0)
    package_price = models.DecimalField("preço da embalagem", max_digits=12, decimal_places=2, default=0)
    current_stock = models.DecimalField("estoque atual", max_digits=12, decimal_places=3, default=0)
    minimum_stock = models.DecimalField("estoque mínimo", max_digits=12, decimal_places=3, default=0)
    active = models.BooleanField("ativo", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "ingrediente"
        verbose_name_plural = "ingredientes"

    @property
    def unit_cost(self):
        if not self.package_quantity:
            return Decimal("0")
        return self.package_price / self.package_quantity

    @property
    def is_low_stock(self):
        return self.current_stock <= self.minimum_stock

    def __str__(self):
        return self.name


class Recipe(models.Model):
    name = models.CharField("receita", max_length=150, unique=True)
    yield_quantity = models.PositiveIntegerField("rendimento em unidades", default=1)
    extra_cost = models.DecimalField("custo adicional", max_digits=12, decimal_places=2, default=0)
    overhead_percent = models.DecimalField("acréscimo de custos (%)", max_digits=5, decimal_places=2, default=10)
    preparation_minutes = models.PositiveIntegerField("tempo de preparo (min)", default=0)
    active = models.BooleanField("ativa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "receita"
        verbose_name_plural = "receitas"

    @property
    def ingredients_cost(self):
        return sum((item.cost for item in self.items.select_related("ingredient")), Decimal("0"))

    @property
    def total_cost(self):
        base = self.ingredients_cost + self.extra_cost
        return base * (Decimal("1") + self.overhead_percent / Decimal("100"))

    @property
    def unit_cost(self):
        if not self.yield_quantity:
            return Decimal("0")
        return self.total_cost / self.yield_quantity

    def __str__(self):
        return self.name


class RecipeItem(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="items", verbose_name="receita")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="recipe_items", verbose_name="ingrediente")
    quantity = models.DecimalField("quantidade utilizada", max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])

    class Meta:
        unique_together = ("recipe", "ingredient")
        ordering = ["id"]
        verbose_name = "item da receita"
        verbose_name_plural = "itens da receita"

    @property
    def cost(self):
        return self.quantity * self.ingredient.unit_cost

    def __str__(self):
        return f"{self.ingredient} — {self.quantity} {self.ingredient.unit}"


class Product(models.Model):
    name = models.CharField("produto", max_length=150)
    description = models.TextField("descrição", blank=True)
    recipe = models.ForeignKey(Recipe, on_delete=models.PROTECT, related_name="products", verbose_name="receita")
    weight_grams = models.PositiveIntegerField("peso (g)", null=True, blank=True)
    sale_price = models.DecimalField("preço de venda", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    available_quantity = models.PositiveIntegerField("quantidade pronta", default=0)
    active = models.BooleanField("disponível na loja", default=True)
    featured = models.BooleanField("destaque", default=False)

    class Meta:
        ordering = ["-featured", "name"]
        verbose_name = "produto"
        verbose_name_plural = "produtos"

    @property
    def unit_cost(self):
        return self.recipe.unit_cost

    @property
    def unit_profit(self):
        return self.sale_price - self.unit_cost

    @property
    def markup_percent(self):
        if not self.unit_cost:
            return Decimal("0")
        return (self.sale_price / self.unit_cost - Decimal("1")) * Decimal("100")

    def __str__(self):
        return self.name


class Customer(models.Model):
    name = models.CharField("nome", max_length=120)
    phone = models.CharField("celular", max_length=30, db_index=True)
    email = models.EmailField("e-mail", blank=True)
    address = models.CharField("endereço", max_length=255, blank=True)
    birthday = models.DateField("aniversário", null=True, blank=True)
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self):
        return f"{self.name} — {self.phone}"


class AvailablePickupDate(models.Model):
    pickup_date = models.DateField("data disponível", unique=True, db_index=True)
    active = models.BooleanField("disponível para pedidos", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pickup_date"]
        verbose_name = "data de retirada"
        verbose_name_plural = "datas de retirada"

    def clean(self):
        super().clean()
        if self.pickup_date and self.pickup_date < timezone.localdate():
            from django.core.exceptions import ValidationError

            raise ValidationError({"pickup_date": "A data de retirada não pode estar no passado."})

    def __str__(self):
        return self.pickup_date.strftime("%d/%m/%Y")


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "NOVO", "Novo"
        APPROVED = "CONFIRMADO", "Aprovado"
        PREPARING = "EM_PREPARO", "Em preparo"
        READY = "PRONTO", "Pronto"
        COMPLETED = "CONCLUIDO", "Concluído"
        CANCELLED = "CANCELADO", "Cancelado"

    class DeliveryType(models.TextChoices):
        PICKUP = "RETIRADA", "Retirada"

    class PaymentMethod(models.TextChoices):
        PIX = "PIX", "Pix"
        CARD = "CARTAO", "Cartão"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDENTE", "Pendente"
        PAID = "PAGO", "Pago"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders", verbose_name="cliente")
    status = models.CharField("status", max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    delivery_type = models.CharField("recebimento", max_length=10, choices=DeliveryType.choices, default=DeliveryType.PICKUP)
    delivery_address = models.CharField("endereço de entrega", max_length=255, blank=True)
    requested_for = models.DateTimeField("data desejada", null=True, blank=True)
    payment_method = models.CharField("forma de pagamento", max_length=15, choices=PaymentMethod.choices, default=PaymentMethod.PIX)
    payment_status = models.CharField("pagamento", max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_fee = models.DecimalField("taxa de entrega", max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField("observações", blank=True)
    stock_deducted_at = models.DateTimeField("estoque baixado em", null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"

    def recalculate_total(self, save=True):
        self.subtotal = sum((item.subtotal for item in self.items.all()), Decimal("0"))
        self.total = self.subtotal + self.delivery_fee
        if save:
            self.save(update_fields=["subtotal", "total", "updated_at"])
        return self.total

    def __str__(self):
        return f"Pedido #{self.pk} — {self.customer.name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="pedido")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items", verbose_name="produto")
    quantity = models.PositiveIntegerField("quantidade", validators=[MinValueValidator(1)])
    unit_price = models.DecimalField("valor unitário", max_digits=12, decimal_places=2)

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.product}"


class StockMovement(models.Model):
    class Type(models.TextChoices):
        PURCHASE = "COMPRA", "Compra/entrada"
        PRODUCTION = "PRODUCAO", "Uso em produção"
        ADJUSTMENT = "AJUSTE", "Ajuste"

    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="movements", verbose_name="ingrediente")
    movement_type = models.CharField("tipo", max_length=12, choices=Type.choices)
    quantity = models.DecimalField("quantidade (+ entrada / - saída)", max_digits=12, decimal_places=3)
    amount = models.DecimalField("valor da movimentação", max_digits=12, decimal_places=2, default=0)
    description = models.CharField("descrição", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "movimentação de estoque"
        verbose_name_plural = "movimentações de estoque"


class ProductionBatch(models.Model):
    class Status(models.TextChoices):
        PLANNED = "PLANEJADA", "Planejada"
        COMPLETED = "CONCLUIDA", "Concluída"
        CANCELLED = "CANCELADA", "Cancelada"

    recipe = models.ForeignKey(Recipe, on_delete=models.PROTECT, related_name="batches", verbose_name="receita")
    batches = models.DecimalField("quantidade de receitas", max_digits=8, decimal_places=2, default=1)
    units_produced = models.PositiveIntegerField("unidades produzidas", default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANNED)
    notes = models.CharField("observações", max_length=255, blank=True)
    produced_at = models.DateTimeField("produzido em", default=timezone.now)

    class Meta:
        ordering = ["-produced_at"]
        verbose_name = "produção"
        verbose_name_plural = "produções"


class Receivable(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDENTE", "Pendente"
        PAID = "PAGO", "Pago"

    order = models.OneToOneField(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="receivable", verbose_name="pedido")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="receivables", verbose_name="cliente")
    description = models.CharField("descrição", max_length=200)
    due_date = models.DateField("vencimento", null=True, blank=True)
    amount = models.DecimalField("valor", max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    paid_at = models.DateField("data do pagamento", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "due_date", "-created_at"]
        verbose_name = "conta a receber"
        verbose_name_plural = "contas a receber"

    @property
    def is_overdue(self):
        return bool(self.status == self.Status.PENDING and self.due_date and self.due_date < timezone.localdate())


class CashEntry(models.Model):
    class Kind(models.TextChoices):
        INCOME = "ENTRADA", "Entrada"
        EXPENSE = "SAIDA", "Saída"

    date = models.DateField("data", default=timezone.localdate, db_index=True)
    description = models.CharField("descrição", max_length=200)
    kind = models.CharField("tipo", max_length=8, choices=Kind.choices)
    amount = models.DecimalField("valor", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="cash_entries")
    receivable = models.OneToOneField(Receivable, on_delete=models.SET_NULL, null=True, blank=True, related_name="cash_entry")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "lançamento de caixa"
        verbose_name_plural = "lançamentos de caixa"

    def __str__(self):
        return f"{self.date:%d/%m/%Y} — {self.description}"
