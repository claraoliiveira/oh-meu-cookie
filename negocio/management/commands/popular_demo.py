from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from negocio.models import Ingredient, Product, Recipe, RecipeItem


class Command(BaseCommand):
    help = "Cria os ingredientes, receitas e produtos iniciais da planilha."

    def handle(self, *args, **options):
        costs = [
            ("Farinha de trigo", "g", 1000, "3.99"),
            ("Açúcar Cristal", "g", 1000, "2.95"),
            ("Açúcar Mascavo", "g", 1000, "17.25"),
            ("Ovos", "un", 30, "23.00"),
            ("Manteiga", "g", 500, "15.99"),
            ("Essência de baunilha", "ml", 30, "6.99"),
            ("Gotas de chocolate", "g", 1010, "27.50"),
            ("Bicarbonato de sódio", "g", 150, "2.15"),
            ("Fermento Royal", "g", 250, "12.95"),
            ("Chocolate 50%", "g", 200, "33.95"),
            ("Nutella", "g", 750, "57.99"),
            ("Marshmallow grande", "un", 80, "7.79"),
            ("Marshmallow mini", "un", 70, "7.75"),
        ]
        ingredients = {}
        for name, unit, quantity, price in costs:
            ingredient, _ = Ingredient.objects.update_or_create(
                name=name,
                defaults={
                    "unit": unit,
                    "package_quantity": quantity,
                    "package_price": Decimal(price),
                    "current_stock": Decimal(quantity),
                    "minimum_stock": Decimal(quantity) * Decimal("0.15"),
                },
            )
            ingredients[name] = ingredient

        base_items = [
            ("Farinha de trigo", 340),
            ("Açúcar Cristal", 100),
            ("Açúcar Mascavo", 100),
            ("Ovos", 2),
            ("Manteiga", 110),
            ("Essência de baunilha", 7),
            ("Gotas de chocolate", 235),
            ("Bicarbonato de sódio", 7),
            ("Fermento Royal", 7),
        ]
        recipes = [
            ("Cookies tradicionais 40g", 23, "2.50", base_items, "Cookie artesanal com gotas de chocolate."),
            ("Cookies 100g", 9, "7.00", base_items, "Cookie grande, macio por dentro e dourado por fora."),
            (
                "Cookies de chocolate 40g",
                23,
                "3.50",
                base_items + [("Chocolate 50%", 35)],
                "Massa de chocolate com gotas generosas.",
            ),
            (
                "Cookie tradicional com marshmallow",
                23,
                "3.50",
                base_items + [("Marshmallow mini", 6)],
                "Tradicional com marshmallow macio.",
            ),
            (
                "Cookie recheado 100g",
                11,
                "6.00",
                [(name, qty) for name, qty in base_items if name != "Manteiga"] + [("Manteiga", 100), ("Nutella", 15)],
                "80g de massa e 20g de recheio cremoso.",
            ),
        ]
        for index, (name, yield_quantity, price, items, description) in enumerate(recipes):
            recipe, _ = Recipe.objects.update_or_create(
                name=name,
                defaults={"yield_quantity": yield_quantity, "extra_cost": Decimal("3.50")},
            )
            recipe.items.all().delete()
            for ingredient_name, quantity in items:
                RecipeItem.objects.create(recipe=recipe, ingredient=ingredients[ingredient_name], quantity=quantity)
            Product.objects.update_or_create(
                name=name,
                defaults={
                    "recipe": recipe,
                    "description": description,
                    "weight_grams": 100 if "100g" in name else 40,
                    "sale_price": Decimal(price),
                    "available_quantity": 20,
                    "featured": index < 2,
                },
            )

        User = get_user_model()
        if not User.objects.filter(username="clara").exists():
            User.objects.create_superuser("clara", "", "troque-esta-senha")
            self.stdout.write(self.style.WARNING("Usuária inicial: clara | senha: troque-esta-senha"))
        self.stdout.write(self.style.SUCCESS("Dados iniciais criados com sucesso."))
