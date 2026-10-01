"""Algoritmos propios de caminos y bosques mínimos con colas de prioridad.

Proyecto de Matemática Discreta (IMAT, ICAI): Enrique Capella.
"""

from itertools import count
import heapq
import math
from typing import Callable, Hashable

import networkx as nx

Peso = Callable[[nx.Graph, Hashable, Hashable], float]


def _valida_grafo(G: nx.Graph, peso: Peso, *, no_negativos: bool = False) -> None:
    if G.is_multigraph():
        raise ValueError("Simplifique las aristas paralelas antes de aplicar el algoritmo.")
    for u, v in G.edges:
        valor = float(peso(G, u, v))
        if not math.isfinite(valor) or (no_negativos and valor < 0):
            raise ValueError("Los pesos deben ser finitos y, para Dijkstra, no negativos.")


def _dijkstra(G: nx.Graph, origen: Hashable, peso: Peso, destino=None) -> dict:
    if origen not in G:
        raise nx.NodeNotFound(f"No existe el nodo de origen {origen!r}.")
    _valida_grafo(G, peso, no_negativos=True)
    distancias = {origen: 0.0}
    padres = {origen: None}
    orden = count()  # Evita comparar etiquetas heterogéneas cuando hay empates.
    cola = [(0.0, next(orden), origen)]
    while cola:
        distancia, _, u = heapq.heappop(cola)
        if distancia != distancias[u]:
            continue
        if u == destino:
            break
        for v in G.neighbors(u):
            candidato = distancia + float(peso(G, u, v))
            if candidato < distancias.get(v, math.inf):
                distancias[v] = candidato
                padres[v] = u
                heapq.heappush(cola, (candidato, next(orden), v))
    return padres


def dijkstra(G: nx.Graph, origen: Hashable, peso: Peso) -> dict:
    """Devuelve los padres de los nodos alcanzables desde origen. O((V+E) log V)."""
    return _dijkstra(G, origen, peso)


def camino_minimo(G: nx.Graph, origen: Hashable, destino: Hashable, peso: Peso) -> list:
    """Dijkstra con parada en destino y reconstrucción del camino."""
    if destino not in G:
        raise nx.NodeNotFound(f"No existe el nodo de destino {destino!r}.")
    padres = _dijkstra(G, origen, peso, destino)
    if destino not in padres:
        raise nx.NetworkXNoPath(f"No hay camino entre {origen!r} y {destino!r}.")
    camino = [destino]
    while camino[-1] != origen:
        camino.append(padres[camino[-1]])
    return camino[::-1]


def prim(G: nx.Graph, peso: Peso) -> dict:
    """Bosque abarcador mínimo de un grafo NO dirigido. O(E log E)."""
    if G.is_directed():
        raise ValueError("Prim requiere un grafo no dirigido.")
    _valida_grafo(G, peso)
    padres, visitados = {}, set()
    orden = count()
    for raiz in G:
        if raiz in visitados:
            continue
        padres[raiz] = None
        cola = [(0.0, next(orden), None, raiz)]
        while cola:
            _, _, padre, u = heapq.heappop(cola)
            if u in visitados:
                continue
            visitados.add(u)
            padres[u] = padre
            for v in G.neighbors(u):
                if v not in visitados:
                    heapq.heappush(cola, (float(peso(G, u, v)), next(orden), u, v))
    return padres


def kruskal(G: nx.Graph, peso: Peso) -> list[tuple]:
    """Bosque abarcador mínimo usando union-find. O(E log E)."""
    if G.is_directed():
        raise ValueError("Kruskal requiere un grafo no dirigido.")
    _valida_grafo(G, peso)
    padres = {u: u for u in G}
    rangos = dict.fromkeys(G, 0)

    def find(u):
        while padres[u] != u:
            padres[u] = padres[padres[u]]
            u = padres[u]
        return u

    resultado = []
    for u, v in sorted(G.edges, key=lambda arista: float(peso(G, *arista))):
        ru, rv = find(u), find(v)
        if ru == rv:
            continue
        if rangos[ru] < rangos[rv]:
            ru, rv = rv, ru
        padres[rv] = ru
        if rangos[ru] == rangos[rv]:
            rangos[ru] += 1
        resultado.append((u, v))
    return resultado
