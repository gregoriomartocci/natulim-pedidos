import json

from app.main import crear_app
from app.seguridad import firma
from tests.conftest import SECRETO, TIENDA


def enviar(cliente, tema, cuerpo, webhook_id="w1", secreto=SECRETO, tienda=TIENDA):
    crudo = json.dumps(cuerpo).encode()
    return cliente.post("/webhooks", data=crudo, headers={
        "X-Shopify-Topic": tema, "X-Shopify-Webhook-Id": webhook_id, "X-Shopify-Shop-Domain": tienda,
        "X-Shopify-Hmac-Sha256": firma(crudo, secreto), "Content-Type": "application/json",
    })


def test_rechaza_firma_invalida(cfg, pedido, shopify_falso):
    c = crear_app(cfg, shopify_falso()).test_client()
    assert enviar(c, "orders/create", pedido, secreto="otro").status_code == 401


def test_rechaza_otra_tienda(cfg, pedido, shopify_falso):
    c = crear_app(cfg, shopify_falso()).test_client()
    assert enviar(c, "orders/create", pedido, tienda="otra.myshopify.com").status_code == 403


def test_create_guarda_y_anota(cfg, pedido, shopify_falso):
    s = shopify_falso(direccion={"countryCodeV2": "ES", "provinceCode": "M", "zip": "28001"})
    r = enviar(crear_app(cfg, s).test_client(), "orders/create", pedido)
    assert r.status_code == 200
    assert r.get_json()["resultado"] == {"sync": "nuevo", "marcar": "punto_de_partida"}


def test_reintento_del_mismo_webhook_no_duplica(cfg, pedido, shopify_falso):
    c = crear_app(cfg, shopify_falso(direccion=None)).test_client()
    enviar(c, "orders/create", pedido, webhook_id="igual")
    assert enviar(c, "orders/create", pedido, webhook_id="igual").get_json()["resultado"] == "repetido"


def test_error_devuelve_500_para_que_shopify_reintente(cfg, pedido, shopify_falso):
    class Rompe(shopify_falso):
        def graphql(self, *a, **k):
            raise RuntimeError("Shopify caído")
    c = crear_app(cfg, Rompe()).test_client()
    assert enviar(c, "orders/updated", pedido).status_code == 500
    # el reintento con el mismo id se procesa (no quedó marcado como hecho)
    c2 = crear_app(cfg, shopify_falso(direccion=None)).test_client()
    assert enviar(c2, "orders/updated", pedido).status_code == 200


def test_delete_marca_eliminado(cfg, pedido, shopify_falso):
    c = crear_app(cfg, shopify_falso(direccion=None)).test_client()
    enviar(c, "orders/create", pedido, webhook_id="a")
    r = enviar(c, "orders/delete", {"id": pedido["id"]}, webhook_id="b")
    assert r.get_json()["resultado"] == {"sync": "eliminado"}


def test_cada_requerimiento_se_apaga_por_separado(cfg, pedido, shopify_falso):
    from dataclasses import replace
    solo_sync = crear_app(replace(cfg, marcar_activo=False), None).test_client()
    assert enviar(solo_sync, "orders/create", pedido).get_json()["resultado"] == {"sync": "nuevo"}
