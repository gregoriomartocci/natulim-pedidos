# Evidencia de la prueba en vivo (17/11/2026)

Tienda de desarrollo `natulim-sevica`. Servicio local (`uv run python -m app.main`) expuesto con un túnel de cloudflared, y webhooks `ORDERS_CREATE`, `ORDERS_UPDATED` y `ORDERS_DELETE` registrados con `scripts/registrar_webhooks.py`. La prueba es `scripts/probar_en_tienda.py`: crea sus propios pedidos con el tag `prueba-e2e` y no toca ningún pedido existente.

## Salida de la prueba

```
1. Pedido nuevo con envío a Madrid
    ('#6522', 'M', '28001', None) [('300259', 1, 1)]
2. CX cambia la cantidad de la línea (1 → 2)
    [('300259', 2, 2)]
3. CX cambia la dirección a Las Palmas (35001)
    tags: ['cambio_a_pedido_para_canarias', 'prueba-e2e'] | metacampo: {'value': 'true'}
    SQLite: ('#6522', 'GC', '35001', None)
4. Vuelve a península: el tag se queda (hubo un cambio)
    tags: ['cambio_a_pedido_para_canarias', 'prueba-e2e'] | metacampo: {'value': 'false'}
5. Pedido que NACE en Canarias (Tenerife): no lleva tag
    tags: ['prueba-e2e'] | metacampo: {'value': 'true'}
6. Se borra un pedido: queda marcado en SQLite, no se borra la fila
    ('#6523', 'TF', '38001', '2026-11-17T17:13:13+00:00')
```

## Log del servicio

Cada webhook se procesó y respondió 200. `marcado` aparece una sola vez: el `tagsAdd` disparó otro `orders/updated` que terminó en `sin_cambio`, sin bucle.

```
2026-11-17 12:12:48 orders/create #6522 {'sync': 'nuevo', 'marcar': 'punto_de_partida'}
2026-11-17 12:12:48 orders/updated #6522 {'sync': 'actualizado', 'marcar': 'sin_cambio'}
2026-11-17 12:12:50 orders/updated #6522 {'sync': 'actualizado', 'marcar': 'sin_cambio'}
2026-11-17 12:12:53 orders/updated #6522 {'sync': 'actualizado', 'marcar': 'marcado'}
2026-11-17 12:12:55 orders/updated #6522 {'sync': 'actualizado', 'marcar': 'sin_cambio'}
2026-11-17 12:12:56 orders/updated #6522 {'sync': 'actualizado', 'marcar': 'sin_cambio'}
2026-11-17 12:13:05 orders/create #6523 {'sync': 'nuevo', 'marcar': 'punto_de_partida'}
2026-11-17 12:13:06 orders/updated #6523 {'sync': 'actualizado', 'marcar': 'sin_cambio'}
2026-11-17 12:13:07 orders/updated #6523 {'sync': 'actualizado', 'marcar': 'sin_cambio'}
2026-11-17 12:13:13 orders/updated #6523 {'sync': 'actualizado', 'marcar': 'no_existe'}
2026-11-17 12:13:13 orders/delete 8080423485768 {'sync': 'eliminado'}
```

## Base SQLite al terminar

```
nombre  envio_provincia  envio_cp  eliminado
------  ---------------  --------  ---------
#6522   M                28001     0        
#6523   TF               38001     1        

nombre  sku     cantidad  cantidad_actual
------  ------  --------  ---------------
#6522   300259  2         2              
#6523   300259  1         1              
```
