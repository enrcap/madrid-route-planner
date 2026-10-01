from pathlib import Path
import subprocess
import sys

import networkx as nx
import pytest
from shapely.geometry import LineString

from callejero import AddressNotFoundError, ROOT, busca_direccion, carga_callejero, carga_grafo, dms_to_decimal
from grafo_pesado import camino_minimo
from gps import (
    calcula_peso_tiempo_esperado, encuentra_nodo_mas_cercano, genera_instrucciones,
    indica_giro, longitud_arista, prepara_grafo, tiempo_arista, velocidad_arista,
)


@pytest.mark.parametrize("texto,esperado", [
    ('40°30\'0" N', 40.5), ("3°42'40.53'' W", -(3 + 42/60 + 40.53/3600)),
    ('3°0\'0" O', -3), ('10°30\'0" S', -10.5),
])
def test_conversion_coordenadas(texto, esperado):
    assert dms_to_decimal(texto) == pytest.approx(esperado)


@pytest.mark.parametrize("texto", ['90°1\'0" N', '3°70\'0" W', 'coordenada', '180°0\'1" E'])
def test_coordenada_invalida(texto):
    with pytest.raises(ValueError):
        dms_to_decimal(texto)


def test_direcciones_exactas_y_sin_mutaciones():
    df = carga_callejero(ROOT / 'data/demo/direcciones.csv')
    antes = df.copy(deep=True)
    assert busca_direccion('  CALLE de Alberto Aguilera,23  ', df) == busca_direccion('Calle de Alberto Aguilera, 23', df)
    assert df.equals(antes)
    with pytest.raises(AddressNotFoundError):
        busca_direccion('Calle de Alberto, 23', df)
    with pytest.raises(AddressNotFoundError):
        busca_direccion('Calle de Alberto Aguilera, abc', df)
    extra = df.iloc[[0]].copy()
    extra['latitud'] += 0.01
    import pandas as pd
    with pytest.raises(AddressNotFoundError, match='ambigua'):
        busca_direccion('Calle de Alberto Aguilera, 23', pd.concat([df, extra]))


def test_aristas_paralelas_seleccionadas_segun_modo():
    G = nx.MultiDiGraph(crs='epsg:4326')
    G.add_node(1, x=0., y=0.)
    G.add_node(2, x=1., y=0., highway='traffic_signals')
    G.add_edge(1, 2, key=0, length=100., maxspeed='10', name='Corta')
    G.add_edge(1, 2, key=1, length=200., maxspeed='100', name='Rápida')
    G.add_edge(1, 1, length=1., maxspeed='50')
    distancia = prepara_grafo(G, 'distance')
    tiempo = prepara_grafo(G, 'time')
    espera = prepara_grafo(G, 'signals')
    assert distancia[1][2]['original_key'] == 0
    assert tiempo[1][2]['original_key'] == 1
    assert espera[1][2]['route_cost'] == pytest.approx(7.2 + 24)
    assert not distancia.has_edge(1, 1)
    assert distancia.graph['crs'] == G.graph['crs']
    G.nodes[2].pop('highway')
    assert calcula_peso_tiempo_esperado(prepara_grafo(G, 'time'), 1, 2) == pytest.approx(7.2)


@pytest.mark.parametrize("raw,esperado", [('30 mph', 48.28032), (['50','30'],30), ('50;30',30), (None,30), ([],30), ('signals',30), ('0',30)])
def test_limites_velocidad(raw, esperado):
    assert velocidad_arista({'maxspeed':raw,'highway':['residential']}) == pytest.approx(esperado)
    assert tiempo_arista({'length':100, 'maxspeed':50}) == pytest.approx(7.2)


def test_longitud_no_se_inventa():
    with pytest.raises(KeyError):
        longitud_arista({})
    with pytest.raises(ValueError):
        longitud_arista({'length':-1})


def test_giros_usan_geometria_y_no_indice():
    G = nx.DiGraph()
    for n,x,y in [(1,0,0),(2,0,1),(3,1,1),(4,-1,1),(5,0,2)]:
        G.add_node(n,x=x,y=y)
    for u,v,nombre in [(1,2,'A'),(2,3,'B'),(2,4,'C'),(2,5,'D')]:
        G.add_edge(u,v,length=100,name=nombre)
    assert indica_giro(G,1,2,3) == 'Gire a la derecha'
    assert indica_giro(G,1,2,4) == 'Gire a la izquierda'
    assert indica_giro(G,1,2,5) == 'Continúe recto'
    G[1][2]['geometry'] = LineString([(0,1),(0,0)])
    assert indica_giro(G,1,2,3) == 'Gire a la derecha'
    assert 'derecha' in genera_instrucciones(G,[1,2,3])[1]
    assert len(genera_instrucciones(G,[1])) == 1


def test_nodo_cercano_considera_latitud():
    G = nx.Graph()
    G.add_node('este',x=1,y=80)
    G.add_node('norte',x=0,y=80.5)
    assert encuentra_nodo_mas_cercano(G,80,0) == 'este'
    with pytest.raises(ValueError):
        encuentra_nodo_mas_cercano(nx.Graph(),40,-3)


def test_demo_ejecutable_sin_red(tmp_path):
    import os
    env = {**os.environ, 'MPLBACKEND': 'Agg'}
    imagen = tmp_path / 'ruta.png'
    resultado = subprocess.run(
        [sys.executable, str(ROOT / 'gps.py'), '--demo', '--mode', 'compare', '--no-show', '--save-map', str(imagen)],
        cwd=tmp_path, env=env, text=True, capture_output=True, timeout=60,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert imagen.is_file() and imagen.stat().st_size > 10000
    assert 'km' in resultado.stdout


def test_importar_gps_no_inicia_aplicacion():
    resultado = subprocess.run([sys.executable,'-c','import gps'],cwd=ROOT,text=True,capture_output=True,timeout=30)
    assert resultado.returncode == 0 and resultado.stdout == ''


@pytest.mark.parametrize('modo', ['distance', 'time', 'signals'])
def test_ruta_demo_optima_frente_a_networkx(modo):
    df = carga_callejero(ROOT / 'data/demo/direcciones.csv')
    grafo = prepara_grafo(carga_grafo(ROOT / 'data/demo/madrid.graphml'), modo)
    origen = encuentra_nodo_mas_cercano(grafo, *busca_direccion('Calle de Alberto Aguilera, 23', df))
    destino = encuentra_nodo_mas_cercano(grafo, *busca_direccion('Calle de Alcala, 23', df))
    ruta = camino_minimo(grafo, origen, destino, lambda g,u,v:g[u][v]['route_cost'])
    coste = sum(grafo[u][v]['route_cost'] for u,v in zip(ruta,ruta[1:]))
    assert coste == pytest.approx(nx.shortest_path_length(grafo, origen, destino, weight='route_cost'))
