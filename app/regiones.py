"""En qué región de España cae una dirección de envío.

Se usa en el requerimiento 4 (¿la dirección nueva es de Canarias?) y en el 1
(suscriptores de península contra Canarias).

Se mira primero el código de provincia de Shopify y, si falta, el código
postal: el CP lo escribe el cliente y el código de provincia lo completa el
checkout, así que juntos cubren direcciones cargadas a mano desde el admin.
"""

# Códigos de provincia de Shopify para España (ISO 3166-2:ES sin el prefijo).
_PROVINCIA = {
    "GC": "canarias",  # Las Palmas
    "TF": "canarias",  # Santa Cruz de Tenerife
    "PM": "baleares",
    "CE": "ceuta",
    "ML": "melilla",
}

# Los dos primeros dígitos del CP son la provincia.
_PREFIJO_CP = {
    "35": "canarias",
    "38": "canarias",
    "07": "baleares",
    "51": "ceuta",
    "52": "melilla",
}


def _campo(direccion: dict, *claves: str) -> str:
    for clave in claves:
        valor = direccion.get(clave)
        if valor:
            return str(valor).strip()
    return ""


def region(direccion: dict | None) -> str | None:
    """'peninsula', 'canarias', 'baleares', 'ceuta', 'melilla', 'fuera_de_espana' o None si no hay dirección.

    Acepta tanto el formato REST de los webhooks (country_code, province_code,
    zip) como el de GraphQL (countryCodeV2, provinceCode, zip).
    """
    if not direccion:
        return None
    pais = _campo(direccion, "country_code", "countryCodeV2", "countryCode").upper()
    if pais and pais != "ES":
        return "fuera_de_espana"
    provincia = _campo(direccion, "province_code", "provinceCode").upper()
    if provincia in _PROVINCIA:
        return _PROVINCIA[provincia]
    cp = _campo(direccion, "zip").replace(" ", "")
    if len(cp) >= 2 and cp[:2] in _PREFIJO_CP:
        return _PREFIJO_CP[cp[:2]]
    if not pais and not provincia and not cp:
        return None
    return "peninsula"


def es_canarias(direccion: dict | None) -> bool:
    return region(direccion) == "canarias"
