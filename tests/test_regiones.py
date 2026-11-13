import pytest

from app.regiones import es_canarias, region


@pytest.mark.parametrize("direccion, esperado", [
    ({"country_code": "ES", "province_code": "GC", "zip": "35001"}, "canarias"),
    ({"country_code": "ES", "province_code": "TF", "zip": "38001"}, "canarias"),
    ({"country_code": "ES", "province_code": "", "zip": "38 400"}, "canarias"),  # CP cargado a mano, sin provincia
    ({"countryCodeV2": "ES", "provinceCode": "TF", "zip": "38001"}, "canarias"),  # formato GraphQL
    ({"country_code": "ES", "province_code": "M", "zip": "28001"}, "peninsula"),
    ({"country_code": "ES", "province_code": "PM", "zip": "07001"}, "baleares"),
    ({"country_code": "ES", "province_code": "CE", "zip": "51001"}, "ceuta"),
    ({"country_code": "ES", "province_code": "ML", "zip": "52001"}, "melilla"),
    ({"country_code": "PT", "province_code": "", "zip": "1000-001"}, "fuera_de_espana"),
    (None, None),
    ({}, None),
])
def test_region(direccion, esperado):
    assert region(direccion) == esperado


def test_es_canarias():
    assert es_canarias({"country_code": "ES", "zip": "35100"})
    assert not es_canarias({"country_code": "ES", "zip": "28001"})
    assert not es_canarias(None)
