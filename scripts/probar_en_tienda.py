"""Prueba de punta a punta contra la tienda de desarrollo (req. 3 y 4).

Necesita el servicio corriendo y los webhooks registrados apuntando a él
(ver README, "3. Correr"). Crea pedidos de prueba propios, nunca toca pedidos
existentes, y deja todo con el tag `prueba-e2e` para encontrarlos y borrarlos.

    uv run python -m scripts.probar_en_tienda            # corre la prueba
    uv run python -m scripts.probar_en_tienda --limpiar  # borra los pedidos de prueba

Simula lo que haría alguien de CX desde el admin con las mismas mutaciones
que usa el admin (orderUpdate para la dirección, orderEdit para las líneas):
los webhooks que recibe el servicio son los mismos.
"""

import sqlite3
import sys
import time

from app.config import cargar
from app.shopify import Shopify

TAG_PRUEBA = "prueba-e2e"
TAG_CANARIAS = "cambio_a_pedido_para_canarias"
ESPERA = 20  # segundos máximos esperando que el webhook llegue y se procese

MADRID = {"firstName": "Prueba", "lastName": "E2E", "address1": "Calle de Prueba 1", "city": "Madrid",
          "zip": "28001", "provinceCode": "M", "countryCode": "ES"}
LAS_PALMAS = {**MADRID, "city": "Las Palmas de Gran Canaria", "zip": "35001", "provinceCode": "GC"}
TENERIFE = {**MADRID, "city": "Santa Cruz de Tenerife", "zip": "38001", "provinceCode": "TF"}

_VARIANTE = "query($q:String!){ productVariants(first:1, query:$q){ nodes{ id sku } } }"
_CREAR = """mutation($o: OrderCreateOrderInput!){ orderCreate(order:$o){ order{ id name legacyResourceId } userErrors{ field message } } }"""
_DIRECCION = """mutation($i: OrderInput!){ orderUpdate(input:$i){ order{ id } userErrors{ field message } } }"""
_TAGS = "query($id:ID!){ order(id:$id){ tags metafield(namespace:\"natulim\", key:\"envio_canarias\"){ value } } }"
_EDIT_BEGIN = """mutation($id:ID!){ orderEditBegin(id:$id){ calculatedOrder{ id lineItems(first:10){ nodes{ id sku quantity } } } userErrors{ field message } } }"""
_EDIT_QTY = """mutation($id:ID!,$li:ID!,$q:Int!){ orderEditSetQuantity(id:$id, lineItemId:$li, quantity:$q){ userErrors{ field message } } }"""
_EDIT_COMMIT = """mutation($id:ID!){ orderEditCommit(id:$id, notifyCustomer:false){ order{ id } userErrors{ field message } } }"""
_BORRAR = """mutation($id:ID!){ orderDelete(orderId:$id){ deletedId userErrors{ field message } } }"""
_DE_PRUEBA = "query{ orders(first:50, query:\"tag:prueba-e2e\"){ nodes{ id name } } }"


def ok(r: dict, campo: str) -> dict:
    errores = r[campo].get("userErrors") or []
    if errores:
        raise SystemExit(f"{campo}: {errores}")
    return r[campo]


def esperar(condicion, que: str):
    for _ in range(ESPERA):
        valor = condicion()
        if valor:
            return valor
        time.sleep(1)
    raise SystemExit(f"FALLÓ: no pasó '{que}' en {ESPERA}s")


def main(argv: list[str]) -> int:
    cfg = cargar()
    s = Shopify(cargar())

    if argv[:1] == ["--limpiar"]:
        for o in s.graphql(_DE_PRUEBA)["orders"]["nodes"]:
            ok(s.graphql(_BORRAR, {"id": o["id"]}), "orderDelete")
            print("borrado", o["name"])
        return 0

    db = sqlite3.connect(cfg.db_path)
    fila = lambda id_: db.execute("select nombre, envio_provincia, envio_cp, eliminado_en from pedidos where id = ?", (id_,)).fetchone()
    lineas = lambda id_: db.execute("select sku, cantidad, cantidad_actual from lineas where pedido_id = ? order by sku", (id_,)).fetchall()
    tags = lambda gid: s.graphql(_TAGS, {"id": gid})["order"]

    variante = s.graphql(_VARIANTE, {"q": "sku:300259"})["productVariants"]["nodes"][0]

    def crear(direccion: dict) -> dict:
        o = ok(s.graphql(_CREAR, {"o": {
            "lineItems": [{"variantId": variante["id"], "quantity": 1}],
            "shippingAddress": direccion, "tags": [TAG_PRUEBA], "financialStatus": "PAID",
        }}), "orderCreate")["order"]
        return o

    print("1. Pedido nuevo con envío a Madrid")
    a = crear(MADRID)
    id_a = int(a["legacyResourceId"])
    print("   ", esperar(lambda: fila(id_a), "el pedido aparece en SQLite"), lineas(id_a))

    print("2. CX cambia la cantidad de la línea (1 → 2)")
    edit = ok(s.graphql(_EDIT_BEGIN, {"id": a["id"]}), "orderEditBegin")["calculatedOrder"]
    ok(s.graphql(_EDIT_QTY, {"id": edit["id"], "li": edit["lineItems"]["nodes"][0]["id"], "q": 2}), "orderEditSetQuantity")
    ok(s.graphql(_EDIT_COMMIT, {"id": edit["id"]}), "orderEditCommit")
    print("   ", esperar(lambda: [l for l in lineas(id_a) if l[2] == 2], "la cantidad cambia en SQLite"))

    print("3. CX cambia la dirección a Las Palmas (35001)")
    ok(s.graphql(_DIRECCION, {"i": {"id": a["id"], "shippingAddress": LAS_PALMAS}}), "orderUpdate")
    t = esperar(lambda: (lambda x: x if TAG_CANARIAS in x["tags"] else None)(tags(a["id"])), "aparece el tag")
    print("    tags:", t["tags"], "| metacampo:", t["metafield"])
    print("    SQLite:", esperar(lambda: (lambda f: f if f and f[2] == "35001" else None)(fila(id_a)), "la dirección cambia en SQLite"))

    print("4. Vuelve a península: el tag se queda (hubo un cambio)")
    ok(s.graphql(_DIRECCION, {"i": {"id": a["id"], "shippingAddress": MADRID}}), "orderUpdate")
    time.sleep(8)
    t = tags(a["id"])
    print("    tags:", t["tags"], "| metacampo:", t["metafield"])
    assert t["tags"].count(TAG_CANARIAS) == 1

    print("5. Pedido que NACE en Canarias (Tenerife): no lleva tag")
    b = crear(TENERIFE)
    id_b = int(b["legacyResourceId"])
    esperar(lambda: fila(id_b), "el pedido aparece en SQLite")
    time.sleep(5)
    t = tags(b["id"])
    print("    tags:", t["tags"], "| metacampo:", t["metafield"])
    assert TAG_CANARIAS not in t["tags"]

    print("6. Se borra un pedido: queda marcado en SQLite, no se borra la fila")
    ok(s.graphql(_BORRAR, {"id": b["id"]}), "orderDelete")
    print("   ", esperar(lambda: (lambda f: f if f and f[3] else None)(fila(id_b)), "queda marcado como eliminado"))

    print(f"\nOK. Pedido de prueba que queda en la tienda: {a['name']} (tag {TAG_PRUEBA}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
