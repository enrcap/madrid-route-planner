"""Carga de direcciones y redes viarias de Madrid.

Proyecto de Matemática Discreta (IMAT, ICAI): Enrique Capella.
"""

from pathlib import Path
import re
import unicodedata

import networkx as nx
import pandas as pd

ROOT = Path(__file__).resolve().parent
STREET_FILE_NAME = ROOT / "data" / "direcciones.csv"
MAP_FILE_NAME = ROOT / "data" / "madrid.graphml"
PLACE_NAME = "Madrid, Spain"
MAX_SPEEDS = {
    "living_street": 20, "residential": 30, "primary_link": 40,
    "unclassified": 40, "secondary_link": 40, "trunk_link": 40,
    "secondary": 50, "tertiary": 50, "primary": 50, "trunk": 50,
    "tertiary_link": 50, "busway": 50, "motorway_link": 70, "motorway": 100,
}


class ServiceNotAvailableError(RuntimeError):
    """No se pudo recuperar la red viaria."""


class AddressNotFoundError(ValueError):
    """Dirección ausente, ambigua o con formato inválido."""


# Compatibilidad con el nombre del proyecto académico original.
AdressNotFoundError = AddressNotFoundError


def normaliza(texto: str) -> str:
    """Normaliza mayúsculas, espacios y acentos sin búsquedas parciales."""
    texto = unicodedata.normalize("NFKD", str(texto))
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).casefold().split())


def dms_to_decimal(coordenada: str) -> float:
    """Convierte grados, minutos, segundos y hemisferio (N/S/E/W/O)."""
    match = re.fullmatch(
        r"\s*(\d+(?:[.,]\d+)?)\s*°\s*(\d+(?:[.,]\d+)?)\s*['′]\s*"
        r"(\d+(?:[.,]\d+)?)\s*(?:[\"″]|'{2}|′{2})\s*([NSEWO])\s*", str(coordenada), re.I,
    )
    if not match:
        raise ValueError(f"Coordenada DMS inválida: {coordenada!r}")
    grados, minutos, segundos = (float(v.replace(",", ".")) for v in match.groups()[:3])
    direccion = match[4].upper()
    limite = 90 if direccion in "NS" else 180
    if minutos >= 60 or segundos >= 60 or grados + minutos / 60 + segundos / 3600 > limite:
        raise ValueError(f"Coordenada fuera de rango: {coordenada!r}")
    decimal = grados + minutos / 60 + segundos / 3600
    return -decimal if direccion in "SWO" else decimal


def carga_callejero(ruta: str | Path = STREET_FILE_NAME) -> pd.DataFrame:
    """Lee solo las columnas necesarias del CSV municipal y prepara el índice."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe {ruta}. Consulta data/README.md para obtener los datos.")
    columnas = {
        "VIA_CLASE": "clase_via", "VIA_PAR": "particula_via",
        "VIA_NOMBRE": "nombre_via", "NUMERO": "numero",
        "LATITUD": "latitud", "LONGITUD": "longitud",
    }
    df = pd.read_csv(ruta, sep=";", encoding="latin1", usecols=list(columnas)).rename(columns=columnas)
    df["numero"] = pd.to_numeric(df["numero"], errors="raise")
    for columna in ("latitud", "longitud"):
        df[columna] = df[columna].map(dms_to_decimal)
    df["nombre_completo"] = (
        df["clase_via"].fillna("") + " " + df["particula_via"].fillna("") + " " + df["nombre_via"].fillna("")
    ).map(normaliza)
    return df


def busca_direccion(direccion: str, callejero: pd.DataFrame) -> tuple[float, float]:
    """Busca una dirección completa, tolerando acentos y espacios.

    Ejemplo: 'Calle de Alberto Aguilera, 23'. Ante varios portales con
    coordenadas diferentes se pide desambiguación en vez de elegir uno al azar.
    """
    match = re.fullmatch(r"\s*(.+?)\s*,\s*(\d+)\s*", direccion)
    if not match:
        raise AddressNotFoundError("Use el formato 'Calle de Alberto Aguilera, 23'.")
    nombre, numero = normaliza(match[1]), int(match[2])
    coincidencias = callejero.loc[
        (callejero["nombre_completo"] == nombre) & (callejero["numero"] == numero),
        ["latitud", "longitud"],
    ].drop_duplicates()
    if coincidencias.empty:
        raise AddressNotFoundError(f"No se encontró la dirección: {direccion}")
    if len(coincidencias) > 1:
        raise AddressNotFoundError(f"Dirección ambigua: {direccion}. Use otra dirección o coordenadas.")
    return tuple(float(v) for v in coincidencias.iloc[0])


def carga_grafo(ruta: str | Path = MAP_FILE_NAME, descargar: bool = False) -> nx.MultiDiGraph:
    """Carga un GraphML local; solo descarga Madrid si se solicita explícitamente."""
    import osmnx as ox

    ruta = Path(ruta)
    try:
        if ruta.is_file():
            return ox.load_graphml(ruta)
        if not descargar:
            raise FileNotFoundError(f"No existe {ruta}. Use --download-map o consulte data/README.md.")
        ox.settings.cache_folder = str(ROOT / "cache")
        grafo = ox.graph_from_place(PLACE_NAME, network_type="drive")
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(grafo, ruta)
        return grafo
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise ServiceNotAvailableError(f"No se pudo cargar la red viaria: {exc}") from exc


def procesa_grafo(multidigrafo: nx.MultiDiGraph, peso=None) -> nx.DiGraph:
    """Elimina bucles y selecciona la mejor arista paralela para el coste elegido.

    Conserva metadatos, geometría y clave original de cada arista seleccionada.
    El grafo debe procesarse de nuevo cuando cambia el criterio de optimización.
    """
    if peso is None:
        peso = lambda datos: float(datos["length"])
    grafo = nx.DiGraph(**multidigrafo.graph)
    grafo.add_nodes_from(multidigrafo.nodes(data=True))
    for u, v, key, datos in multidigrafo.edges(keys=True, data=True):
        if u == v:
            continue
        coste = float(peso(datos))
        if not grafo.has_edge(u, v) or coste < grafo[u][v]["route_cost"]:
            grafo.add_edge(u, v, **{**datos, "route_cost": coste, "original_key": key})
    return grafo
