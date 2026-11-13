"""Configuración leída del entorno (.env en local, variables del host en producción)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool(nombre: str, defecto: bool) -> bool:
    valor = os.getenv(nombre)
    if valor is None or valor == "":
        return defecto
    return valor.strip().lower() in {"1", "true", "si", "sí", "yes"}


@dataclass(frozen=True)
class Config:
    shop: str
    api_version: str
    client_id: str
    client_secret: str
    admin_token: str
    db_path: str
    sync_activo: bool
    marcar_activo: bool


def cargar() -> Config:
    return Config(
        shop=os.getenv("SHOPIFY_SHOP", "").strip(),
        api_version=os.getenv("SHOPIFY_API_VERSION", "2026-10").strip(),
        client_id=os.getenv("SHOPIFY_CLIENT_ID", "").strip(),
        client_secret=os.getenv("SHOPIFY_CLIENT_SECRET", "").strip(),
        admin_token=os.getenv("SHOPIFY_ADMIN_TOKEN", "").strip(),
        db_path=os.getenv("DB_PATH", "pedidos.sqlite3").strip(),
        sync_activo=_bool("SYNC_ACTIVO", True),
        marcar_activo=_bool("MARCAR_ACTIVO", True),
    )
