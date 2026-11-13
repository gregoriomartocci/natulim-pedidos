from app.seguridad import firma, verificar_hmac


def test_firma_valida():
    cuerpo = b'{"id": 1}'
    assert verificar_hmac(cuerpo, firma(cuerpo, "s"), "s")


def test_firma_invalida_o_ausente():
    cuerpo = b'{"id": 1}'
    assert not verificar_hmac(cuerpo, firma(cuerpo, "otro"), "s")
    assert not verificar_hmac(cuerpo, None, "s")
    assert not verificar_hmac(cuerpo, firma(cuerpo, "s"), "")


def test_cuerpo_alterado():
    assert not verificar_hmac(b'{"id": 2}', firma(b'{"id": 1}', "s"), "s")
