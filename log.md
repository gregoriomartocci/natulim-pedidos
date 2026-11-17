# Log de decisiones

Bitácora de la simulación: qué decidí, por qué y qué quedó pendiente. Lo más nuevo va abajo.

## 2026-11-12 — Arranque

- Repo vacío con `log.md` como primer commit, como pide el enunciado.
- Antes de tocar la tienda: contacto al Lead Tech por Discord (santiago.pesantez) para pedir acceso a la dev store, pasarle mi correo y la fecha de entrega.

## 2026-11-12 — Diseño general (req. 3 y 4)

- **Un solo servicio Python con un endpoint de webhooks** para los dos requerimientos: comparten app, credenciales y temas (`orders/create`, `orders/updated`). Cada uno se apaga con su variable (`SYNC_ACTIVO`, `MARCAR_ACTIVO`) para poder ponerlos en producción por separado.
- **Webhooks y no polling.** Es lo más simple que cumple "si el pedido cambia en Shopify, también debe cambiar en la app" en tiempo casi real. Riesgo conocido: un webhook se puede perder si el servicio está caído más que los reintentos de Shopify → en producción se suma una reconciliación horaria (anotado como alcance fuera).
- **Flask**: el servicio es un solo endpoint síncrono; no necesita más.
- **App del Dev Dashboard con client credentials.** Desde el 1/1/2026 Shopify no deja crear custom apps desde el admin. El token dura 24 h y se renueva solo. Se soporta también un token `shpat_` por si la tienda tiene una app legacy. A confirmar con el Lead Tech cómo se crea la app en la tienda dev.
- **Firma HMAC** con el client secret sobre el cuerpo crudo, comparación en tiempo constante, y se rechaza si el dominio de la tienda no es el configurado.
- **Errores → 500** para que Shopify reintente. Un webhook se anota como procesado solo cuando terminó bien.

## 2026-11-12 — Req. 3: sincronización

- **Upsert por id de Shopify** + tabla de `X-Shopify-Webhook-Id` procesados: los reintentos no duplican.
- **Gana el `updated_at` más nuevo**: los webhooks pueden llegar desordenados (un `updated` viejo que se reintenta tarde no pisa uno nuevo).
- **Líneas reemplazadas enteras** en cada versión: es la forma más simple de reflejar ediciones de pedido (agregar, quitar, cambiar cantidad). Se guardan `cantidad` y `cantidad_actual`, y las propiedades de línea en JSON porque ahí suelen viajar los datos de los bundles (útil para el req. 2).
- **Solo pedidos desde el go-live** (acordado con el área): la fecha de inicio se fija la primera vez que se crea la base; un `updated` de un pedido anterior se ignora para no tener pedidos a medias.
- **Borrado = marca** (`eliminado_en`), no se borra la fila.
- **Datos mínimos, sin datos personales** (RGPD): ni nombre, ni email, ni calle. País, provincia y CP alcanzan.
- **Importes como texto**, tal como los manda Shopify, para no perder precisión con floats.
- **SQLite en WAL** y un lock en el servidor: un solo escritor a la vez, que es lo que SQLite soporta de todos modos.

## 2026-11-12 — Req. 4: tag de Canarias

- **El problema es detectar el CAMBIO**: `orders/updated` trae la dirección actual, no la anterior, y no hay base de datos. Opciones evaluadas:
  - Etiquetar todo pedido con dirección de Canarias en cada update → marca también los que nacieron en Canarias, y el tag dice "cambio".
  - Usar la base del req. 3 → acopla los dos requerimientos y el 4 dice que no requiere base.
  - **Elegida:** guardar la última región conocida en un metacampo del propio pedido (`natulim.envio_canarias`). Es una función nativa de Shopify, no requiere base y sobrevive a reinicios.
- **Se lee el pedido fresco por GraphQL** en cada update en vez de confiar en el payload, que puede ser una versión vieja si llegó tarde.
- **Sin bucles**: el `tagsAdd` dispara otro `orders/updated`, pero el metacampo ya dice Canarias y no se hace nada.
- **Canarias** = provincia `GC`/`TF` o CP 35xxx/38xxx (el CP cubre direcciones cargadas a mano sin provincia).
- **Pedidos anteriores al despliegue** no tienen metacampo: el primer update solo fija el punto de partida. Para los abiertos, `scripts/preparar_pedidos_abiertos.py` se corre una vez el día del despliegue.
- **Preguntas para el Lead Tech:** ¿un pedido que nace en Canarias lleva el tag? (decidí que no). ¿Se quita el tag si la dirección vuelve a península? (decidí que no: marca que hubo un cambio).

## 2026-11-12 — Req. 1 y 2 (sin acceso a la tienda todavía)

- **Req. 1:** Recharge no está en la tienda dev. Recharge etiqueta el primer pedido de cada suscripción con `Subscription First Order`; `scripts/suscriptores.py` cuenta clientes únicos con ese pedido en los últimos 6 meses, por región de envío. Requiere `read_all_orders` (pedidos de más de 60 días). En producción, la fuente correcta es la API de Recharge. Preguntas: ¿suscriptor nuevo = cliente o suscripción? ¿Península excluye Baleares, Ceuta y Melilla?
- **Req. 2:** hipótesis antes de ver los pedidos: el 3PL no puede "armar el kit" porque el kit no existe en su sistema; si recibe el SKU del pack sin desglosar, el pedido se traba. Que el Pack limpiacristales sí se desglose descarta que la app esté rota en general: apunta a la configuración del Pack Esenciales del hogar. Pendiente: comparar #6491 y #6480 en la tienda.

## 2026-11-12 — Tests

- 38 tests con pytest, sin red: regiones, firma, sincronización (duplicados, desorden, inicio, borrado), tag de Canarias (todas las transiciones, bucle, ida y vuelta) y el endpoint completo con un Shopify falso.

## 2026-11-17 — Acceso a la tienda y prueba en vivo

- **Acceso:** Santiago pasó la tienda `natulim-sevica` (Shopify Plus App Development) y las credenciales de una app ya creada. Funcionan con client credentials, así que no hubo que crear la app. Las credenciales van en `.env`, que está fuera de git.
- **La tienda la comparten otros candidatos:** hay pedidos con `prueba-rrhh-yara` y dos que ya tenían `cambio_a_pedido_para_canarias`. Por eso:
  - la prueba crea sus propios pedidos con el tag `prueba-e2e` y no edita ningún pedido existente;
  - **no** corrí `preparar_pedidos_abiertos.py`, que escribiría un metacampo en ~5.500 pedidos ajenos;
  - el registro de webhooks solo agrega los nuestros y nunca borra otros.
- **Prueba de punta a punta** (`scripts/probar_en_tienda.py`, salida en `docs/evidencia.md`): alta, edición de línea, cambio a Canarias con tag, vuelta a península (el tag se queda), pedido nacido en Canarias sin tag, y borrado marcado. Todo OK; un solo `marcado`, sin bucle.
- **Req. 1:** 920 primeros pedidos de suscripción, uno por cliente, todos fechados entre el 14 y el 21/05/2026 (datos replicados). Con el corte estricto de 6 meses (17/05): península 386, Canarias 11, Baleares 14. Desde el 14/05: 854 / 32 / 34. Reporto el estricto y aclaro la sensibilidad al día de corte.
- **Req. 2:**
  - En la tienda ningún pack tiene componentes (`productVariantComponents` vacío, sin metacampos de bundle): el desglose lo hace la app, fuera de Shopify.
  - Los dos pedidos tienen el pack como una sola línea, y la linealización `natulim.line_items` lleva el código del pack (`PLD1`, `PEHD1`).
  - La diferencia que sí se ve es de producto: según su ficha, el **Pack Esenciales del Hogar incluye los otros cuatro packs** (Antical, Desengrasante, Limpiacristales y Multisuperficies), mientras que el Limpiacristales es botella + recargas.
  - Hipótesis principal: la app desglosa un solo nivel, o el Esenciales no está configurado.
  - Descartado como causa principal: envío a Baleares (hay 213 pedidos a Baleares con el mismo courier).
- **Herramientas:** cloudflared descargado del release oficial (no hay Homebrew en esta máquina).

## 2026-11-17 — Correcciones al documento final (después de releerlo)

- **Req. 2:** la tabla decía "Linealización que va al 3PL" para `natulim.line_items`. Es impreciso: se arma en Shopify **antes** del desglose, por eso #6480 (que sí llegó) también tiene códigos de pack. La alerta que proponía estaba mal apuntada: el chequeo va sobre lo que la app manda al 3PL. Corregido.
- **Req. 3 y 4:** sumé al "¿lo ponemos en producción?" el límite de unos 5 s que Shopify da para responder un webhook. Hoy se procesa dentro de la petición; en producción conviene responder 200 al instante y procesar en cola.
