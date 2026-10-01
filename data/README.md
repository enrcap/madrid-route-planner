# Datos y procedencia

## Demo incluida

`demo/madrid.graphml` contiene un recorte del centro de Madrid; `demo/direcciones.csv`
contiene dos direcciones para la demostración. Ambos proceden de los archivos del
proyecto académico original. Su fecha de captura no consta: la demo no representa
necesariamente el estado actual de las calles.

El CSV tiene el esquema del [Callejero oficial del Ayuntamiento de Madrid](https://datos.madrid.es/dataset/213605-0-callejero-oficial-madrid).
La identificación de su procedencia se basa en ese esquema y el contexto del proyecto;
el ZIP no incluía metadatos originales de descarga.

- Cartografía: © OpenStreetMap contributors, [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
- Direcciones: Ayuntamiento de Madrid, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), según la ficha del conjunto municipal.
- Transformaciones: selección espacial de nodos y aristas del mapa; selección de dos
  registros y seis columnas del callejero. No se han inventado calles ni coordenadas.
- `demo/manifest.json` registra el ámbito, tamaño, fuentes y hashes de los originales.

## Usar Madrid completo

1. Abra el [conjunto municipal](https://datos.madrid.es/dataset/213605-0-callejero-oficial-madrid).
2. Descargue **Relación de direcciones vigentes, con coordenadas** en CSV.
3. Guárdelo como `data/direcciones.csv`. El lector espera separador `;`, codificación
   Latin-1 y las columnas `VIA_CLASE`, `VIA_PAR`, `VIA_NOMBRE`, `NUMERO`, `LATITUD`,
   `LONGITUD`, con coordenadas DMS. Si cambia el esquema del proveedor, habrá que adaptar el lector.
4. Copie un GraphML compatible con OSMnx como `data/madrid.graphml`, o ejecute:

```bash
python gps.py --download-map --origin "Calle de Alberto Aguilera, 23" --destination "Calle de Alcala, 23" --mode compare
```

La primera descarga del mapa de todo Madrid puede tardar y depende de los servicios
de OpenStreetMap. Después se reutiliza el GraphML local. No se necesita descargar
nada para `--demo`.

Los dos archivos completos y la caché están excluidos de Git para mantener el
repositorio ligero. Se pueden usar otras carpetas con `--data-dir`.

## Reproducir el recorte

Si dispone de los dos archivos originales:

```bash
python scripts/build_demo.py --source-dir /ruta/a/los/datos/originales
```

El script usa los mismos límites espaciales y selecciona las direcciones de ejemplo.
Con otra fecha de datos, las rutas y el número de nodos pueden variar.
