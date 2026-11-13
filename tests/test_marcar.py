from app import marcar

PENINSULA = {"countryCodeV2": "ES", "provinceCode": "M", "zip": "28001"}
CANARIAS = {"countryCodeV2": "ES", "provinceCode": "GC", "zip": "35001"}


def test_pedido_nuevo_solo_anota_punto_de_partida(shopify_falso):
    s = shopify_falso(direccion=CANARIAS)
    assert marcar.procesar(s, 1) == "punto_de_partida"
    assert s.anotado == "true" and s.tags == []  # nació en Canarias: no es un cambio


def test_cambio_de_peninsula_a_canarias_marca(shopify_falso):
    s = shopify_falso(direccion=CANARIAS, anotado="false")
    assert marcar.procesar(s, 1) == "marcado"
    assert s.tags == [marcar.TAG] and s.anotado == "true"


def test_no_marca_dos_veces(shopify_falso):
    s = shopify_falso(direccion=CANARIAS, anotado="false")
    marcar.procesar(s, 1)
    assert marcar.procesar(s, 1) == "sin_cambio"  # el tagsAdd dispara otro orders/updated
    assert s.tags == [marcar.TAG]


def test_sigue_en_peninsula_no_hace_nada(shopify_falso):
    s = shopify_falso(direccion=PENINSULA, anotado="false")
    assert marcar.procesar(s, 1) == "sin_cambio"
    assert s.llamadas == ["Pedido"]  # una sola lectura, ninguna escritura


def test_vuelve_a_peninsula_conserva_el_tag(shopify_falso):
    s = shopify_falso(direccion=PENINSULA, anotado="true", tags=[marcar.TAG])
    assert marcar.procesar(s, 1) == "sin_cambio"
    assert s.anotado == "false" and s.tags == [marcar.TAG]


def test_ida_y_vuelta_a_canarias_no_duplica(shopify_falso):
    s = shopify_falso(direccion=CANARIAS, anotado="false", tags=[marcar.TAG])
    assert marcar.procesar(s, 1) == "ya_marcado"
    assert s.tags == [marcar.TAG]


def test_pedido_borrado(shopify_falso):
    assert marcar.procesar(shopify_falso(existe=False), 1) == "no_existe"
