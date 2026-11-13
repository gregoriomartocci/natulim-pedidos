"""Requerimiento 4: etiquetar pedidos cuya dirección de envío pasa a Canarias.

El problema es saber que la dirección CAMBIÓ: el webhook `orders/updated` trae
la dirección de ahora, no la de antes. Sin base de datos propia, la última
región conocida se guarda en el propio pedido, en un metacampo
(`natulim.envio_canarias`, booleano). Así:

- orders/create  → se anota si el pedido nace con envío a Canarias.
- orders/updated → si ahora es Canarias y antes no, se agrega el tag
  `cambio_a_pedido_para_canarias`. Después se actualiza el metacampo.

Un pedido creado ya con dirección de Canarias NO lleva el tag: no hubo cambio.
Si el pedido no tiene metacampo (es de antes de que la app existiera), se toma
la dirección actual como punto de partida y no se etiqueta; para los pedidos
abiertos al momento del despliegue está `scripts/preparar_pedidos_abiertos.py`.

El tag nunca se quita solo: si CX vuelve la dirección a península, el pedido
conserva la marca del cambio (pregunta abierta para el Lead Tech, ver log.md).
"""

from .regiones import es_canarias
from .shopify import Shopify, gid_pedido, sin_errores

TAG = "cambio_a_pedido_para_canarias"
NAMESPACE = "natulim"
CLAVE = "envio_canarias"

_LEER = """
query Pedido($id: ID!) {
  order(id: $id) {
    id
    name
    tags
    shippingAddress { countryCodeV2 provinceCode zip }
    metafield(namespace: "%s", key: "%s") { value }
  }
}
""" % (NAMESPACE, CLAVE)

_ANOTAR = """
mutation Anotar($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) { userErrors { field message } }
}
"""

_ETIQUETAR = """
mutation Etiquetar($id: ID!, $tags: [String!]!) {
  tagsAdd(id: $id, tags: $tags) { userErrors { field message } }
}
"""


def _anotar(shopify: Shopify, gid: str, canarias: bool) -> None:
    datos = shopify.graphql(_ANOTAR, {"metafields": [{
        "ownerId": gid, "namespace": NAMESPACE, "key": CLAVE, "type": "boolean",
        "value": "true" if canarias else "false",
    }]})
    sin_errores(datos["metafieldsSet"], "metafieldsSet")


def procesar(shopify: Shopify, pedido_id: int | str) -> str:
    """Se llama con cada orders/create y orders/updated. Lee el pedido fresco
    de Shopify (el payload puede ser una versión vieja si llegó tarde) y
    devuelve qué hizo: 'marcado', 'ya_marcado', 'sin_cambio', 'punto_de_partida'
    o 'no_existe'."""
    gid = gid_pedido(pedido_id)
    pedido = shopify.graphql(_LEER, {"id": gid})["order"]
    if not pedido:
        return "no_existe"

    ahora = es_canarias(pedido.get("shippingAddress"))
    anotado = (pedido.get("metafield") or {}).get("value")

    if anotado is None:
        _anotar(shopify, gid, ahora)
        return "punto_de_partida"

    antes = anotado == "true"
    resultado = "sin_cambio"
    if ahora and not antes:
        if TAG in pedido.get("tags", []):
            resultado = "ya_marcado"
        else:
            sin_errores(shopify.graphql(_ETIQUETAR, {"id": gid, "tags": [TAG]})["tagsAdd"], "tagsAdd")
            resultado = "marcado"
    if ahora != antes:
        _anotar(shopify, gid, ahora)
    return resultado
