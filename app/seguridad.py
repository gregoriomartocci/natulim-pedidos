"""Verificación de la firma de los webhooks de Shopify.

Shopify firma cada webhook con HMAC-SHA256 del cuerpo crudo usando el client
secret de la app, y manda la firma en base64 en `X-Shopify-Hmac-Sha256`. Sin
esta verificación cualquiera que conozca la URL podría escribir pedidos falsos
en la base o etiquetar pedidos.
"""

import base64
import hashlib
import hmac


def firma(cuerpo: bytes, secreto: str) -> str:
    digest = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def verificar_hmac(cuerpo: bytes, cabecera: str | None, secreto: str) -> bool:
    if not cabecera or not secreto:
        return False
    # Sobre los bytes crudos, nunca sobre el JSON re-serializado; y en tiempo constante.
    return hmac.compare_digest(firma(cuerpo, secreto), cabecera)
