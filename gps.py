"""Planificador de rutas por distancia, tiempo y espera en semáforos.

Proyecto de Matemática Discreta (IMAT, ICAI): Enrique Capella y Mateo Gómez-Acebo.
"""

import argparse
import math
from pathlib import Path
import re

import networkx as nx

from callejero import (
    ROOT, MAX_SPEEDS, AddressNotFoundError, ServiceNotAvailableError,
    busca_direccion, carga_callejero, carga_grafo, procesa_grafo,
)
from grafo_pesado import camino_minimo

MODOS = {"distance": "Distancia mínima", "time": "Tiempo mínimo", "signals": "Tiempo con espera"}
COLORES = {"distance": "#38bdf8", "time": "#fbbf24", "signals": "#fb7185"}


def longitud_arista(datos: dict) -> float:
    """Longitud válida en metros; un dato ausente nunca equivale a coste cero."""
    longitud = float(datos["length"])
    if not math.isfinite(longitud) or longitud < 0:
        raise ValueError("La longitud debe ser finita y no negativa.")
    return longitud


def velocidad_arista(datos: dict) -> float:
    """Velocidad en km/h; usa el menor límite válido o una estimación por vía.

    Admite límites numéricos, listas, valores separados por ';' y unidades mph.
    La estimación por vía es una hipótesis del modelo, no una norma de tráfico.
    """
    raw = datos.get("maxspeed")
    valores = raw if isinstance(raw, (list, tuple)) else [raw]
    limites = []
    for valor in valores:
        for parte in str(valor).lower().split(";"):
            match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(km/h|kph|mph)?\s*", parte)
            if match:
                limite = float(match[1]) * (1.609344 if match[2] == "mph" else 1)
                if limite > 0 and math.isfinite(limite):
                    limites.append(limite)
    if limites:
        return min(limites)
    vias = datos.get("highway", "")
    if not isinstance(vias, (list, tuple)):
        vias = [vias]
    return min((MAX_SPEEDS.get(via, 50) for via in vias), default=50)


def tiempo_arista(datos: dict) -> float:
    """Tiempo de circulación estimado en segundos, sin tráfico en tiempo real."""
    return longitud_arista(datos) * 3.6 / velocidad_arista(datos)


def es_semaforo(datos_nodo: dict) -> bool:
    valor = datos_nodo.get("highway")
    return valor == "traffic_signals" if not isinstance(valor, (list, tuple)) else "traffic_signals" in valor


def prepara_grafo(G: nx.MultiDiGraph, modo: str) -> nx.DiGraph:
    """Selecciona aristas según el modo, con espera solo en nodos señalizados."""
    if modo not in MODOS:
        raise ValueError(f"Modo desconocido: {modo}")
    grafo = procesa_grafo(G, longitud_arista if modo == "distance" else tiempo_arista)
    if modo == "signals":
        for _, v, datos in grafo.edges(data=True):
            if es_semaforo(grafo.nodes[v]):
                datos["route_cost"] += 0.8 * 30
    return grafo


def calcula_peso_longitud(G, u, v) -> float:
    return longitud_arista(G[u][v])


def calcula_peso_tiempo(G, u, v) -> float:
    return tiempo_arista(G[u][v])


def calcula_peso_tiempo_esperado(G, u, v) -> float:
    return tiempo_arista(G[u][v]) + (24 if es_semaforo(G.nodes[v]) else 0)


def encuentra_nodo_mas_cercano(G: nx.Graph, lat: float, lon: float):
    """Encuentra el nodo más cercano por distancia de gran círculo (haversine)."""
    if not G:
        raise ValueError("La red viaria está vacía.")
    if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordenadas fuera de rango.")
    phi = math.radians(lat)

    def distancia(nodo):
        datos = G.nodes[nodo]
        phi2 = math.radians(float(datos["y"]))
        return math.sin((phi2 - phi) / 2) ** 2 + math.cos(phi) * math.cos(phi2) * math.sin(math.radians(float(datos["x"]) - lon) / 2) ** 2

    return min(G, key=distancia)


def coordenadas_arista(G, u, v) -> list:
    """Devuelve la geometría orientada de u a v, o el segmento entre nodos."""
    origen = (float(G.nodes[u]["x"]), float(G.nodes[u]["y"]))
    destino = (float(G.nodes[v]["x"]), float(G.nodes[v]["y"]))
    geometria = G[u][v].get("geometry")
    puntos = list(geometria.coords) if geometria is not None else [origen, destino]
    distancia = lambda p: (p[0] - origen[0]) ** 2 + (p[1] - origen[1]) ** 2
    if distancia(puntos[-1]) < distancia(puntos[0]):
        puntos.reverse()
    return puntos


def rumbo(a, b) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    return math.degrees(math.atan2(
        math.sin(lon2 - lon1) * math.cos(lat2),
        math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1),
    ))


def indica_giro(G, a, b, c) -> str:
    entrada = coordenadas_arista(G, a, b)
    salida = coordenadas_arista(G, b, c)
    angulo = (rumbo(salida[0], salida[1]) - rumbo(entrada[-2], entrada[-1]) + 180) % 360 - 180
    if abs(angulo) < 25:
        return "Continúe recto"
    if abs(angulo) > 150:
        return "Cambie de sentido"
    return "Gire a la derecha" if angulo > 0 else "Gire a la izquierda"


def nombre_arista(datos):
    nombre = datos.get("name", "vía sin nombre")
    if isinstance(nombre, (list, tuple)):
        return " / ".join(map(str, nombre)) or "vía sin nombre"
    return str(nombre)


def genera_instrucciones(G: nx.Graph, ruta: list) -> list[str]:
    """Agrupa tramos por calle y estima giros mediante geometría geográfica."""
    if len(ruta) < 2:
        return ["Origen y destino coinciden en el mismo nodo de la red."]
    instrucciones = []
    calle_actual, distancia = None, 0.0
    for i, (u, v) in enumerate(zip(ruta, ruta[1:])):
        calle = nombre_arista(G[u][v])
        if calle_actual is not None and calle != calle_actual:
            instrucciones.append(f"Continúe por {calle_actual} durante {distancia:.0f} metros.")
            instrucciones.append(f"{indica_giro(G, ruta[i - 1], u, v)} hacia {calle}.")
            distancia = 0.0
        calle_actual = calle
        distancia += longitud_arista(G[u][v])
    instrucciones.append(f"Continúe por {calle_actual} durante {distancia:.0f} metros hasta el destino.")
    return instrucciones


def resumen_ruta(G, ruta) -> dict:
    aristas = [G[u][v] for u, v in zip(ruta, ruta[1:])]
    segundos = sum(tiempo_arista(d) for d in aristas)
    semaforos = sum(es_semaforo(G.nodes[v]) for v in ruta[1:])
    return {"distance_m": sum(longitud_arista(d) for d in aristas), "time_s": segundos,
            "expected_time_s": segundos + 24 * semaforos, "signals": semaforos}


def resalta_rutas(resultados: dict, archivo: Path | None = None, mostrar: bool = True):
    """Dibuja las geometrías reales y un resumen de las rutas calculadas."""
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D

    G = next(iter(resultados.values()))[0]
    fig, ax = plt.subplots(figsize=(12, 9), facecolor="#0f172a")
    ax.set_facecolor("#0f172a")
    base = [coordenadas_arista(G, u, v) for u, v in G.edges]
    ax.add_collection(LineCollection(base, colors="#475569", linewidths=0.65, alpha=0.55))
    leyenda = []
    for indice, (modo, (grafo, ruta)) in enumerate(resultados.items()):
        segmentos = [coordenadas_arista(grafo, u, v) for u, v in zip(ruta, ruta[1:])]
        ax.add_collection(LineCollection(segmentos, colors=COLORES[modo], linewidths=5.5 - indice * 1.4, alpha=0.9))
        datos = resumen_ruta(grafo, ruta)
        etiqueta = f"{MODOS[modo]}  ·  {datos['distance_m'] / 1000:.2f} km  ·  {datos['time_s'] / 60:.1f} min"
        if modo == "signals":
            etiqueta += f"  ·  {datos['expected_time_s'] / 60:.1f} min con espera"
        leyenda.append(Line2D([0], [0], color=COLORES[modo], lw=3, label=etiqueta))
    ruta = next(iter(resultados.values()))[1]
    for nodo, etiqueta, color in [(ruta[0], "ORIGEN", "#34d399"), (ruta[-1], "DESTINO", "#f8fafc")]:
        x, y = G.nodes[nodo]["x"], G.nodes[nodo]["y"]
        ax.scatter(x, y, s=100, color=color, edgecolors="#0f172a", zorder=10)
        ax.annotate(etiqueta, (x, y), xytext=(10, 8), textcoords="offset points", color=color, weight="bold", fontsize=10)
    ax.autoscale()
    ax.set_aspect(1 / math.cos(math.radians(float(G.nodes[ruta[0]]["y"]))))
    ax.axis("off")
    ax.set_title("MADRID  /  PLANIFICADOR DE RUTAS", color="#f8fafc", loc="left", fontsize=20, pad=20, weight="bold")
    legend = ax.legend(handles=leyenda, loc="lower left", facecolor="#0f172a", edgecolor="#475569", labelcolor="#f8fafc", fontsize=10)
    legend.set_zorder(20)
    fig.text(0.08, 0.035, "Dijkstra propio · estimaciones sin tráfico real | © OpenStreetMap contributors · ODbL\nhttps://www.openstreetmap.org/copyright", color="#94a3b8", fontsize=9)
    fig.subplots_adjust(left=0.06, right=0.96, top=0.9, bottom=0.11)
    if archivo:
        archivo = Path(archivo)
        archivo.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(archivo, dpi=160, facecolor=fig.get_facecolor())
    if mostrar:
        plt.show()
    plt.close(fig)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Planificador académico de rutas de Madrid con Dijkstra.")
    parser.add_argument("--demo", action="store_true", help="Usa el recorte incluido y direcciones predeterminadas, sin red.")
    parser.add_argument("--origin", help="Dirección de origen: 'Calle de Alberto Aguilera, 23'.")
    parser.add_argument("--destination", help="Dirección de destino.")
    parser.add_argument("--mode", choices=[*MODOS, "compare"], default="distance")
    parser.add_argument("--data-dir", type=Path, help="Carpeta que contiene direcciones.csv y madrid.graphml.")
    parser.add_argument("--download-map", action="store_true", help="Descarga Madrid si no existe el grafo local; requiere conexión.")
    parser.add_argument("--save-map", type=Path)
    parser.add_argument("--no-show", action="store_true", help="Ejecuta sin abrir una ventana gráfica.")
    args = parser.parse_args(argv)
    if args.demo and args.download_map:
        parser.error("La demo usa datos incluidos: no combine --demo y --download-map.")
    carpeta = args.data_dir or (ROOT / "data" / "demo" if args.demo else ROOT / "data")
    origen_texto = args.origin or ("Calle de Alberto Aguilera, 23" if args.demo else None)
    destino_texto = args.destination or ("Calle de Alcala, 23" if args.demo else None)
    try:
        if not origen_texto:
            origen_texto = input("Dirección de origen (Enter para salir): ").strip()
            if not origen_texto:
                return 0
        if not destino_texto:
            destino_texto = input("Dirección de destino (Enter para salir): ").strip()
            if not destino_texto:
                return 0
        callejero = carga_callejero(carpeta / "direcciones.csv")
        G = carga_grafo(carpeta / "madrid.graphml", descargar=args.download_map)
        origen_coords = busca_direccion(origen_texto, callejero)
        destino_coords = busca_direccion(destino_texto, callejero)
        # No asociamos silenciosamente una dirección exterior al recorte de la demo.
        xs = [float(d["x"]) for _, d in G.nodes(data=True)]
        ys = [float(d["y"]) for _, d in G.nodes(data=True)]
        for lat, lon in [origen_coords, destino_coords]:
            if not (min(xs) <= lon <= max(xs) and min(ys) <= lat <= max(ys)):
                raise ValueError("La dirección queda fuera del área del mapa cargado.")
        origen = encuentra_nodo_mas_cercano(G, *origen_coords)
        destino = encuentra_nodo_mas_cercano(G, *destino_coords)
        resultados = {}
        modos = MODOS if args.mode == "compare" else [args.mode]
        print(f"{origen_texto} -> {destino_texto}\n")
        for modo in modos:
            grafo = prepara_grafo(G, modo)
            ruta = camino_minimo(grafo, origen, destino, lambda g, u, v: g[u][v]["route_cost"])
            resultados[modo] = grafo, ruta
            resumen = resumen_ruta(grafo, ruta)
            print(f"{MODOS[modo]}: {resumen['distance_m'] / 1000:.2f} km; {resumen['time_s'] / 60:.1f} min de circulación")
            if modo == "signals":
                print(f"  Con espera: {resumen['expected_time_s'] / 60:.1f} min; {resumen['signals']} nodos con semáforo detectados.")
            for instruccion in genera_instrucciones(grafo, ruta):
                print(f"  - {instruccion}")
            print()
        if args.save_map or not args.no_show:
            resalta_rutas(resultados, args.save_map, mostrar=not args.no_show)
        return 0
    except (AddressNotFoundError, ServiceNotAvailableError, FileNotFoundError, ValueError, nx.NetworkXException, EOFError) as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
