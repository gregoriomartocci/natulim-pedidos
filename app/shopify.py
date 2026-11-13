"""Cliente mínimo de la Admin GraphQL API de Shopify.

Autenticación, dos caminos:
- `SHOPIFY_ADMIN_TOKEN`: token fijo de una custom app "legacy" creada desde el
  admin. Desde el 1/1/2026 Shopify ya no deja crear apps nuevas así, pero las
  que existían siguen andando.
- Si no hay token: client credentials grant con el client id y secret de una
  app del Dev Dashboard. El token dura 24 h; se pide de nuevo un minuto antes
  de vencer. Requiere que la app y la tienda sean de la misma organización.
"""

import time

import requests

from .config import Config


class ErrorShopify(RuntimeError):
    pass


class Shopify:
    def __init__(self, cfg: Config, sesion: requests.Session | None = None):
        if not cfg.shop:
            raise ErrorShopify("Falta SHOPIFY_SHOP en el entorno.")
        self.cfg = cfg
        self.http = sesion or requests.Session()
        self._token = cfg.admin_token or None
        self._vence = float("inf") if cfg.admin_token else 0.0

    def _token_vigente(self) -> str:
        if self._token and time.time() < self._vence:
            return self._token
        if not (self.cfg.client_id and self.cfg.client_secret):
            raise ErrorShopify("Sin SHOPIFY_ADMIN_TOKEN ni SHOPIFY_CLIENT_ID/SECRET: no hay cómo autenticarse.")
        r = self.http.post(
            f"https://{self.cfg.shop}/admin/oauth/access_token",
            json={
                "grant_type": "client_credentials",
                "client_id": self.cfg.client_id,
                "client_secret": self.cfg.client_secret,
            },
            timeout=15,
        )
        if r.status_code != 200:
            raise ErrorShopify(f"No se pudo obtener el token ({r.status_code}): {r.text[:300]}")
        datos = r.json()
        self._token = datos["access_token"]
        self._vence = time.time() + int(datos.get("expires_in", 86400)) - 60
        return self._token

    def graphql(self, consulta: str, variables: dict | None = None) -> dict:
        url = f"https://{self.cfg.shop}/admin/api/{self.cfg.api_version}/graphql.json"
        for intento in range(4):
            ultimo = intento == 3
            r = self.http.post(
                url,
                json={"query": consulta, "variables": variables or {}},
                headers={"X-Shopify-Access-Token": self._token_vigente()},
                timeout=20,
            )
            if r.status_code == 429 and not ultimo:  # límite de pedidos: esperar y reintentar
                time.sleep(2 ** intento)
                continue
            if r.status_code == 401 and not self.cfg.admin_token and not ultimo:
                self._vence = 0  # token vencido o revocado: se pide otro
                continue
            if r.status_code != 200:
                raise ErrorShopify(f"GraphQL {r.status_code}: {r.text[:300]}")
            cuerpo = r.json()
            errores = cuerpo.get("errors") or []
            throttled = any(isinstance(e, dict) and (e.get("extensions") or {}).get("code") == "THROTTLED" for e in errores)
            if throttled and not ultimo:  # límite de costo de GraphQL
                time.sleep(2 ** intento)
                continue
            if errores:
                raise ErrorShopify(f"GraphQL: {errores}")
            return cuerpo["data"]
        raise ErrorShopify("GraphQL: se agotaron los reintentos")


def gid_pedido(pedido_id: int | str) -> str:
    return f"gid://shopify/Order/{pedido_id}"


def sin_errores(resultado: dict, operacion: str) -> dict:
    errores = resultado.get("userErrors") or []
    if errores:
        raise ErrorShopify(f"{operacion}: {errores}")
    return resultado
