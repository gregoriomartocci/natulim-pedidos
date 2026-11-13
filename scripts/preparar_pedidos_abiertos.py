"""Requerimiento 4, el día del despliegue: anota la región de envío de los
pedidos abiertos que ya existían.

Sin esto, si CX cambia a Canarias la dirección de un pedido creado antes de
desplegar, la app no sabe cuál era la dirección anterior y no lo marca (lo
toma como punto de partida). Se corre una vez, después de registrar los
webhooks. No etiqueta nada: solo deja el punto de partida.

Uso:
    uv run python -m scripts.preparar_pedidos_abiertos
"""

import sys

from app.marcar import CLAVE, NAMESPACE, _anotar
from app.regiones import es_canarias
from app.config import cargar
from app.shopify import Shopify

_PEDIDOS = """
query Abiertos($cursor: String) {
  orders(first: 100, after: $cursor, query: "status:open fulfillment_status:unshipped") {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      name
      shippingAddress { countryCodeV2 provinceCode zip }
      metafield(namespace: "%s", key: "%s") { value }
    }
  }
}
""" % (NAMESPACE, CLAVE)


def main() -> int:
    shopify = Shopify(cargar())
    cursor, anotados, ya = None, 0, 0
    while True:
        pagina = shopify.graphql(_PEDIDOS, {"cursor": cursor})["orders"]
        for pedido in pagina["nodes"]:
            if pedido.get("metafield"):
                ya += 1
                continue
            _anotar(shopify, pedido["id"], es_canarias(pedido.get("shippingAddress")))
            anotados += 1
        if not pagina["pageInfo"]["hasNextPage"]:
            break
        cursor = pagina["pageInfo"]["endCursor"]
    print(f"Pedidos abiertos anotados: {anotados}. Ya tenían punto de partida: {ya}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
