"""
EN02 — Graph-Based Source Attribution
======================================
Implements a graph-based attribution module for identifying the most likely
emission source from a detected plume.

Architecture: "GNN-ready" — adjacency and scoring logic mirrors what a
Graph Neural Network would learn, but uses deterministic heuristics now.

Flow:
  1. Build facility graph (nodes = plants, edges = spatial proximity)
  2. Compute plume centroid in geo-space
  3. Score each candidate by: distance + wind alignment + facility type weight
  4. Return top-1..3 sources with confidence scores

Label: "Graph-based attribution (GNN-ready architecture)"

Extension path:
  - Replace score() with a GNN forward pass (PyTorch Geometric)
  - Node features: facility type, historical emissions, capacity
  - Edge features: distance, wind correlation, terrain
  - Train on labelled plume-source pairs
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ── Facility type emission probability priors ─────────────────────────────────
FACILITY_PRIOR = {
    "Oil Refinery":   0.85,
    "Natural Gas":    0.90,
    "Pipeline":       0.70,
    "Landfill":       0.65,
    "Mining":         0.60,
    "Petrochemical":  0.82,
    "Unknown":        0.50,
}


@dataclass
class FacilityNode:
    """Graph node representing a monitored facility."""
    id:          str
    name:        str
    lat:         float
    lon:         float
    ftype:       str
    # GNN-extensible feature vector (populated at runtime)
    features:    Dict[str, float] = field(default_factory=dict)


@dataclass
class PlumeObservation:
    """Observed plume — centroid in geo-coordinates."""
    centroid_lat:   float
    centroid_lon:   float
    area_m2:        float
    intensity:      float       # 0–1 concentration proxy
    wind_speed_ms:  float = 5.0
    wind_dir_deg:   float = 270.0   # degrees from N


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    R   = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ  = math.radians(lat2 - lat1)
    dλ  = math.radians(lon2 - lon1)
    a   = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _bearing_deg(lat1, lon1, lat2, lon2) -> float:
    """Forward bearing from point 1 → point 2 in degrees [0–360]."""
    dlon  = math.radians(lon2 - lon1)
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    x     = math.sin(dlon) * math.cos(φ2)
    y     = math.cos(φ1)*math.sin(φ2) - math.sin(φ1)*math.cos(φ2)*math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _wind_alignment_score(
    plume: PlumeObservation,
    facility: FacilityNode,
) -> float:
    """
    Wind alignment: how well does the wind vector point from facility to plume?
    Score = cos(angle between wind direction and plume-facility bearing).
    Range: [-1, 1] → normalised to [0, 1].
    """
    # Bearing from facility to plume centroid
    bearing = _bearing_deg(facility.lat, facility.lon, plume.centroid_lat, plume.centroid_lon)
    # Wind direction: meteorological convention (direction wind is coming FROM)
    # Downwind direction = wind_dir_deg + 180
    downwind = (plume.wind_dir_deg + 180) % 360
    delta    = abs(bearing - downwind) % 360
    if delta > 180: delta = 360 - delta
    return (math.cos(math.radians(delta)) + 1) / 2   # normalise to [0, 1]


def build_facility_graph(
    facilities: List[Dict[str, Any]],
    proximity_km: float = 150.0,
) -> Tuple[List[FacilityNode], Dict[str, List[str]]]:
    """
    Build adjacency graph: nodes = facilities, edges = proximity within threshold.
    Returns:
        nodes     : list of FacilityNode objects
        adjacency : {facility_id: [neighbour_id, ...]}
    """
    nodes = [
        FacilityNode(
            id=f["id"], name=f["name"], lat=f["lat"], lon=f["lon"],
            ftype=f.get("type", "Unknown"),
        )
        for f in facilities
    ]
    adjacency: Dict[str, List[str]] = {n.id: [] for n in nodes}
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            if i >= j: continue
            d = _haversine_km(a.lat, a.lon, b.lat, b.lon)
            if d <= proximity_km:
                adjacency[a.id].append(b.id)
                adjacency[b.id].append(a.id)
    return nodes, adjacency


def score_facility(
    facility: FacilityNode,
    plume: PlumeObservation,
    adjacency: Dict[str, List[str]],
    max_distance_km: float = 500.0,
    dist_weight: float = 0.40,
    wind_weight: float = 0.35,
    prior_weight: float = 0.15,
    cluster_weight: float = 0.10,
) -> float:
    """
    Compute attribution score for one facility.

    Score components:
      - Distance score:     closer → higher (exponential decay)
      - Wind alignment:     facility upwind of plume → higher
      - Type prior:         emission probability for facility type
      - Cluster bonus:      facility with many connected neighbours gets slight boost
                           (simulates GNN neighbourhood aggregation)

    All weights sum to 1.0.
    """
    # Distance score (exponential decay)
    d_km          = _haversine_km(facility.lat, facility.lon, plume.centroid_lat, plume.centroid_lon)
    dist_score    = math.exp(-d_km / (max_distance_km * 0.4))

    # Wind alignment
    wind_score    = _wind_alignment_score(plume, facility)

    # Type prior
    prior         = FACILITY_PRIOR.get(facility.ftype, 0.5)

    # Cluster bonus (GNN neighbourhood aggregation proxy)
    n_neighbours  = len(adjacency.get(facility.id, []))
    cluster_score = min(n_neighbours / 5.0, 1.0)

    total = (dist_weight   * dist_score
           + wind_weight   * wind_score
           + prior_weight  * prior
           + cluster_weight * cluster_score)

    # Store for explainability
    facility.features = {
        "distance_km":    round(d_km, 2),
        "dist_score":     round(dist_score, 3),
        "wind_score":     round(wind_score, 3),
        "type_prior":     prior,
        "cluster_score":  round(cluster_score, 3),
        "total":          round(total, 4),
    }
    return total


def graph_attribution(
    plume: PlumeObservation,
    facilities: List[Dict[str, Any]],
    top_k: int = 3,
    proximity_km: float = 150.0,
) -> Dict[str, Any]:
    """
    Main attribution function.

    Parameters
    ----------
    plume       : PlumeObservation with centroid + atmospheric state.
    facilities  : List of facility dicts (id, name, lat, lon, type).
    top_k       : Number of top candidates to return.
    proximity_km: Graph edge threshold.

    Returns
    -------
    Dict with top candidates, attribution confidence, and graph metadata.
    """
    if not facilities:
        return {"top_candidates": [], "confidence": 0.0, "method": "graph-attribution (GNN-ready)"}

    nodes, adjacency = build_facility_graph(facilities, proximity_km=proximity_km)

    scored: List[Tuple[float, FacilityNode]] = []
    for node in nodes:
        s = score_facility(node, plume, adjacency)
        scored.append((s, node))

    scored.sort(key=lambda x: x[0], reverse=True)
    top    = scored[:top_k]

    # Softmax-normalise scores → attribution probabilities
    total_score = sum(s for s, _ in top) or 1e-9
    candidates  = []
    for rank, (score, node) in enumerate(top):
        conf_pct = round((score / total_score) * 100, 1)
        candidates.append({
            "rank":        rank + 1,
            "plant_id":    node.id,
            "plant_name":  node.name,
            "plant_type":  node.ftype,
            "lat":         node.lat,
            "lon":         node.lon,
            "score":       round(score, 4),
            "confidence":  conf_pct,
            "details":     node.features,
            "neighbours":  adjacency.get(node.id, []),
        })

    # Overall confidence = margin between top-1 and top-2 score
    margin = (scored[0][0] - scored[1][0]) if len(scored) > 1 else scored[0][0]
    overall_conf = round(min(50 + margin * 300, 98.0), 1)

    return {
        "top_candidates":    candidates,
        "primary_source":    candidates[0] if candidates else None,
        "overall_confidence": overall_conf,
        "graph_nodes":        len(nodes),
        "graph_edges":        sum(len(v) for v in adjacency.values()) // 2,
        "proximity_km":       proximity_km,
        "attribution_method": "Graph-based attribution (GNN-ready architecture)",
        "note": (
            "Score components: distance decay + wind alignment + facility type prior "
            "+ neighbourhood clustering. Mirrors GNN message-passing aggregation."
        ),
    }


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    from ai.pipelines.pipeline_manager_v2 import PLANT_DB

    plume = PlumeObservation(
        centroid_lat=19.2, centroid_lon=73.0,
        area_m2=18_000, intensity=0.65,
        wind_speed_ms=5.0, wind_dir_deg=270.0,
    )
    result = graph_attribution(plume, PLANT_DB, top_k=3)
    print(json.dumps(result, indent=2))
