# Natulim · Sincronización y marcado de pedidos

Un servicio en Python que recibe los webhooks de pedidos de Shopify y resuelve dos requerimientos:

| | Qué hace | Dónde |
|---|---|---|
| **Req. 3 · Sincronización** | Mantiene una copia de cada pedido nuevo (con sus líneas) en SQLite, y la actualiza cuando el pedido cambia en Shopify. | `app/db.py` |
| **Req. 4 · Marcado** | Cuando la dirección de envío de un pedido cambia a Canarias, le agrega el tag `cambio_a_pedido_para_canarias`. | `app/marcar.py` |

Cada uno se puede prender o apagar por separado (`SYNC_ACTIVO`, `MARCAR_ACTIVO`) para ponerlos en producción de a uno.

```
Shopify ──webhook firmado──▶ POST /webhooks ──▶ verifica HMAC y tienda
                                    │
              orders/create ────────┼──▶ Req. 3: upsert pedido + líneas en SQLite
              orders/updated ───────┤    Req. 4: lee el pedido por GraphQL, compara con el
              orders/delete ────────┘            metacampo natulim.envio_canarias y etiqueta
```

## Requisitos

- Python 3.11 o superior y [uv](https://docs.astral.sh/uv/) (o `pip`).
- Acceso a la tienda de desarrollo con permiso para crear apps.
- Una URL pública HTTPS hacia el servicio: en local, un túnel ([cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/) o ngrok).

## 1. Instalar

```bash
git clone <este repo> && cd natulim-pedidos
uv sync                      # crea .venv con las dependencias y pytest
cp .env.example .env         # y completar los valores (ver paso 2)
uv run pytest                # 38 tests, sin red ni Shopify
```

Sin uv: `python -m venv .venv && source .venv/bin/activate && pip install flask requests python-dotenv pytest`.

## 2. Crear la app en Shopify

Desde el 1/1/2026 Shopify no permite crear custom apps nuevas desde el admin: las apps nuevas se crean en el **Dev Dashboard**.

1. En el [Dev Dashboard](https://dev.shopify.com/dashboard) de la organización de la tienda: **Create app**.
2. Scopes de la Admin API: `read_orders`, `write_orders`. Para el script del req. 1 sumar `read_all_orders` (pedidos de más de 60 días) y `read_customers`.
3. Si la API pide acceso a *protected customer data* para los webhooks de pedidos, habilitarlo en la configuración de la app (solo se guardan país, provincia y CP; ver "Datos" más abajo).
4. Instalar la app en la tienda de desarrollo.
5. Copiar **Client ID** y **Client secret** a `.env` (`SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`) y el dominio `*.myshopify.com` a `SHOPIFY_SHOP`.

El servicio obtiene el token solo (client credentials grant, válido 24 h, se renueva automáticamente). Esto funciona cuando la app y la tienda son de la misma organización. Si la tienda ya tiene una custom app "legacy" con token `shpat_…`, alcanza con ponerlo en `SHOPIFY_ADMIN_TOKEN`. En los dos casos el **client secret** hace falta igual, porque con él se verifica la firma de los webhooks.

## 3. Correr

```bash
uv run python -m app.main                    # escucha en :8000 (PORT para cambiarlo)
cloudflared tunnel --url http://localhost:8000   # en otra terminal: da una URL https://….trycloudflare.com
```

Registrar los webhooks apuntando a esa URL (es idempotente):

```bash
uv run python -m scripts.registrar_webhooks https://….trycloudflare.com/webhooks
uv run python -m scripts.registrar_webhooks --listar
```

Para el req. 4, una sola vez después de registrar: anotar la región de los pedidos abiertos que ya existían, así un cambio de dirección sobre ellos también se detecta.

```bash
uv run python -m scripts.preparar_pedidos_abiertos
```

## 4. Probar de punta a punta

1. Crear un pedido de prueba en la tienda (admin → Pedidos → Crear pedido, con dirección en Madrid).
2. Ver el log del servicio: `orders/create #… {'sync': 'nuevo', 'marcar': 'punto_de_partida'}`.
3. `sqlite3 pedidos.sqlite3 "select nombre, envio_cp from pedidos; select pedido_id, sku, cantidad from lineas;"`
4. En el pedido, editar la dirección de envío a una de Las Palmas (CP 35001). El log muestra `'marcar': 'marcado'` y el pedido queda con el tag `cambio_a_pedido_para_canarias`.
5. Editar una línea del pedido: la fila de `lineas` cambia.

## Cómo funciona

**Req. 3 · Sincronización (`app/db.py`)**
- Clave: el id de Shopify. Guardar es un upsert, así que un webhook repetido no duplica nada.
- Los webhooks pueden llegar repetidos o desordenados: se guarda solo si el `updated_at` que llega es más nuevo que el guardado, y cada `X-Shopify-Webhook-Id` procesado queda anotado.
- Las líneas se reemplazan enteras con cada versión del pedido (`cantidad` original y `cantidad_actual` tras ediciones o devoluciones; las propiedades de línea van en JSON, que es donde suelen viajar los datos de bundles).
- Solo pedidos creados desde que el servicio arrancó por primera vez (`meta.sincroniza_desde`), como se acordó con el área.
- Un pedido borrado en Shopify se marca con `eliminado_en`, no se borra.
- Si algo falla, el servicio responde 500 y Shopify reintenta.

**Req. 4 · Marcado (`app/marcar.py`)**
- El webhook trae la dirección de ahora, no la anterior. Sin base de datos, la última región conocida se guarda en el propio pedido, en el metacampo `natulim.envio_canarias`.
- `orders/create` anota si el pedido nace en Canarias. En cada `orders/updated` se lee el pedido fresco por GraphQL: si ahora es Canarias y antes no, `tagsAdd`. Un pedido que nace en Canarias no se etiqueta: no hubo cambio.
- Agregar el tag dispara otro `orders/updated`; como el metacampo ya dice Canarias, no hace nada (sin bucles).
- Canarias = provincia `GC` o `TF`, o CP que empieza con 35 o 38 (`app/regiones.py`).

## Datos

Por RGPD se guarda lo mínimo: ni nombre, ni email, ni calle. País, provincia y CP alcanzan para logística y Growth. Las credenciales van en `.env`, que está en `.gitignore`.

## Estructura

```
app/
  main.py        servidor Flask: POST /webhooks, GET /health
  config.py      variables de entorno
  seguridad.py   verificación HMAC de los webhooks
  shopify.py     cliente GraphQL (token, reintentos, límites)
  db.py          req. 3: esquema SQLite y upsert
  marcar.py      req. 4: detección del cambio a Canarias y tag
  regiones.py    región de España según provincia y CP
scripts/
  registrar_webhooks.py         suscribir / listar / borrar webhooks
  preparar_pedidos_abiertos.py  req. 4: punto de partida de pedidos previos al despliegue
  suscriptores.py               req. 1: suscriptores nuevos península vs. Canarias
tests/           pytest con payloads de ejemplo y un Shopify falso
docs/respuestas.md   documento final para Growth y el Lead Tech
log.md           decisiones tomadas durante el trabajo
AGENTS.md        guía para quien (persona o IA) siga trabajando en el repo
```

## Problemas comunes

- **401 en `/webhooks`**: el `SHOPIFY_CLIENT_SECRET` no es el de la app que registró los webhooks.
- **No llega ningún webhook**: `registrar_webhooks --listar` debe mostrar la URL actual del túnel (cambia cada vez que se reinicia cloudflared).
- **`webhookSubscriptionCreate` pide protected customer data**: habilitarlo en la app (paso 2.3).
- **Error al obtener el token**: el client credentials grant requiere que la app sea de la misma organización que la tienda; si no, usar un token de custom app en `SHOPIFY_ADMIN_TOKEN`.
