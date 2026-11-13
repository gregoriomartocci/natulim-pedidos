# Para quien siga trabajando acá (personas o agentes de IA)

Servicio Python que recibe webhooks de pedidos de Shopify. Leé `README.md` para el qué y `log.md` para el porqué de cada decisión.

## Comandos

- Tests: `uv run pytest` — tienen que pasar antes de cada commit. No usan red.
- Servidor local: `uv run python -m app.main`
- Webhooks: `uv run python -m scripts.registrar_webhooks <url>/webhooks`

## Reglas

- Nunca commitear `.env` ni credenciales. Los valores nuevos van en `.env.example`, vacíos.
- Toda decisión de diseño se anota en `log.md` (fecha, qué y por qué).
- Cada requerimiento queda aislado en su módulo (`db.py` req. 3, `marcar.py` req. 4) y se apaga con su variable (`SYNC_ACTIVO`, `MARCAR_ACTIVO`).
- La firma HMAC se verifica sobre el cuerpo crudo. No parsear y re-serializar antes.
- Lo que escribe en Shopify tiene que ser idempotente: los webhooks se repiten y llegan desordenados, y cada escritura propia dispara otro `orders/updated`.
- Nada de datos personales en la base (RGPD): solo país, provincia y CP.
- Llamadas a Shopify solo por `app/shopify.py` (maneja token, 429 y THROTTLED). En tests se reemplaza por `ShopifyFalso` (`tests/conftest.py`).
