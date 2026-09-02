import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.utils import timezone

from .models import AvailablePickupDate, CashEntry, Customer, Ingredient, Order, OrderItem, Product, Receivable, Recipe, RecipeItem
from .services import marcar_recebivel_pago, registrar_producao


class BusinessRulesTests(TestCase):
    def setUp(self):
        self.flour = Ingredient.objects.create(
            name="Farinha", package_quantity=1000, package_price=Decimal("5.00"), current_stock=1000, minimum_stock=100
        )
        self.recipe = Recipe.objects.create(name="Cookie teste", yield_quantity=10, extra_cost=Decimal("0"), overhead_percent=0)
        RecipeItem.objects.create(recipe=self.recipe, ingredient=self.flour, quantity=200)
        self.product = Product.objects.create(name="Cookie teste", recipe=self.recipe, sale_price=Decimal("3.00"))
        self.customer = Customer.objects.create(name="Clara", phone="33999999999")

    def test_recipe_and_unit_cost(self):
        self.assertEqual(self.recipe.total_cost, Decimal("1.00"))
        self.assertEqual(self.recipe.unit_cost, Decimal("0.10"))

    def test_order_total(self):
        order = Order.objects.create(customer=self.customer, delivery_fee=Decimal("2.00"))
        OrderItem.objects.create(order=order, product=self.product, quantity=3, unit_price=self.product.sale_price)
        order.recalculate_total()
        self.assertEqual(order.subtotal, Decimal("9.00"))
        self.assertEqual(order.total, Decimal("11.00"))

    def test_production_deducts_stock(self):
        batch = registrar_producao(self.recipe, Decimal("2"))
        self.flour.refresh_from_db()
        self.assertEqual(batch.units_produced, 20)
        self.assertEqual(self.flour.current_stock, Decimal("600"))

    def test_production_rejects_insufficient_stock(self):
        with self.assertRaises(ValidationError):
            registrar_producao(self.recipe, Decimal("10"))

    def test_paid_receivable_creates_income(self):
        receivable = Receivable.objects.create(customer=self.customer, description="Venda", amount=Decimal("20"))
        marcar_recebivel_pago(receivable)
        receivable.refresh_from_db()
        self.assertEqual(receivable.status, Receivable.Status.PAID)
        self.assertTrue(CashEntry.objects.filter(receivable=receivable, kind=CashEntry.Kind.INCOME, amount=20).exists())


class PublicFlowTests(TestCase):
    def setUp(self):
        ingredient = Ingredient.objects.create(name="Farinha", package_quantity=1000, package_price=5)
        recipe = Recipe.objects.create(name="Cookie", yield_quantity=10)
        RecipeItem.objects.create(recipe=recipe, ingredient=ingredient, quantity=100)
        self.product = Product.objects.create(name="Cookie", recipe=recipe, sale_price=Decimal("3.00"))
        self.pickup_date = AvailablePickupDate.objects.create(pickup_date=timezone.localdate() + timedelta(days=2))
        self.client = Client()

    def test_catalog_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cookie")
        self.assertContains(response, 'href="/entrar/?next=/gestao/"')

    def test_login_redirects_to_management(self):
        get_user_model().objects.create_user("clara", password="senha-forte")
        response = self.client.post(
            "/entrar/?next=/gestao/",
            {"username": "clara", "password": "senha-forte"},
        )
        self.assertRedirects(response, "/gestao/")

    def test_checkout_creates_order(self):
        response = self.client.post(
            "/pedido/finalizar/",
            {
                "name": "Clara",
                "phone": "33999999999",
                "payment_method": "PIX",
                "requested_for": self.pickup_date.pickup_date.isoformat(),
                "items_json": json.dumps([{"product_id": self.product.pk, "quantity": 2}]),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.total, Decimal("6.00"))
        self.assertEqual(order.delivery_type, Order.DeliveryType.PICKUP)
        self.assertEqual(order.delivery_fee, Decimal("0"))

    def test_checkout_rejects_payment_outside_pix_or_card(self):
        response = self.client.post(
            "/pedido/finalizar/",
            {
                "name": "Clara",
                "phone": "33999999999",
                "payment_method": "DINHEIRO",
                "requested_for": self.pickup_date.pickup_date.isoformat(),
                "items_json": json.dumps([{"product_id": self.product.pk, "quantity": 1}]),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_rejects_date_not_released_by_management(self):
        response = self.client.post(
            "/pedido/finalizar/",
            {
                "name": "Clara",
                "phone": "33999999999",
                "payment_method": "PIX",
                "requested_for": (timezone.localdate() + timedelta(days=10)).isoformat(),
                "items_json": json.dumps([{"product_id": self.product.pk, "quantity": 1}]),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_management_can_release_pickup_date(self):
        get_user_model().objects.create_user("clara", password="senha-forte")
        self.client.login(username="clara", password="senha-forte")
        new_date = timezone.localdate() + timedelta(days=7)
        response = self.client.post(
            "/gestao/datas-retirada/",
            {"action": "add", "pickup_date": new_date.isoformat()},
        )
        self.assertRedirects(response, "/gestao/datas-retirada/")
        self.assertTrue(AvailablePickupDate.objects.filter(pickup_date=new_date).exists())

    def test_management_requires_login(self):
        response = self.client.get("/gestao/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/entrar/", response.url)
        self.assertNotContains(self.client.get("/"), "Abrir loja de pedidos")
        get_user_model().objects.create_user("clara", password="senha-forte")
        self.client.login(username="clara", password="senha-forte")
        response = self.client.get("/gestao/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Abrir loja de pedidos")
        self.assertContains(response, "clara")

    def test_management_can_create_and_receive_receivable(self):
        get_user_model().objects.create_user("clara", password="senha-forte")
        self.client.login(username="clara", password="senha-forte")
        response = self.client.post(
            "/gestao/financeiro/",
            {
                "action": "receivable",
                "receivable-customer_name": "Cliente teste",
                "receivable-phone": "33988887777",
                "receivable-description": "Encomenda de cookies",
                "receivable-due_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
                "receivable-amount": "45.90",
            },
        )
        self.assertRedirects(response, "/gestao/financeiro/")
        receivable = Receivable.objects.get()
        self.assertEqual(receivable.customer.name, "Cliente teste")
        self.assertEqual(receivable.amount, Decimal("45.90"))

        response = self.client.post(
            "/gestao/financeiro/",
            {"action": "pay", "receivable_id": receivable.pk},
        )
        self.assertRedirects(response, "/gestao/financeiro/")
        receivable.refresh_from_db()
        self.assertEqual(receivable.status, Receivable.Status.PAID)
        self.assertTrue(CashEntry.objects.filter(receivable=receivable, amount=Decimal("45.90")).exists())

    def test_management_can_create_edit_and_hide_product(self):
        get_user_model().objects.create_user("clara", password="senha-forte")
        self.client.login(username="clara", password="senha-forte")
        response = self.client.post(
            "/gestao/produtos/",
            {
                "action": "add",
                "name": "Cookie novo",
                "description": "Cookie cadastrado pela gestão.",
                "recipe": self.product.recipe_id,
                "weight_grams": 80,
                "sale_price": "8.50",
                "available_quantity": 12,
                "active": "on",
                "featured": "on",
            },
        )
        self.assertRedirects(response, "/gestao/produtos/")
        product = Product.objects.get(name="Cookie novo")
        self.assertEqual(product.sale_price, Decimal("8.50"))
        self.assertTrue(product.active)

        response = self.client.post(
            f"/gestao/produtos/{product.pk}/editar/",
            {
                "name": "Cookie novo editado",
                "description": "Descrição atualizada.",
                "recipe": self.product.recipe_id,
                "weight_grams": 90,
                "sale_price": "9.90",
                "available_quantity": 8,
                "active": "on",
            },
        )
        self.assertRedirects(response, "/gestao/produtos/")
        product.refresh_from_db()
        self.assertEqual(product.name, "Cookie novo editado")
        self.assertEqual(product.sale_price, Decimal("9.90"))

        response = self.client.post(
            "/gestao/produtos/",
            {"action": "toggle", "product_id": product.pk},
        )
        self.assertRedirects(response, "/gestao/produtos/")
        product.refresh_from_db()
        self.assertFalse(product.active)
        self.assertNotContains(self.client.get("/"), "Cookie novo editado")

    def test_product_management_requires_login(self):
        response = self.client.get("/gestao/produtos/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/entrar/", response.url)

        get_user_model().objects.create_user(
            username="gestora-produtos",
            password="senha-segura-123",
        )
        self.client.login(
            username="gestora-produtos",
            password="senha-segura-123",
        )
        response = self.client.get("/gestao/produtos/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Novo produto")
