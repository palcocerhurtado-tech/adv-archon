# Plan Tecnico: Geolocalizacion Normativa

## Objetivo

Extender `ADV ARCHON` para aceptar coordenadas (`lat,lng`) y convertirlas en un
flujo urbanistico completo:

`coords -> municipio -> parcela/catastro -> PGOU/normativa -> informe con confianza`

La clave es no romper el contrato actual del sistema, que hoy gira alrededor de:

`plan + municipality -> plan_compliance_check()`

Por eso la geolocalizacion debe entrar como una capa previa de resolucion del
emplazamiento, no como una reescritura del bloque PGOU existente.


## Principio de integracion

Mantener intactos estos carriles ya existentes:

- `UrbanComplianceTools.plan_compliance_check(plan_path, municipality)`
- slash commands `/pgou check` y `/pgou report`
- API `/v1/compliance/check` y `/v1/compliance/report`
- auto-trigger desktop para PDFs

La capacidad nueva debe producir un `site context` estructurado que, al final,
desemboque en un `municipality` validado y, si es posible, tambien una parcela
o referencia catastral.


## Flujo objetivo

### Paso 1. Resolver ubicacion

Input posible:

- coordenadas `lat,lng`
- coordenadas embebidas en el prompt
- coordenadas asociadas a un PDF o expediente

Salida:

- municipio
- provincia
- comunidad autonoma
- direccion aproximada
- proveedor usado
- confianza

### Paso 2. Resolver parcela / catastro

Si las coordenadas son suficientemente precisas:

- referencia catastral si existe
- identificador de parcela
- geometria basica o bounding box
- si cae dentro o cerca de lindes
- confianza

### Paso 3. Resolver normativa aplicable

Con el municipio ya resuelto:

- comprobar si el PGOU ya esta indexado
- si no lo esta, lanzar `pgou_fetch` o `pgou_add`
- devolver tambien una lista de normativa complementaria pendiente:
  - CTE estatal
  - normativa autonoma
  - capas sectoriales futuras

### Paso 4. Generar informe

El informe debe separar con claridad:

- `hechos resueltos`
- `fuentes usadas`
- `nivel de confianza`
- `lagunas pendientes`
- `siguiente accion recomendada`


## APIs y proveedores recomendados

### MVP recomendado

Orden de proveedores:

1. `Catastro / servicios abiertos`
2. `IDEE / IGN / CNIG / CartoCiudad`
3. `Google Geocoding` como fallback premium de UX

### Por que este orden

- Para producto urbanistico en Espana, la fuente oficial debe mandar.
- Google es util para reverse geocoding y UX, pero no debe ser la unica verdad.
- El municipio puede resolverse con geocodificacion; la parcela exige capa
  catastral o equivalente.

### Claves realmente necesarias

#### Obligatorias para arrancar esta fase

- `ninguna nueva` si empezamos con fuentes abiertas oficiales y los conectores
  HTTP/web ya existentes.

#### Recomendadas

- `GOOGLE_GEOCODING_API_KEY`
  - para reverse geocoding de respaldo
  - mejora velocidad y experiencia
  - no sustituye Catastro/IGN

#### No subir todavia salvo que luego haga falta

- `GOOGLE_MAPS_API_KEY`
- `CARTOCIUDAD_API_KEY`
- `IGN_API_KEY`
- `CATASTRO_API_KEY`

Ahora mismo no hay evidencia en la repo de que necesitemos esas claves para el
MVP. Si alguna API concreta las exige al implementarla, se anadiran despues.


## Donde guardar secretos

Seguir el patron actual del proyecto:

- secretos en `~/.adv-archon/.env`
- configuracion no secreta en `~/.adv-archon/config.toml`

Variables nuevas recomendadas:

- `GOOGLE_GEOCODING_API_KEY`

No reutilizar `GOOGLE_API_KEY`, porque hoy ya sirve de fallback para Gemini.


## Nueva configuracion propuesta

Anadir `GeoConfig` en `src/adv_archon/core/config.py`:

```toml
[geo]
enabled = true
provider = "hybrid"
country = "ES"
google_enabled = true
catastro_enabled = true
ign_enabled = true
rate_limit_interval_seconds = 0.25
retry_attempts = 3
retry_base_delay_seconds = 0.8
max_concurrency = 2
cache_ttl_hours = 168
```

Campos sugeridos:

- `enabled`
- `provider`
- `country`
- `google_enabled`
- `catastro_enabled`
- `ign_enabled`
- `rate_limit_interval_seconds`
- `retry_attempts`
- `retry_base_delay_seconds`
- `max_concurrency`
- `cache_ttl_hours`


## Modulos nuevos a anadir

### Nuevos modulos core

- `src/adv_archon/core/geo_store.py`
  - SQLite para cachear resoluciones geograficas
  - no mezclar con `PGOUStore`

- `src/adv_archon/core/site_context.py`
  - dataclasses para:
    - `CoordinateInput`
    - `LocationResolution`
    - `ParcelResolution`
    - `ApplicableRegulationContext`
    - `SiteContext`

### Nuevos modulos de integracion

- `src/adv_archon/integrations/google_geocoding.py`
  - reverse geocoding opcional con Google

- `src/adv_archon/integrations/catastro.py`
  - consulta de datos catastrales / coordenadas / referencia

- `src/adv_archon/integrations/ign_geo.py`
  - municipio, toponimia o verificacion geoespacial complementaria

### Nueva capa de herramientas

- `src/adv_archon/tools/geo_tools.py`
  - tools de alto nivel:
    - `resolve_coordinates`
    - `resolve_parcel`
    - `resolve_site_context`
    - `site_applicability_report`

### Extension del bloque urbanistico

- ampliar `src/adv_archon/tools/urban_compliance.py` con wrappers, sin romper lo
  existente:
  - `plan_compliance_check_at_coordinates(plan_path, latitude, longitude)`
  - `resolve_normative_context(latitude, longitude)`


## Persistencia nueva

No reutilizar `pgou.db` para coordenadas o parcela.

### Base nueva propuesta

- `geo.db`

### Tablas sugeridas

#### `location_resolutions`

- `id`
- `latitude`
- `longitude`
- `municipality`
- `province`
- `region`
- `formatted_address`
- `provider`
- `confidence`
- `resolved_at`
- `raw_payload_json`

#### `parcel_resolutions`

- `id`
- `latitude`
- `longitude`
- `municipality`
- `cadastral_reference`
- `parcel_label`
- `source`
- `confidence`
- `geometry_json`
- `resolved_at`
- `raw_payload_json`

#### `site_context_cache`

- `id`
- `latitude`
- `longitude`
- `municipality`
- `cadastral_reference`
- `pgou_indexed`
- `confidence_summary`
- `sources_json`
- `resolved_at`


## Encaje exacto en la repo actual

### `core/config.py`

Anadir:

- `GeoConfig`
- `paths.geo_db`
- carga de `GOOGLE_GEOCODING_API_KEY`

### `core/runtime.py`

Anadir:

- instanciacion de `GeoStore`
- instanciacion de `GeoTools`
- registro de nuevas tool specs

Importante:

- no tocar el contrato actual de `UrbanComplianceTools`
- solo enriquecer `_maybe_build_compliance_prompt()` para que, si detecta
  coordenadas y contexto urbanistico, resuelva primero el emplazamiento

### `core/intent.py`

Anadir:

- deteccion de coordenadas `lat,lng`
- helper `extract_coordinates()`
- mantener heuristica restrictiva para no secuestrar PDFs normales

### `ui/commands.py`

Anadir sin romper `/pgou` actual:

- `/pgou locate <lat> <lng>`
- `/pgou context <lat> <lng>`
- `/pgou check-coords <plano.pdf> <lat> <lng>`

### `desktop/workers.py`

Mejorar:

- si el usuario sube un PDF y pega coordenadas, usar coords en vez de pedir
  municipio
- no autoactivar geolocalizacion si el usuario solo quiere resumir un PDF

### `api`

Anadir endpoints nuevos, sin tocar los actuales:

- `POST /v1/location/resolve`
- `POST /v1/location/parcel`
- `POST /v1/location/context`
- opcional despues:
  - `POST /v1/compliance/check-by-coordinates`

Esto permite mantener compatibilidad con clientes actuales.


## Datos que debe devolver el informe

El informe de aplicabilidad deberia devolver:

- coordenadas de entrada
- municipio resuelto
- parcela / referencia catastral, si existe
- fuente de resolucion
- confianza por etapa
- PGOU indexado o no
- normativa municipal localizada
- advertencias:
  - municipio resuelto por estimacion
  - coordenadas cerca de lindes
  - parcela no identificada
  - normativa municipal no indexada
  - capas sectoriales no verificadas aun


## Niveles de confianza

Usar al menos estos niveles:

- `high`
  - municipio y parcela coherentes y validados por fuente oficial
- `medium`
  - municipio claro, parcela dudosa o no resuelta
- `low`
  - municipio estimado o conflicto entre proveedores

Y guardar siempre:

- proveedor primario
- proveedores de verificacion
- timestamp


## Fase de implementacion recomendada

### Fase 1

- `coords -> municipio`
- `GeoConfig`
- `GeoStore`
- `resolve_coordinates`
- comando `/pgou locate`
- endpoint `/v1/location/resolve`

### Fase 2

- `coords -> parcela / referencia catastral`
- `resolve_parcel`
- cache en `geo.db`
- endpoint `/v1/location/parcel`

### Fase 3

- `coords -> site context -> PGOU`
- `resolve_site_context`
- `/pgou context`
- endpoint `/v1/location/context`

### Fase 4

- `plan + coords -> compliance`
- `check-by-coordinates`
- UX desktop mejorada


## Claves que me tienes que pasar

### Si quieres arrancar ya con el MVP

Solo esta:

- `GOOGLE_GEOCODING_API_KEY`

### Si no quieres depender de Google al principio

No hace falta pasarme ninguna clave nueva todavia. Podemos arrancar con el
camino oficial/open-first y dejar Google como fallback posterior.


## Recomendacion final

La mejor decision para esta repo es:

- `open-first` para Catastro/IGN/IDEE
- `Google Geocoding` como mejora opcional
- `GeoStore` separado de `PGOUStore`
- endpoints y comandos nuevos, sin romper el contrato actual

Eso permite evolucionar el producto urbanistico sin desestabilizar ni la CLI,
ni el desktop, ni la API existente.
