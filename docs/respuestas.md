# Simulación Natulim · Respuestas

Gregorio Martocci · Repo: `<URL del repo en GitHub>`

> Lo que está entre ⟦ ⟧ se completa con lo que se vea en la tienda de desarrollo.

---

## Requerimiento 1 · Mensaje para Growth (Discord)

> Hola! Suscriptores nuevos de los últimos 6 meses (⟦dd/mm/aaaa⟧ al ⟦dd/mm/aaaa⟧): **península ⟦X⟧, Canarias ⟦Y⟧** (⟦X/Y⟧ a 1). Cuento clientes cuya primera suscripción empezó en ese período, por su dirección de envío; península = España sin Baleares, Ceuta ni Melilla. Si os sirve lo desgloso por mes.

**Cómo lo saqué.** En producción la fuente es Recharge: su API de suscripciones filtrada por fecha de creación, agrupando por cliente y por provincia de la dirección de envío. Como Recharge no está en la tienda de desarrollo, usé lo que Recharge deja en Shopify: el primer pedido de cada suscripción lleva el tag `Subscription First Order`. El script es `scripts/suscriptores.py`. Supuestos que confirmé con el Lead Tech: ⟦qué se cuenta como "suscriptor nuevo" y qué entra en "península"⟧.

---

## Requerimiento 2 · Diagnóstico de bundles (para el Lead Tech)

> **Resumen:** no es un problema del software del 3PL. ⟦Causa confirmada al revisar los pedidos.⟧
>
> **Qué revisé.** Los pedidos #6491 (no recibido) y #6480 (recibido) en la tienda de desarrollo:
>
> | | #6480 (recibido) | #6491 (no recibido) |
> |---|---|---|
> | Packs que contiene | ⟦⟧ | ⟦⟧ |
> | ¿Llegó desglosado a líneas de componentes? | ⟦⟧ | ⟦⟧ |
> | SKU de las líneas | ⟦⟧ | ⟦⟧ |
> | Origen (web, suscripción/Recharge, draft order, POS) | ⟦⟧ | ⟦⟧ |
> | Tags y propiedades de línea | ⟦⟧ | ⟦⟧ |
> | Estado de preparación / fulfillment orders | ⟦⟧ | ⟦⟧ |
>
> **Lo que está pasando.** Los dos reportes describen el mismo fallo desde lados distintos y los dos llegan a una causa equivocada:
>
> - Logística dice que el 3PL "no arma el kit por un problema en su software". Pero el 3PL **nunca arma kits a partir del SKU del pack**: el pack no existe en su sistema y solo puede preparar los componentes. Si le llega una línea con el pack sin desglosar, recibe un SKU que no conoce y el pedido se queda sin preparar. El síntoma que ven en el 3PL es la consecuencia, no la causa.
> - CX culpa a "la aplicación de Growth" en general, pero la app **sí desglosa** el Pack limpiacristales. Lo que falla es el desglose de **un pack concreto**, el Pack Esenciales del hogar.
> - ⟦#6491 contiene el Pack Esenciales del hogar y llegó sin desglosar; #6480 contiene el Pack limpiacristales (o ningún pack) y sí se desglosó.⟧
>
> **Causa más probable** (la app no está instalada en la dev store, así que esta parte es por descarte): la app no tiene bien configurado el Pack Esenciales del hogar. Lo más común es que le falte la definición de componentes (el metacampo o la tabla que relaciona el pack con sus productos), que algún componente no tenga SKU o que el pack tenga una variante nueva que la app no reconoce. ⟦Si #6491 vino de Recharge: los pedidos de suscripción los crea Recharge por API y la app puede no estar escuchando ese origen.⟧
>
> **Qué hay que hacer**
> 1. **Hoy:** desglosar a mano #6491 (editar el pedido: quitar el pack, agregar sus componentes a precio 0) y reenviarlo al 3PL. Avisar a CX para que le escriba al cliente.
> 2. **Hoy:** buscar todos los pedidos abiertos con el SKU del Pack Esenciales del hogar sin desglosar (`sku:⟦SKU⟧ fulfillment_status:unfulfilled`) y hacer lo mismo con cada uno.
> 3. **Esta semana:** corregir la configuración del pack en la app y agregar un test por cada pack existente. Es una app hecha con IA y sin pruebas: el próximo pack nuevo va a fallar igual.
> 4. **Alerta:** que ningún pedido llegue al 3PL con un SKU de pack. Un chequeo antes del envío (o en el webhook de creación de pedido) que avise por Slack/Discord a Logística.
> 5. **A mediano plazo:** evaluar los bundles nativos de Shopify (productos con componentes), que mandan los componentes al fulfillment sin una app propia en el medio.
>
> Le respondería a Logística y a CX con el mismo resumen, para cerrar las dos hipótesis.

---

## Requerimiento 3 · Sincronización de pedidos

**¿Lo ponemos ya en producción?** Todavía no tal como está: hoy corre en una máquina con un túnel. La lógica sí está lista: verifica la firma, ignora los duplicados y el desorden de los webhooks, y está cubierta por tests. Le faltan tres cosas antes de que alguien pueda confiar en esa base:

1. **Un lugar estable para correr**, con disco persistente para SQLite (un servicio pequeño en Fly.io o Railway con volumen, o una VM). En los planes gratuitos con disco efímero la base se pierde en cada despliegue.
2. **Reconciliación.** Los webhooks son "al menos una vez", no "exactamente una vez": si el servicio está caído más tiempo del que Shopify reintenta, se pierden cambios. Hace falta un job cada hora que pida a la Admin API los pedidos con `updated_at` posterior al último sincronizado y los pase por la misma función de guardado.
3. **Monitoreo y respaldo**: alerta si `/health` falla o si hay respuestas 500, y copia continua de la base (por ejemplo con Litestream).

**¿Cómo lo ponemos en producción?**
1. Crear la app en el Dev Dashboard de la organización de producción (no reutilizar la de dev) e instalarla en la tienda.
2. Desplegar el servicio con `SYNC_ACTIVO=true` y `MARCAR_ACTIVO=false`, con el `.env` cargado como secretos del host.
3. Registrar los webhooks con `scripts/registrar_webhooks.py` apuntando a la URL de producción. Desde ese momento corre el "inicio" de la sincronización: los pedidos anteriores no se tienen en cuenta, como se acordó.
4. Verificar con un pedido real (o uno de prueba que se cancela) que aparece en la base.
5. Activar la reconciliación horaria y las alertas.
6. Si la base va a ser consultada por otras áreas, pasar de SQLite a Postgres: el esquema es el mismo.

---

## Requerimiento 4 · Marcar pedidos que cambian a Canarias

**¿Lo ponemos ya en producción?** Sí, con poco riesgo. Solo agrega un tag y un metacampo, no modifica nada más del pedido, es idempotente y no entra en bucles. Antes, una prueba en la tienda de desarrollo con alguien de CX haciendo una edición real de dirección.

**¿Cómo lo ponemos en producción?**
1. Mismo servicio y misma app: desplegar con `MARCAR_ACTIVO=true` (no necesita base de datos).
2. Registrar los webhooks (si no estaban por el req. 3).
3. Correr una vez `scripts/preparar_pedidos_abiertos.py`. Anota la región actual de los pedidos abiertos, para que un cambio de dirección sobre pedidos creados antes del despliegue también se detecte.
4. Avisar a CX y a Logística del tag y para qué sirve (por ejemplo, un filtro guardado en el admin de pedidos `tag:cambio_a_pedido_para_canarias`).

**Decisiones a confirmar con el negocio:** un pedido que nace con dirección en Canarias no se etiqueta (no hubo cambio), y si la dirección vuelve a península el tag se queda (marca que hubo un cambio). ⟦Respuesta del Lead Tech⟧.

---

## Alcance

**Incluí**
- Req. 3 y 4 en un solo servicio, con verificación HMAC, idempotencia, orden por `updated_at`, borrados marcados y no eliminados, 38 tests y despliegue por requerimiento.
- Scripts para registrar webhooks, preparar pedidos previos al despliegue (req. 4) y calcular los suscriptores (req. 1).
- Diagnóstico del req. 2 basado en los pedidos de la tienda.
- `README.md` para instalar desde cero, `log.md` con las decisiones y `AGENTS.md` para que otra persona o una IA pueda seguir.

**Dejé fuera, y por qué**
- **Reconciliación del req. 3:** no hace falta para demostrar el flujo en la tienda de desarrollo, pero es lo primero que agregaría antes de producción (ver arriba).
- **Despliegue permanente:** corre en local con un túnel. Desplegarlo en un plan gratuito con disco efímero daría una falsa sensación de que está "en producción".
- **Inspección de la app de bundles y de Recharge:** no están instaladas en la tienda; el req. 2 y el origen de datos del req. 1 son conceptuales en esa parte.
- **Datos personales:** no se guardan a propósito (RGPD); si otra área los necesita, se agregan con su justificación.

**Cómo usé IA:** como plantea la simulación, para buena parte del código, los tests y la documentación. Revisé cada decisión de diseño (cómo detectar el cambio de dirección sin base de datos, el orden por `updated_at`, qué datos no guardar, cómo evitar bucles) y la dejé anotada con su porqué en `log.md`. Las consultas al Lead Tech las escribí sin IA, como pide la consigna.
