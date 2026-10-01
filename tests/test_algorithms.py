import math
import random

import networkx as nx
import pytest

from grafo_pesado import camino_minimo, dijkstra, kruskal, prim


def peso(G, u, v):
    return G[u][v]["weight"]


def coste(G, ruta):
    return sum(peso(G, u, v) for u, v in zip(ruta, ruta[1:]))


@pytest.mark.parametrize("seed", range(10))
def test_dijkstra_coincide_con_networkx(seed):
    rng = random.Random(seed)
    G = nx.gnp_random_graph(25, 0.18, seed=seed, directed=True)
    for u, v in G.edges:
        G[u][v]["weight"] = rng.randint(0, 100)
    distancias = nx.single_source_dijkstra_path_length(G, 0, weight="weight")
    assert set(dijkstra(G, 0, peso)) == set(distancias)
    for destino, distancia in distancias.items():
        ruta = camino_minimo(G, 0, destino, peso)
        assert ruta[0] == 0 and ruta[-1] == destino
        assert coste(G, ruta) == distancia


def test_destino_inalcanzable_y_nodo_ausente():
    G = nx.DiGraph()
    G.add_nodes_from([1, 2])
    with pytest.raises(nx.NetworkXNoPath):
        camino_minimo(G, 1, 2, peso)
    with pytest.raises(nx.NodeNotFound):
        camino_minimo(G, 1, 3, peso)
    with pytest.raises(nx.NodeNotFound):
        dijkstra(G, 3, peso)
    assert camino_minimo(G, 1, 1, peso) == [1]


def test_empates_con_etiquetas_heterogeneas():
    G = nx.DiGraph()
    G.add_weighted_edges_from([(0, "a", 1), (0, 2, 1), ("a", "fin", 2), (2, "fin", 1)])
    assert coste(G, camino_minimo(G, 0, "fin", peso)) == 2


@pytest.mark.parametrize("valor", [-1, math.inf, math.nan])
def test_dijkstra_rechaza_pesos_invalidos(valor):
    G = nx.DiGraph()
    G.add_edge(1, 2, weight=valor)
    with pytest.raises(ValueError):
        camino_minimo(G, 1, 2, peso)


@pytest.mark.parametrize("seed", range(10))
def test_bosques_minimos_coinciden_con_networkx(seed):
    rng = random.Random(seed)
    G = nx.gnp_random_graph(20, 0.12, seed=seed)
    G.add_node("aislado")
    for u, v in G.edges:
        G[u][v]["weight"] = rng.randint(-10, 20)
    esperado = nx.minimum_spanning_tree(G, weight="weight")
    padres = prim(G, peso)
    aristas_prim = [(u, v) for v, u in padres.items() if u is not None]
    for aristas in [aristas_prim, kruskal(G, peso)]:
        bosque = nx.Graph()
        bosque.add_nodes_from(G)
        bosque.add_edges_from(aristas)
        assert nx.is_forest(bosque)
        assert nx.number_connected_components(bosque) == nx.number_connected_components(G)
        assert len(aristas) == esperado.number_of_edges()
        assert sum(peso(G, u, v) for u, v in aristas) == esperado.size(weight="weight")
    assert padres["aislado"] is None


@pytest.mark.parametrize("algoritmo", [prim, kruskal])
def test_mst_rechaza_grafo_dirigido(algoritmo):
    with pytest.raises(ValueError):
        algoritmo(nx.DiGraph(), peso)
    assert algoritmo(nx.Graph(), peso) == ({} if algoritmo is prim else [])


def test_prim_admite_empates_con_etiquetas_heterogeneas():
    G = nx.Graph()
    G.add_weighted_edges_from([(0, "a", 1), (0, 2, 1), ("a", 2, 2)])
    padres = prim(G, peso)
    assert sum(peso(G, u, v) for v, u in padres.items() if u is not None) == 2
