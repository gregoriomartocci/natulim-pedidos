from app import db


def test_guarda_pedido_con_lineas_y_sin_datos_personales(cfg, pedido):
    conn = db.conectar(cfg.db_path)
    assert db.guardar_pedido(conn, pedido) == "nuevo"
    fila = conn.execute("SELECT * FROM pedidos").fetchone()
    assert fila["nombre"] == "#6491" and fila["envio_cp"] == "28001" and fila["total"] == "34.90"
    assert "email" not in fila.keys()
    lineas = conn.execute("SELECT sku, cantidad FROM lineas ORDER BY id").fetchall()
    assert [tuple(l) for l in lineas] == [("PACK-ESENCIALES", 1), ("DET-FL", 1)]


def test_actualizacion_reemplaza_lineas(cfg, pedido):
    conn = db.conectar(cfg.db_path)
    db.guardar_pedido(conn, pedido)
    pedido["updated_at"] = "2030-01-10T11:00:00+01:00"
    pedido["line_items"] = pedido["line_items"][:1]
    pedido["line_items"][0]["current_quantity"] = 3
    assert db.guardar_pedido(conn, pedido) == "actualizado"
    lineas = conn.execute("SELECT sku, cantidad_actual FROM lineas").fetchall()
    assert [tuple(l) for l in lineas] == [("PACK-ESENCIALES", 3)]


def test_version_vieja_no_pisa_la_nueva(cfg, pedido):
    conn = db.conectar(cfg.db_path)
    nuevo = dict(pedido, updated_at="2030-01-10T12:00:00+01:00", tags="nuevo")
    db.guardar_pedido(conn, nuevo)
    viejo = dict(pedido, updated_at="2030-01-10T11:00:00+01:00", tags="viejo")
    assert db.guardar_pedido(conn, viejo) == "version_vieja"
    assert conn.execute("SELECT etiquetas FROM pedidos").fetchone()["etiquetas"] == "nuevo"


def test_ignora_pedidos_anteriores_al_inicio(cfg, pedido):
    conn = db.conectar(cfg.db_path)
    pedido["created_at"] = "2020-01-01T00:00:00Z"
    assert db.guardar_pedido(conn, pedido) == "anterior_al_inicio"
    assert conn.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0] == 0


def test_eliminar_marca_y_no_borra(cfg, pedido):
    conn = db.conectar(cfg.db_path)
    db.guardar_pedido(conn, pedido)
    assert db.marcar_eliminado(conn, pedido["id"])
    fila = conn.execute("SELECT eliminado_en FROM pedidos").fetchone()
    assert fila["eliminado_en"] is not None
    assert conn.execute("SELECT COUNT(*) FROM lineas").fetchone()[0] == 2


def test_inicio_se_fija_una_sola_vez(cfg):
    primero = db.sincroniza_desde(db.conectar(cfg.db_path))
    assert db.sincroniza_desde(db.conectar(cfg.db_path)) == primero
