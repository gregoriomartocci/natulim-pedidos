from datetime import date

from scripts.suscriptores import contar, mensaje, restar_meses


def p(i, cliente, cp, fecha="2030-01-01"):
    return {"id": f"o{i}", "createdAt": fecha, "customer": {"id": cliente} if cliente else None,
            "shippingAddress": {"countryCodeV2": "ES", "zip": cp}}


def test_cuenta_clientes_una_vez_en_su_primera_region():
    pedidos = [p(1, "c1", "28001", "2030-01-01"), p(2, "c1", "35001", "2030-02-01"),
               p(3, "c2", "38001"), p(4, "c3", "07001"), p(5, None, "35100")]
    assert contar(pedidos) == {"peninsula": 1, "canarias": 2, "baleares": 1}


def test_mensaje():
    texto = mensaje({"peninsula": 30, "canarias": 10}, date(2030, 1, 1), date(2030, 7, 1))
    assert "península 30, Canarias 10 (3.0 a 1)" in texto


def test_restar_meses():
    assert restar_meses(date(2026, 11, 12), 6) == date(2026, 5, 12)
    assert restar_meses(date(2026, 3, 31), 6) == date(2025, 9, 28)
