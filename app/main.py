"""Servidor de webhooks: un solo endpoint para los requerimientos 3 y 4.

Shopify manda POST /webhooks con el tema en `X-Shopify-Topic`:
- orders/create  → guarda el pedido (req. 3) y anota su región de envío (req. 4)
- orders/updated → actualiza el pedido (req. 3) y revisa si pasó a Canarias (req. 4)
- orders/delete  → marca el pedido como eliminado (req. 3)

Responde 200 solo cuando terminó bien. Ante un error responde 500 y Shopify
reintenta: ese reintento es lo que hace que no se pierdan pedidos por una
caída momentánea. Un webhook ya procesado (mismo X-Shopify-Webhook-Id) se
ignora, así que los reintentos no duplican nada.
"""

import json
import logging
import os
import threading
from contextlib import nullcontext

from flask import Flask, jsonify, request

from . import db, marcar
from .config import Config, cargar
from .seguridad import verificar_hmac
from .shopify import Shopify

log = logging.getLogger("natulim")


def crear_app(cfg: Config | None = None, shopify: Shopify | None = None) -> Flask:
    cfg = cfg or cargar()
    app = Flask(__name__)
    conn = db.conectar(cfg.db_path) if cfg.sync_activo else None
    # Un webhook a la vez contra la base: el servidor atiende en varios hilos y
    # así un created y un updated del mismo pedido no se cruzan.
    candado = threading.Lock() if conn is not None else nullcontext()
    cliente = shopify if shopify is not None else (Shopify(cfg) if cfg.marcar_activo else None)

    @app.get("/health")
    def health():
        return jsonify(ok=True, sync=cfg.sync_activo, marcar=cfg.marcar_activo)

    @app.post("/webhooks")
    def webhooks():
        cuerpo = request.get_data()
        if not verificar_hmac(cuerpo, request.headers.get("X-Shopify-Hmac-Sha256"), cfg.client_secret):
            return jsonify(error="firma inválida"), 401
        tienda = request.headers.get("X-Shopify-Shop-Domain", "")
        if cfg.shop and tienda and tienda != cfg.shop:
            return jsonify(error=f"tienda inesperada: {tienda}"), 403

        tema = request.headers.get("X-Shopify-Topic", "")
        webhook_id = request.headers.get("X-Shopify-Webhook-Id")
        pedido = json.loads(cuerpo)
        resultado: dict[str, str] = {}
        with candado:
            return _procesar(tema, webhook_id, pedido, resultado)

    def _procesar(tema: str, webhook_id: str | None, pedido: dict, resultado: dict[str, str]):
        if conn is not None and db.ya_procesado(conn, webhook_id):
            return jsonify(resultado="repetido"), 200
        try:
            if tema in ("orders/create", "orders/updated"):
                if conn is not None:
                    resultado["sync"] = db.guardar_pedido(conn, pedido)
                if cliente is not None:
                    resultado["marcar"] = marcar.procesar(cliente, pedido["id"])
            elif tema == "orders/delete":
                if conn is not None:
                    resultado["sync"] = "eliminado" if db.marcar_eliminado(conn, pedido["id"]) else "no_estaba"
            else:
                resultado["ignorado"] = tema
            if conn is not None:
                db.marcar_procesado(conn, webhook_id, tema)
        except Exception:
            log.exception("Falló %s del pedido %s", tema, pedido.get("id"))
            return jsonify(error="falló el procesamiento; Shopify va a reintentar"), 500

        log.info("%s %s %s", tema, pedido.get("name") or pedido.get("id"), resultado)
        return jsonify(resultado=resultado), 200

    return app


def principal() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    crear_app().run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    principal()
