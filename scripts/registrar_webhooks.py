"""Suscribe la app a los webhooks de pedidos apuntando a la URL pública del servidor.

Uso:
    uv run python -m scripts.registrar_webhooks https://mi-servidor.example.com/webhooks
    uv run python -m scripts.registrar_webhooks --listar
    uv run python -m scripts.registrar_webhooks --borrar-todos

Es idempotente: si ya existe una suscripción al mismo tema y URL, no crea otra.
"""

import sys

from app.config import cargar
from app.shopify import Shopify, sin_errores

TEMAS = ["ORDERS_CREATE", "ORDERS_UPDATED", "ORDERS_DELETE"]

_LISTAR = """
query { webhookSubscriptions(first: 50) { nodes { id topic uri } } }
"""

_CREAR = """
mutation Crear($topic: WebhookSubscriptionTopic!, $uri: String!) {
  webhookSubscriptionCreate(topic: $topic, webhookSubscription: { uri: $uri, format: JSON }) {
    webhookSubscription { id topic uri }
    userErrors { field message }
  }
}
"""

_BORRAR = """
mutation Borrar($id: ID!) {
  webhookSubscriptionDelete(id: $id) { userErrors { field message } }
}
"""


def listar(shopify: Shopify) -> list[dict]:
    return shopify.graphql(_LISTAR)["webhookSubscriptions"]["nodes"]


def main(argv: list[str]) -> int:
    shopify = Shopify(cargar())
    if not argv:
        print(__doc__)
        return 1
    if argv[0] == "--listar":
        for w in listar(shopify):
            print(f"{w['topic']:<16} {w['uri']}  ({w['id']})")
        return 0
    if argv[0] == "--borrar-todos":
        for w in listar(shopify):
            sin_errores(shopify.graphql(_BORRAR, {"id": w["id"]})["webhookSubscriptionDelete"], "webhookSubscriptionDelete")
            print(f"borrado {w['topic']} {w['uri']}")
        return 0

    uri = argv[0]
    if not uri.startswith("https://"):
        print("La URL tiene que ser https (Shopify no manda webhooks a http).")
        return 1
    existentes = {(w["topic"], w["uri"]) for w in listar(shopify)}
    for tema in TEMAS:
        if (tema, uri) in existentes:
            print(f"ya estaba   {tema}")
            continue
        r = sin_errores(shopify.graphql(_CREAR, {"topic": tema, "uri": uri})["webhookSubscriptionCreate"], "webhookSubscriptionCreate")
        print(f"registrado  {tema} → {r['webhookSubscription']['uri']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
