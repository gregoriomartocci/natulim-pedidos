"""Requerimiento 3: copia de los pedidos de Shopify en SQLite.

Decisiones (detalle en log.md):
- Clave = id de Shopify. Guardar es un upsert, así que recibir dos veces el
  mismo webhook no duplica nada.
- Gana la versión más nueva según `updated_at` de Shopify: los webhooks pueden
  llegar desordenados, y un `orders/updated` viejo no puede pisar uno nuevo.
- Las líneas se reemplazan enteras en cada versión (edición de pedido puede
  agregar, quitar o cambiar cantidades); `cantidad_actual` es la que queda
  después de ediciones y devoluciones.
- Solo pedidos creados desde que la app entró en producción (acordado con el
  área): la fecha de inicio se fija la primera vez que se crea la base.
- Datos mínimos y sin datos personales (RGPD): ni nombre, ni email, ni calle.
  País, provincia y CP alcanzan para logística y Growth.
"""

import json
import sqlite3
from datetime import datetime, timezone

ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (
  clave TEXT PRIMARY KEY,
  valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pedidos (
  id              INTEGER PRIMARY KEY,   -- id de Shopify
  nombre          TEXT NOT NULL,         -- "#6491"
  creado_en       TEXT NOT NULL,
  actualizado_en  TEXT NOT NULL,         -- updated_at de Shopify: decide qué versión gana
  cancelado_en    TEXT,
  estado_pago     TEXT,
  estado_envio    TEXT,
  moneda          TEXT,
  total           TEXT,                  -- texto: el importe exacto que manda Shopify, sin floats
  envio_pais      TEXT,
  envio_provincia TEXT,
  envio_cp        TEXT,
  etiquetas       TEXT,
  eliminado_en    TEXT,                  -- borrado en Shopify: se marca, no se borra acá
  sincronizado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lineas (
  id              INTEGER PRIMARY KEY,   -- id de la línea en Shopify
  pedido_id       INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
  sku             TEXT,
  titulo          TEXT NOT NULL,
  producto_id     INTEGER,
  variante_id     INTEGER,
  cantidad        INTEGER NOT NULL,      -- la pedida originalmente
  cantidad_actual INTEGER,               -- después de ediciones y devoluciones
  precio          TEXT,
  propiedades     TEXT                   -- JSON: los bundles suelen viajar en las propiedades de línea
);
CREATE INDEX IF NOT EXISTS lineas_pedido ON lineas(pedido_id);

CREATE TABLE IF NOT EXISTS webhooks_procesados (
  webhook_id   TEXT PRIMARY KEY,         -- X-Shopify-Webhook-Id
  tema         TEXT NOT NULL,
  procesado_en TEXT NOT NULL
);
"""


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fecha(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def conectar(ruta: str) -> sqlite3.Connection:
    # Una conexión compartida por los hilos del servidor; main.py serializa el
    # acceso con un lock (SQLite admite un solo escritor a la vez de todos modos).
    conn = sqlite3.connect(ruta, isolation_level=None, check_same_thread=False)  # transacciones explícitas
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # lecturas mientras entra un webhook
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.executescript(ESQUEMA)
    conn.execute("INSERT OR IGNORE INTO meta (clave, valor) VALUES ('sincroniza_desde', ?)", (ahora(),))
    return conn


def sincroniza_desde(conn: sqlite3.Connection) -> str:
    return conn.execute("SELECT valor FROM meta WHERE clave = 'sincroniza_desde'").fetchone()["valor"]


def ya_procesado(conn: sqlite3.Connection, webhook_id: str | None) -> bool:
    if not webhook_id:
        return False
    return conn.execute("SELECT 1 FROM webhooks_procesados WHERE webhook_id = ?", (webhook_id,)).fetchone() is not None


def marcar_procesado(conn: sqlite3.Connection, webhook_id: str | None, tema: str) -> None:
    if webhook_id:
        conn.execute(
            "INSERT OR IGNORE INTO webhooks_procesados (webhook_id, tema, procesado_en) VALUES (?, ?, ?)",
            (webhook_id, tema, ahora()),
        )


def guardar_pedido(conn: sqlite3.Connection, pedido: dict) -> str:
    """Guarda o actualiza un pedido con sus líneas. Devuelve qué pasó:
    'nuevo', 'actualizado', 'version_vieja' o 'anterior_al_inicio'."""
    if _fecha(pedido["created_at"]) < _fecha(sincroniza_desde(conn)):
        return "anterior_al_inicio"

    actual = conn.execute("SELECT actualizado_en FROM pedidos WHERE id = ?", (pedido["id"],)).fetchone()
    if actual and _fecha(actual["actualizado_en"]) > _fecha(pedido["updated_at"]):
        return "version_vieja"

    envio = pedido.get("shipping_address") or {}
    fila = {
        "id": pedido["id"],
        "nombre": pedido.get("name") or f"#{pedido.get('order_number', pedido['id'])}",
        "creado_en": pedido["created_at"],
        "actualizado_en": pedido["updated_at"],
        "cancelado_en": pedido.get("cancelled_at"),
        "estado_pago": pedido.get("financial_status"),
        "estado_envio": pedido.get("fulfillment_status"),
        "moneda": pedido.get("currency"),
        "total": pedido.get("current_total_price") or pedido.get("total_price"),
        "envio_pais": envio.get("country_code"),
        "envio_provincia": envio.get("province_code"),
        "envio_cp": envio.get("zip"),
        "etiquetas": pedido.get("tags") or "",
        "sincronizado_en": ahora(),
    }

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            """
            INSERT INTO pedidos (id, nombre, creado_en, actualizado_en, cancelado_en, estado_pago, estado_envio,
                                 moneda, total, envio_pais, envio_provincia, envio_cp, etiquetas, sincronizado_en)
            VALUES (:id, :nombre, :creado_en, :actualizado_en, :cancelado_en, :estado_pago, :estado_envio,
                    :moneda, :total, :envio_pais, :envio_provincia, :envio_cp, :etiquetas, :sincronizado_en)
            ON CONFLICT(id) DO UPDATE SET
              nombre = excluded.nombre, actualizado_en = excluded.actualizado_en,
              cancelado_en = excluded.cancelado_en, estado_pago = excluded.estado_pago,
              estado_envio = excluded.estado_envio, moneda = excluded.moneda, total = excluded.total,
              envio_pais = excluded.envio_pais, envio_provincia = excluded.envio_provincia,
              envio_cp = excluded.envio_cp, etiquetas = excluded.etiquetas,
              sincronizado_en = excluded.sincronizado_en
            """,
            fila,
        )
        conn.execute("DELETE FROM lineas WHERE pedido_id = ?", (pedido["id"],))
        conn.executemany(
            """
            INSERT INTO lineas (id, pedido_id, sku, titulo, producto_id, variante_id, cantidad, cantidad_actual, precio, propiedades)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    linea["id"],
                    pedido["id"],
                    linea.get("sku"),
                    linea.get("title") or linea.get("name") or "",
                    linea.get("product_id"),
                    linea.get("variant_id"),
                    linea["quantity"],
                    linea.get("current_quantity"),
                    linea.get("price"),
                    json.dumps(linea.get("properties") or [], ensure_ascii=False),
                )
                for linea in pedido.get("line_items", [])
            ],
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return "actualizado" if actual else "nuevo"


def marcar_eliminado(conn: sqlite3.Connection, pedido_id: int) -> bool:
    cur = conn.execute(
        "UPDATE pedidos SET eliminado_en = ?, sincronizado_en = ? WHERE id = ? AND eliminado_en IS NULL",
        (ahora(), ahora(), pedido_id),
    )
    return cur.rowcount > 0
