import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.config import Config

PEDIDO = json.loads((Path(__file__).parent / "fixtures" / "pedido.json").read_text())
SECRETO = "secreto-de-prueba"
TIENDA = "natulim-dev.myshopify.com"


@pytest.fixture
def pedido():
    return deepcopy(PEDIDO)


@pytest.fixture
def cfg(tmp_path):
    return Config(
        shop=TIENDA, api_version="2026-10", client_id="id", client_secret=SECRETO, admin_token="shpat_x",
        db_path=str(tmp_path / "pedidos.sqlite3"), sync_activo=True, marcar_activo=True,
    )


class ShopifyFalso:
    """Imita la Admin API: un pedido en memoria con tags y metacampo."""

    def __init__(self, direccion=None, tags=None, anotado=None, existe=True):
        self.direccion = direccion
        self.tags = list(tags or [])
        self.anotado = anotado
        self.existe = existe
        self.llamadas = []

    def graphql(self, consulta, variables=None):
        variables = variables or {}
        self.llamadas.append(consulta.split("(")[0].split()[-1])
        if "order(id:" in consulta:
            if not self.existe:
                return {"order": None}
            return {"order": {
                "id": variables["id"], "name": "#6491", "tags": self.tags, "shippingAddress": self.direccion,
                "metafield": None if self.anotado is None else {"value": self.anotado},
            }}
        if "metafieldsSet" in consulta:
            self.anotado = variables["metafields"][0]["value"]
            return {"metafieldsSet": {"userErrors": []}}
        if "tagsAdd" in consulta:
            self.tags += variables["tags"]
            return {"tagsAdd": {"userErrors": []}}
        raise AssertionError(f"consulta inesperada: {consulta[:60]}")


@pytest.fixture
def shopify_falso():
    return ShopifyFalso
