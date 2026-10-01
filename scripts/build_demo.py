"""Reproduce el recorte de demostración a partir de los dos datos originales."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import osmnx as ox


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'data/demo')
    args = parser.parse_args()
    source = args.source_dir
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    G = ox.load_graphml(source / 'madrid.graphml')
    west, south, east, north = -3.725, 40.412, -3.681, 40.440
    nodos = [n for n, d in G.nodes(data=True) if west <= d['x'] <= east and south <= d['y'] <= north]
    demo = G.subgraph(nodos).copy()
    ox.save_graphml(demo, output / 'madrid.graphml')
    columnas = ['VIA_CLASE','VIA_PAR','VIA_NOMBRE','NUMERO','LATITUD','LONGITUD']
    with (source / 'direcciones.csv').open(encoding='latin1', newline='') as archivo:
        filas = [r for r in csv.DictReader(archivo,delimiter=';') if
                 (r['VIA_NOMBRE'], r['NUMERO']) in [('ALBERTO AGUILERA','23'), ('ALCALA','23')] and not r['CALIFICADOR'].strip()]
    with (output / 'direcciones.csv').open('w', encoding='latin1', newline='') as archivo:
        writer = csv.DictWriter(archivo,fieldnames=columnas,delimiter=';',extrasaction='ignore')
        writer.writeheader()
        writer.writerows(filas)
    manifest = {
        'description': 'Recorte del centro de Madrid a partir del ZIP del proyecto académico.',
        'source_snapshot_date': 'Desconocida; no se presenta como cartografía actualizada.',
        'bbox_west_south_east_north': [west,south,east,north],
        'nodes': demo.number_of_nodes(), 'edges': demo.number_of_edges(), 'addresses':len(filas),
        'source_sha256': {n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in ['madrid.graphml','direcciones.csv']},
        'sources': {
            'graph': 'https://www.openstreetmap.org/copyright',
            'addresses': 'https://datos.madrid.es/dataset/213605-0-callejero-oficial-madrid',
        },
        'licenses': {'graph':'ODbL-1.0','addresses':'CC-BY-4.0'},
    }
    (output / 'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ['nodes','edges','addresses']},indent=2))


if __name__ == '__main__':
    main()
