# Simulación Natulim · Respuestas

Gregorio Martocci · Repo: https://github.com/gregoriomartocci/natulim-pedidos

Todo lo que sigue sale de la tienda de desarrollo `natulim-sevica`, leída por la Admin API el 17/11/2026. Lo que no se pudo verificar está marcado como tal.

---

## Requerimiento 1 · Mensaje para Growth (Discord)

> ¡Hola! Suscriptores nuevos de los últimos 6 meses (17/05/2026 al 17/11/2026): **península 386, Canarias 11** (35 a 1). Cuento clientes cuya primera suscripción empezó en ese período, según su dirección de envío; península = España sin Baleares (14 aparte), Ceuta ni Melilla. Si os sirve, lo desgloso por mes.

**Cómo lo saqué.** En producción, la fuente correcta es Recharge: su API de suscripciones filtrada por fecha de alta y agrupada por cliente y provincia. Como Recharge no está en la tienda de desarrollo, usé lo que Recharge deja en Shopify: el primer pedido de cada suscripción lleva el tag `Subscription First Order`. Lo calcula `scripts/suscriptores.py`.

- Hay 920 pedidos con ese tag, uno por cliente: ningún cliente aparece dos veces.
- **Ojo con el período:** en esta tienda todos esos pedidos están fechados entre el 14 y el 21/05/2026, probablemente por cómo se replicaron los datos. El corte de 6 meses (17/05) deja afuera 509 primeros pedidos del 14 y 15/05. Contando desde el 14/05 serían **península 854, Canarias 32** (27 a 1). Con datos reales esto no pasaría: lo aclaro porque el resultado depende mucho del día de corte.
- Supuestos a confirmar con el Lead Tech:
  - "suscriptor nuevo" = cliente con su primera suscripción en el período, no cada suscripción nueva;
  - "península" excluye Baleares, Ceuta y Melilla.

---

## Requerimiento 2 · Diagnóstico de bundles (para el Lead Tech)

> **Resumen:** no es un problema del software del 3PL ni de "la app" en general. Falla el desglose de **un pack concreto, el Pack Esenciales del Hogar**, y casi seguro por cómo está armado: **es un pack de packs.**
>
> **Qué revisé.** Los pedidos #6480 (recibido) y #6491 (no recibido), por la Admin API:
>
> | | #6480 (recibido) | #6491 (no recibido) |
> |---|---|---|
> | Packs que contiene | Pack Limpiacristales (SKU 300259) y Pack Desengrasante (300258) | **Pack Esenciales del Hogar (300246)** y Pack Lavavajillas a Mano (300642) |
> | Líneas | 3 | 12 (incluye 5 regalos de aniversario `_gwp`) |
> | Linealización armada en Shopify, antes del desglose (`natulim.line_items`) | `PLD1-PDD1-VD1` | `PackD1-BAR1-PEHD1-RCM1-SU1-RCE1-LMBI1-CM2-FL1-TB1-BB1-VD1` |
> | Origen | Checkout web, pedido recuperado | Checkout web, primer pedido con 7 suscripciones de Recharge |
> | Envío | Madrid, courier PQ | Baleares (07420), courier PQ |
> | En la tienda dev | Pagado, sin preparar | Pagado, sin preparar |
>
> **Lo que está pasando**
> - **El Pack Esenciales del Hogar no es como los demás.** Según su ficha, incluye las cuatro Botellas Infinitas (Antical, Desengrasante, Limpiacristales y Multisuperficies) con sus recargas, es decir, los otros cuatro packs. El Pack Limpiacristales, en cambio, es una botella más sus recargas: un nivel.
> - Si la app desglosa un solo nivel, el Pack Limpiacristales llega al 3PL como piezas que sabe preparar. El Esenciales, en cambio, llega como otros packs (o como el pack entero), que el 3PL no tiene dados de alta. Eso explica las dos cosas que ve Logística: "Esenciales no se desglosa, Limpiacristales sí".
> - **Logística** dice que el 3PL "no arma el kit por un problema en su software". Pero el 3PL no arma kits: el kit no existe en su sistema y solo puede preparar componentes. Lo que ven allí es la consecuencia, no la causa.
> - **CX** tiene razón en que el problema está en la app, pero no en toda: #6480 (packs simples) llegó; #6491 (con el Esenciales) no.
>
> **Lo que descarté:**
> - El envío a Baleares no parece ser la causa: hay más de 200 pedidos a Baleares en la tienda con el mismo courier (PQ) que #6480.
> - Que #6491 sea un pedido de Recharge no lo pude descartar del todo, porque la app no está instalada. Pero la mayoría de los pedidos de la tienda vienen de suscripciones, y los packs simples se desglosan bien.
>
> **Lo que no pude ver:** la app de bundles no está en la tienda dev, y en Shopify ningún pack tiene componentes definidos: en los 79 pedidos con el Esenciales y en los 44 con el Limpiacristales, el pack llega como una sola línea, y la linealización `natulim.line_items` lleva el código del pack en los dos pedidos (también en #6480, que sí llegó). O sea: esa linealización se arma antes del desglose, y el desglose ocurre fuera de Shopify, en la app. Lo que recibe el 3PL es la salida de esa app, que no pude ver. Por eso la causa exacta (desglose de un solo nivel o falta de configuración del Esenciales) hay que confirmarla mirando la configuración de la app.
>
> **Qué hay que hacer**
> 1. **Hoy:** desglosar a mano #6491 y reenviarlo al 3PL. Hay que editar el pedido, quitar el Pack Esenciales y agregar sus componentes finales a precio 0: las 4 botellas y las recargas de cada tipo, según la variante. Avisar a CX para que le escriba al cliente.
> 2. **Hoy:** buscar todos los pedidos abiertos con el Esenciales (`sku:300246 OR sku:300247 OR sku:300248` y `fulfillment_status:unfulfilled`) y hacer lo mismo con cada uno. En esta tienda hay 79 pedidos con la variante de 2. En producción hay que contar los abiertos.
> 3. **Esta semana:** en la app, definir el Esenciales con sus componentes finales, no con otros packs, o hacer que la app desglose de forma recursiva. Además, sumar un test por pack que verifique que ningún SKU de pack queda en lo que se manda al 3PL. Es una app hecha con IA y sin pruebas: el próximo pack de packs va a fallar igual.
> 4. **Alerta:** que ningún pedido salga al 3PL con un SKU de pack. El chequeo va sobre **lo que la app manda al 3PL** (no sobre `natulim.line_items`, que siempre lleva códigos de pack porque se arma antes del desglose): si aparece un SKU de pack, se frena el envío y se avisa a Logística. Para confirmar la causa: un pedido de prueba solo con el Esenciales y mirar qué sale hacia el 3PL.
> 5. **A mediano plazo:** evaluar los bundles nativos de Shopify (productos con componentes). Mandan los componentes al fulfillment sin una app propia en el medio.
>
> Le respondería a Logística y a CX con este mismo resumen, para cerrar las dos hipótesis.

---

## Requerimiento 3 · Sincronización de pedidos

**Probado en vivo en la tienda de desarrollo el 17/11** (detalle en `docs/evidencia.md`). Un pedido nuevo aparece en SQLite con sus líneas en menos de un segundo. Si se edita la cantidad de una línea o la dirección, la base cambia. Si se borra el pedido, la fila queda marcada, no se borra.

**¿Lo ponemos ya en producción?** Todavía no tal como está: hoy corre en una máquina con un túnel. La lógica sí está lista: verifica la firma, ignora duplicados y webhooks que llegan desordenados, y está cubierta por tests. Le faltan tres cosas antes de que alguien pueda confiar en esa base:

1. **Un lugar estable para correr**, con disco persistente para SQLite: un servicio pequeño en Fly.io o Railway con volumen, o una VM. En los planes gratuitos con disco efímero la base se pierde en cada despliegue.
2. **Reconciliación.** Los webhooks son "al menos una vez", no "exactamente una vez": si el servicio está caído más tiempo del que Shopify reintenta, se pierden cambios. Hace falta un job cada hora que pida a la Admin API los pedidos con `updated_at` posterior al último sincronizado y los pase por la misma función de guardado.
3. **Monitoreo y respaldo:** alerta si `/health` falla o si hay respuestas 500, y una copia continua de la base (por ejemplo, con Litestream).
4. **Responder rápido y procesar en cola.** Shopify espera la respuesta del webhook unos 5 segundos. Hoy el servicio procesa dentro de la petición, y el req. 4 consulta y escribe por GraphQL: en la prueba respondió en alrededor de 1 segundo, pero si la API limita (`THROTTLED`), los reintentos pueden pasar ese tiempo y Shopify cuenta el webhook como fallido y lo reintenta. No rompe nada, porque todo es idempotente, pero en producción conviene guardar el webhook, responder 200 al instante y procesarlo en una cola.

**¿Cómo lo ponemos en producción?**
1. Crear la app en el Dev Dashboard de la organización de producción (no reutilizar la de dev) e instalarla en la tienda.
2. Desplegar el servicio con `SYNC_ACTIVO=true` y `MARCAR_ACTIVO=false`, con el `.env` cargado como secretos del host.
3. Registrar los webhooks con `scripts/registrar_webhooks.py` apuntando a la URL de producción. Desde ese momento empieza la sincronización: los pedidos anteriores no se tienen en cuenta, como se acordó.
4. Verificar con un pedido de prueba que aparece en la base, y borrarlo.
5. Activar la reconciliación horaria y las alertas.
6. Si la base la van a consultar otras áreas, pasar de SQLite a Postgres. El esquema es el mismo.

---

## Requerimiento 4 · Marcar pedidos que cambian a Canarias

**Probado en vivo el 17/11:**
- Al cambiar la dirección de un pedido de Madrid a Las Palmas (35001), el pedido quedó con el tag `cambio_a_pedido_para_canarias` en unos 5 segundos. Las escrituras propias no generaron un bucle.
- Al volver a Madrid, el tag se quedó.
- Un pedido que nació en Tenerife no lo recibió.

**¿Lo ponemos ya en producción?** Sí, con poco riesgo. Solo agrega un tag y un metacampo, no modifica nada más del pedido, es idempotente y no entra en bucles. Antes, una prueba con alguien de CX haciendo la edición desde el admin. Mi prueba usó la misma mutación del admin (`orderUpdate`), así que el webhook que llega es el mismo.

**¿Cómo lo ponemos en producción?**
1. Mismo servicio y misma app: desplegar con `MARCAR_ACTIVO=true`. No necesita base de datos.
2. Registrar los webhooks, si no estaban por el req. 3.
3. Correr una vez `scripts/preparar_pedidos_abiertos.py`. Anota la región actual de los pedidos abiertos, para que también se detecte un cambio de dirección en pedidos creados antes del despliegue. En la tienda de desarrollo no lo corrí a propósito: escribiría un metacampo en los ~5.500 pedidos de una tienda que comparten otros candidatos.
4. Avisar a CX y a Logística del tag y para qué sirve; por ejemplo, con un filtro guardado en el admin de pedidos: `tag:cambio_a_pedido_para_canarias`.

**Decisiones a confirmar con el negocio:**
- Un pedido que nace con dirección en Canarias no se etiqueta, porque no hubo cambio.
- Si la dirección vuelve a península, el tag se queda: marca que hubo un cambio.

---

## Alcance

**Incluí**
- Req. 3 y 4 en un solo servicio, con verificación HMAC, idempotencia, orden por `updated_at`, borrados marcados en vez de eliminados, 38 tests y despliegue por requerimiento.
- **Prueba de punta a punta contra la tienda** (`scripts/probar_en_tienda.py`), repetible, que crea sus propios pedidos de prueba y los puede borrar.
- Scripts para registrar webhooks, preparar los pedidos anteriores al despliegue (req. 4) y calcular los suscriptores (req. 1).
- Diagnóstico del req. 2 con los datos de los pedidos y de los productos de la tienda.
- `README.md` para instalar desde cero, `log.md` con las decisiones y `AGENTS.md` para que otra persona o una IA pueda seguir.

**Dejé fuera, y por qué**
- **Reconciliación del req. 3:** no hace falta para demostrar el flujo, pero es lo primero que agregaría antes de producción (ver arriba).
- **Despliegue permanente:** corre en local con un túnel. Desplegarlo en un plan gratuito con disco efímero daría la falsa sensación de que está "en producción".
- **Inspección de la app de bundles y de Recharge:** no están instaladas en la tienda. La causa exacta del req. 2 y la fuente de datos del req. 1 son conceptuales en esa parte.
- **Datos personales:** no se guardan a propósito (RGPD). Si otra área los necesita, se agregan con su justificación.

**Cómo usé IA:** como plantea la simulación, para buena parte del código, los tests, el análisis de datos y la documentación. Revisé cada decisión de diseño y la dejé anotada con su porqué en `log.md`: cómo detectar el cambio de dirección sin base de datos, el orden por `updated_at`, qué datos no guardar, cómo evitar bucles. Las consultas al Lead Tech las escribí sin IA, como pide la consigna.
