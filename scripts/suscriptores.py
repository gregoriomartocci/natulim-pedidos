"""Requerimiento 1: suscriptores nuevos de los últimos 6 meses, península contra Canarias.

En producción la fuente es Recharge (no está instalada en la dev store). Este
script usa lo que Recharge deja en Shopify: el primer pedido de cada
suscripción lleva el tag "Subscription First Order". Un suscriptor nuevo es
un cliente con al menos un primer pedido de suscripción en el período.

Supuestos (ver log.md; confirmados o no con el Lead Tech):
- "Península" = España peninsular: sin Baleares, Canarias, Ceuta ni Melilla.
- La región es la de la dirección de envío de ese primer pedido.
- Los pedidos de más de 60 días necesitan el scope read_all_orders.

Uso:
    uv run python -m scripts.suscriptores            # últimos 6 meses
    uv run python -m scripts.suscriptores --tag "Subscription First Order" --meses 6
"""

import argparse
import sys
from collections import Counter
from datetime import date

from app.config import cargar
from app.regiones import region
from app.shopify import Shopify

_PEDIDOS = """
query Primeros($cursor: String, $q: String!) {
  orders(first: 250, after: $cursor, query: $q) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      createdAt
      customer { id }
      shippingAddress { countryCodeV2 provinceCode zip }
    }
  }
}
"""


def restar_meses(d: date, meses: int) -> date:
    mes = d.month - meses
    anio = d.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    return d.replace(year=anio, month=mes, day=min(d.day, 28))


def contar(pedidos: list[dict]) -> Counter:
    """Un suscriptor cuenta una vez, en la región de su primer pedido de suscripción."""
    vistos: dict[str, str] = {}
    for p in sorted(pedidos, key=lambda p: p["createdAt"]):
        quien = (p.get("customer") or {}).get("id") or p["id"]  # sin cliente: se cuenta el pedido
        if quien not in vistos:
            vistos[quien] = region(p.get("shippingAddress")) or "sin_direccion"
    return Counter(vistos.values())


def mensaje(conteo: Counter, desde: date, hasta: date) -> str:
    pen, can = conteo.get("peninsula", 0), conteo.get("canarias", 0)
    proporcion = f"{pen / can:.1f} a 1" if can else "sin suscriptores en Canarias"
    return (
        f"Suscriptores nuevos del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}: "
        f"península {pen}, Canarias {can} ({proporcion}). "
        f"Fuera de esos dos: {sum(conteo.values()) - pen - can}."
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", type=int, default=6)
    ap.add_argument("--tag", default="Subscription First Order")
    args = ap.parse_args(argv)

    hasta = date.today()
    desde = restar_meses(hasta, args.meses)
    q = f"created_at:>={desde.isoformat()} tag:'{args.tag}'"
    shopify = Shopify(cargar())
    pedidos, cursor = [], None
    while True:
        pagina = shopify.graphql(_PEDIDOS, {"cursor": cursor, "q": q})["orders"]
        pedidos += pagina["nodes"]
        if not pagina["pageInfo"]["hasNextPage"]:
            break
        cursor = pagina["pageInfo"]["endCursor"]

    conteo = contar(pedidos)
    print(f"Pedidos con tag '{args.tag}' desde {desde}: {len(pedidos)}")
    for reg, n in conteo.most_common():
        print(f"  {reg:<16} {n}")
    print()
    print(mensaje(conteo, desde, hasta))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
