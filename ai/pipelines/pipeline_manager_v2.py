"""
EN02 — Pipeline Manager v2
===========================
Drop-in upgrade over pipeline_manager.py (v1).

What changed vs v1 (additive only — no deletions):
  • InsightAgent._process()   → now calls physics_emission() for emission model
  • AttributionAgent._process() → now calls graph_attribution() for top-3 candidates
  • _build_response()         → exposes new fields (alert, alert_type, priority,
                                uncertainty_note, graph_attribution, physics_details)
  • PipelineContext           → two new optional fields (graph_result, physics_result)
  • ALERT_THRESHOLD           → configurable via config.py or env var

All original field names in the API response are preserved unchanged.
"""

from __future__ import annotations
import base64, math, random, time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import cv2

# ── EN02 module imports ───────────────────────────────────────────────────────
from ai.config import (
    WIND_SPEED, PIXEL_AREA, METHANE_GWP, GAS_PRICE_USD_PER_KG,
    MODEL_THRESHOLD, IMG_SIZE, SEV_LOW, SEV_MODERATE, SEV_HIGH,
    WIND_ALIGN_WEIGHT, DIST_WEIGHT,
)
from ai.models.satellite_adapter import (
    fetch_sentinel_data, preprocess_bands, compute_swir_ratio,
    generate_pseudo_labels, hybrid_detection,
)
from ai.models.false_positive_filter import filter_false_positives
from ai.utils.temporal_analysis import analyze_time_series, append_emission
from ai.utils.logger import get_logger

# Live data + inference extensions (additive)
from ai.models.inference_model import model_available, model_loaded, predict_plume, predict_plume_prob, torch_available
from ai.data.sentinel2_fetcher import fetch_sentinel2_image
from ai.data.emit_fetcher import emit_availability, fetch_emit_hyperspectral
from ai.models.inversion_pipeline import invert_emission, ime_emission

# ── New v2 modules ────────────────────────────────────────────────────────────
from ai.models.physics_module import physics_emission, severity_from_emission
from ai.models.graph_attribution import graph_attribution, PlumeObservation

logger = get_logger("en02.pipeline.v2")

# ── Alert threshold (kg/hr) ───────────────────────────────────────────────────
import os
ALERT_THRESHOLD = float(os.getenv("EN02_ALERT_THRESHOLD", "300"))

# ── Plant database ────────────────────────────────────────────────────────────
PLANT_DB: List[Dict[str, Any]] = [
    {"id": "P-01", "name": "Refinery Alpha",       "lat": 28.6139, "lon": 77.2090, "type": "Oil Refinery", "country": "India", "operator": "Alpha Corp", "intensity": 0.8},
    {"id": "P-02", "name": "Gas Plant Beta",        "lat": 19.0760, "lon": 72.8777, "type": "Natural Gas", "country": "India", "operator": "Beta Gas", "intensity": 0.6},
    {"id": "P-03", "name": "Compressor Station C",  "lat": 12.9716, "lon": 77.5946, "type": "Pipeline", "country": "India", "operator": "Pipeline Co", "intensity": 0.4},
    {"id": "P-04", "name": "Landfill Site D",       "lat": 22.5726, "lon": 88.3639, "type": "Landfill", "country": "India", "operator": "Waste Mgmt", "intensity": 0.5},
    {"id": "P-05", "name": "Coal Mine E",           "lat": 23.6102, "lon": 85.2799, "type": "Mining", "country": "India", "operator": "Coal India", "intensity": 0.7},
    {"id": "P-06", "name": "Petrochemical Hub F",   "lat": 21.1702, "lon": 72.8311, "type": "Petrochemical", "country": "India", "operator": "Petro Hub", "intensity": 0.9},

]


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE CONTEXT — extended with v2 result fields
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PipelineContext:
    raw_image:        Optional[np.ndarray]  = None
    lat:              float                 = 0.0
    lon:              float                 = 0.0
    emission_history: List[float]           = field(default_factory=list)

    bands:            Dict[str, np.ndarray] = field(default_factory=dict)
    cleaned_bands:    Dict[str, np.ndarray] = field(default_factory=dict)
    swir_ratio:       Optional[np.ndarray]  = None
    ch4_band:         Optional[np.ndarray]  = None
    prob_map:         Optional[np.ndarray]  = None
    raw_mask:         Optional[np.ndarray]  = None
    final_mask:       Optional[np.ndarray]  = None
    fp_report:        Dict[str, Any]        = field(default_factory=dict)
    plume_mask:       Optional[np.ndarray]  = None

    emission:         Dict[str, Any]        = field(default_factory=dict)
    source:           Dict[str, Any]        = field(default_factory=dict)
    insights:         Dict[str, Any]        = field(default_factory=dict)
    temporal:         Dict[str, Any]        = field(default_factory=dict)

    # ── v2 additions ─────────────────────────────────────────────────────────
    graph_result:     Dict[str, Any]        = field(default_factory=dict)
    physics_result:   Dict[str, Any]        = field(default_factory=dict)

    agent_timings:    Dict[str, float]      = field(default_factory=dict)
    data_source:      str                   = "unknown"
    errors:           List[str]             = field(default_factory=list)
    model:            Any                   = None
    device:           str                   = "cpu"


# ─────────────────────────────────────────────────────────────────────────────
# BASE AGENT
# ─────────────────────────────────────────────────────────────────────────────

class _Agent:
    name: str = "BaseAgent"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        t0 = time.perf_counter()
        try:
            ctx = self._process(ctx)
        except Exception as exc:
            ctx.errors.append(f"{self.name}: {exc}")
            logger.warning("%s failed: %s", self.name, exc)
        ctx.agent_timings[self.name] = round((time.perf_counter() - t0) * 1000, 1)
        return ctx

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# AGENTS  (DataAgent / PreprocessingAgent / SpectralAgent / DetectionAgent /
#          PostProcessingAgent unchanged from v1 — included here for completeness)
# ─────────────────────────────────────────────────────────────────────────────

class DataAgent(_Agent):
    name = "DataAgent"

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.raw_image is not None:
            ctx.data_source = "upload"
            gray = cv2.cvtColor(cv2.resize(ctx.raw_image, (IMG_SIZE, IMG_SIZE)), cv2.COLOR_BGR2GRAY)
            ctx.bands = {
                "B04": gray,
                "B08": np.clip(gray.astype(np.int16) + 10, 0, 255).astype(np.uint8),
                "B11": np.clip(gray.astype(np.int16) - 5,  0, 255).astype(np.uint8),
                "B12": np.clip(gray.astype(np.int16) + 5,  0, 255).astype(np.uint8),
                "rgb": cv2.resize(ctx.raw_image, (IMG_SIZE, IMG_SIZE)),
                "swir_ratio": compute_swir_ratio(gray, gray),
            }
        else:
            ctx.data_source = "api_or_stub"
            ctx.bands = fetch_sentinel_data(ctx.lat, ctx.lon)
        return ctx


class PreprocessingAgent(_Agent):
    name = "PreprocessingAgent"

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        ctx.cleaned_bands = preprocess_bands(ctx.bands)
        if ctx.raw_image is not None:
            ctx.raw_image = cv2.fastNlMeansDenoisingColored(
                cv2.resize(ctx.raw_image, (IMG_SIZE, IMG_SIZE)), None, 3, 3, 5, 15,
            )
        return ctx


class SpectralAgent(_Agent):
    name = "SpectralAgent"

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        ctx.swir_ratio = compute_swir_ratio(ctx.cleaned_bands["B11"], ctx.cleaned_bands["B12"])
        nir  = ctx.cleaned_bands["B08"].astype(np.float32)
        attn = ctx.swir_ratio.astype(np.float32) / 255.0
        ctx.ch4_band = np.clip(nir - attn * 65, 0, 255).astype(np.uint8)
        return ctx


class DetectionAgent(_Agent):
    name = "DetectionAgent"

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        import torch
        if ctx.model is not None:
            gray = ctx.cleaned_bands["B04"].astype(np.float32) / 255.0
            t_in = torch.from_numpy(gray).unsqueeze(0).unsqueeze(0).to(ctx.device)
            with torch.no_grad():
                ctx.prob_map = ctx.model(t_in).squeeze().cpu().numpy()
        else:
            ctx.prob_map = _synthetic_prob_map()
        ctx.raw_mask = hybrid_detection(ctx.prob_map, ctx.swir_ratio)
        return ctx


class PostProcessingAgent(_Agent):
    name = "PostProcessingAgent"

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.ch4_band is None or ctx.raw_mask is None:
            ctx.final_mask = ctx.raw_mask
            return ctx
        ctx.final_mask, ctx.fp_report = filter_false_positives(ctx.raw_mask, ctx.ch4_band)
        return ctx


# ─────────────────────────────────────────────────────────────────────────────
# AttributionAgent v2 — uses graph_attribution
# ─────────────────────────────────────────────────────────────────────────────

class AttributionAgent(_Agent):
    """
    v2: replaces simple distance+wind with full graph_attribution() call.
    Returns top-3 candidate sources + graph metadata.
    Falls back to v1 heuristic if graph_attribution raises.
    """
    name = "AttributionAgent"

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        mask = ctx.final_mask if ctx.final_mask is not None else ctx.raw_mask
        if mask is None or not np.any(mask > 0):
            ctx.source = {"plant": None, "confidence": 0.0,
                          "attribution_method": "graph-attribution (GNN-ready)"}
            return ctx

        # Derive plume centroid in pixel coords → approximate geo
        m  = cv2.moments(mask)
        cx = int(m["m10"] / m["m00"]) if m["m00"] else IMG_SIZE // 2
        cy = int(m["m01"] / m["m00"]) if m["m00"] else IMG_SIZE // 2

        # Map pixel centroid to plausible geographic offset around request coords
        lat_off = (cy - IMG_SIZE / 2) * 0.0003
        lon_off = (cx - IMG_SIZE / 2) * 0.0004
        plume = PlumeObservation(
            centroid_lat  = ctx.lat  + lat_off,
            centroid_lon  = ctx.lon  + lon_off,
            area_m2       = float(np.sum(mask > 0)) * PIXEL_AREA,
            intensity     = float(np.mean(ctx.swir_ratio) / 255.0) if ctx.swir_ratio is not None else 0.5,
            wind_speed_ms = WIND_SPEED,
            wind_dir_deg  = 270.0,   # westerly default; replace with ERA5 in production
        )

        graph_res = graph_attribution(plume, PLANT_DB, top_k=3)
        ctx.graph_result = graph_res

        primary = graph_res.get("primary_source")
        if primary:
            # Find the full plant dict for backward compatibility
            plant_dict = next((p for p in PLANT_DB if p["id"] == primary["plant_id"]), None)
            ctx.source = {
                "plant":              plant_dict,
                "confidence":         primary["confidence"],
                "attribution_method": graph_res["attribution_method"],
                "top_candidates":     graph_res["top_candidates"],
                "graph_nodes":        graph_res["graph_nodes"],
                "graph_edges":        graph_res["graph_edges"],
            }
        else:
            ctx.source = {"plant": None, "confidence": 0.0,
                          "attribution_method": "graph-attribution (GNN-ready)"}
        return ctx


# ─────────────────────────────────────────────────────────────────────────────
# InsightAgent v2 — uses physics_emission
# ─────────────────────────────────────────────────────────────────────────────

class InsightAgent(_Agent):
    """
    v2: replaces area×concentration×wind with physics_emission() (Pasquill-Gifford
    dispersion, spread factor, wind alignment, uncertainty band).
    All original output keys preserved.
    """
    name = "InsightAgent"

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        mask = ctx.final_mask if ctx.final_mask is not None else ctx.raw_mask
        methane_detected = mask is not None and bool(np.any(mask > 0))

        if not methane_detected:
            ctx.emission = _zero_emission()
            ctx.insights = {
                "methane_detected": False, "risk_score": 0.0,
                "confidence": 0.0, "uncertainty": 0.0,
                "impact": {"co2_equivalent_kghr": 0.0, "financial_loss_usd_hr": 0.0, "annual_co2_tonnes": 0.0},
                "recommendation": "No methane detected. Continue scheduled monitoring.",
            }
            return ctx

        # ── Physics-informed emission ─────────────────────────────────────────
        plume_area = float(np.sum(mask > 0)) * PIXEL_AREA
        conc_proxy = float(np.mean(ctx.swir_ratio) / 255.0) if ctx.swir_ratio is not None else 0.4

        phys = physics_emission(
            plume_area_m2       = plume_area,
            concentration_proxy = conc_proxy,
            wind_speed_ms       = WIND_SPEED,
            wind_direction_deg  = 270.0,
            pixel_area_m2       = PIXEL_AREA,
            gwp_factor          = METHANE_GWP,
            gas_price_usd_per_kg= GAS_PRICE_USD_PER_KG,
        )
        ctx.physics_result = phys

        emission_kghr = phys["emission_kghr"]
        severity      = severity_from_emission(emission_kghr)
        co2_eq        = phys["co2_equivalent_kghr"]
        fin_loss      = phys["financial_loss_usd_hr"]

        # ── Uncertainty from model variance + physics band ────────────────────
        prob_var     = float(np.var(ctx.prob_map)) if ctx.prob_map is not None else 0.1
        uncertainty  = round(min(phys["uncertainty_band"]["pct"] + prob_var * 100, 35.0), 1)
        confidence   = round(max(100 - uncertainty - random.uniform(0, 5), 50.0), 1)
        coverage_pct = round(100 * np.sum(mask > 0) / (IMG_SIZE * IMG_SIZE), 2)

        ctx.emission = {
            "emission_kghr":         emission_kghr,
            "plume_area_m2":         round(plume_area, 1),
            "coverage_pct":          coverage_pct,
            "severity":              severity,
            "co2_equivalent_kghr":   co2_eq,
            "financial_loss_usd_hr": fin_loss,
            # v2 extras
            "uncertainty_band":      phys["uncertainty_band"],
            "spread_factor":         phys["spread_factor"],
            "stability_class":       phys["stability_class"],
            "model_label":           phys["model_label"],
        }

        risk_score = round(min(100, 20 + emission_kghr / 7), 1)
        annual_co2 = round(co2_eq * 8760 / 1000, 1)

        plant_type = ctx.source.get("plant", {}).get("type", "facility") if ctx.source else "facility"
        ctx.insights = {
            "methane_detected": True,
            "risk_score":       risk_score,
            "confidence":       confidence,
            "uncertainty":      uncertainty,
            "uncertainty_note": (
                f"Based on model variance ({round(prob_var*100,1)}%) + "
                f"physics dispersion uncertainty ({phys['uncertainty_band']['pct']}%)"
            ),
            "impact": {
                "co2_equivalent_kghr":   co2_eq,
                "financial_loss_usd_hr": fin_loss,
                "annual_co2_tonnes":     annual_co2,
            },
            "recommendation": _recommendation(severity, plant_type),
        }
        return ctx


# ─────────────────────────────────────────────────────────────────────────────
# TemporalAgent (unchanged from v1)
# ─────────────────────────────────────────────────────────────────────────────

class TemporalAgent(_Agent):
    name = "TemporalAgent"

    def __init__(self, history_store: Dict[str, list]):
        self._store = history_store

    def _process(self, ctx: PipelineContext) -> PipelineContext:
        plant_id = (ctx.source.get("plant") or {}).get("id", "unknown")
        e        = ctx.emission.get("emission_kghr", 0.0)
        if e > 0:
            self._store[plant_id] = self._store.get(plant_id, []) + [e]
        history  = self._store.get(plant_id, ctx.emission_history + ([e] if e > 0 else []))
        ctx.temporal = analyze_time_series(history)
        return ctx


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE ORCHESTRATOR v2
# ─────────────────────────────────────────────────────────────────────────────

class PipelineManager:
    def __init__(self, model=None, device: str = "cpu"):
        self._model   = model
        self._device  = device
        self._history: Dict[str, list] = {}

        temporal_agent = TemporalAgent(self._history)
        self._agents: List[_Agent] = [
            DataAgent(),
            PreprocessingAgent(),
            SpectralAgent(),
            DetectionAgent(),
            PostProcessingAgent(),
            AttributionAgent(),    # v2 — graph-based
            InsightAgent(),        # v2 — physics-based
            temporal_agent,
        ]

    def run_pipeline(self,
                     raw_image: Optional[np.ndarray] = None,
                     lat: float = 19.076, lon: float = 72.877,
                     emission_history: Optional[List[float]] = None) -> Dict[str, Any]:
        t_start = time.perf_counter()
        ctx = PipelineContext(
            raw_image=raw_image, lat=lat, lon=lon,
            emission_history=emission_history or [],
            model=self._model, device=self._device,
        )
        for agent in self._agents:
            ctx = agent.run(ctx)
        total_ms = round((time.perf_counter() - t_start) * 1000, 1)
        return self._build_response(ctx, total_ms)

    def run_live_pipeline(
        self,
        lat: float,
        lon: float,
        wind_speed_ms: Optional[float] = None,
        radius_km: Optional[float] = None,
        prefer_emit: Optional[bool] = None,
        mask_mode: Optional[str] = None,
        require_live_satellite: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Live pipeline:
          1) Fetch Sentinel-5P CH4
          2) Early exit if no anomaly
          3) Load AVIRIS sample or fallback tile
          4) Run model inference + false-positive filter
          5) Physics emission + graph attribution
        """
        t_start = time.perf_counter()
        ctx = PipelineContext(lat=lat, lon=lon, model=self._model, device=self._device)
        # Optional EMIT hyperspectral path (fallback to Sentinel-2 by default)
        env_emit = os.getenv("ENABLE_EMIT", "0") == "1"
        if prefer_emit is None:
            use_emit = env_emit
        else:
            use_emit = bool(prefer_emit)
        emit_status: Dict[str, Any] = {"available": False}

        bands = None
        last_exc = None
        image_source = "Sentinel-2 L2A"

        if use_emit:
            try:
                emit_status = emit_availability(lat, lon, radius_km=radius_km or 5.0)
                if emit_status.get("available"):
                    bands = fetch_emit_hyperspectral(
                        lat,
                        lon,
                        size=IMG_SIZE,
                        radius_km=radius_km or 5.0,
                    )
                    image_source = "EMIT L2A"
            except Exception as exc:
                emit_status["error"] = str(exc)
                bands = None

        # Fetch real Sentinel-2 L2A bands if EMIT unavailable and live satellite is strictly required
        if bands is None and require_live_satellite:
            base_radius = float(radius_km) if radius_km is not None else 5.0
            radius_candidates = [base_radius, base_radius * 2.0, base_radius * 3.0]
            for rk in radius_candidates:
                try:
                    bands = fetch_sentinel2_image(lat, lon, size=IMG_SIZE, radius_km=rk)
                    image_source = "Sentinel-2 L2A"
                    break
                except Exception as exc:
                    last_exc = exc
        if bands is None:
            if bool(require_live_satellite):
                total_ms = round((time.perf_counter() - t_start) * 1000, 1)
                return {
                    "error": "Live satellite data unavailable",
                    "details": str(last_exc) if last_exc else "No Sentinel-2 tiles returned.",
                    "plume_detected": False,
                    "image_source": "none",
                    "processing_time_ms": total_ms,
                    "pipeline_errors": ctx.errors,
                }

            # Fallback to deterministic synthetic bands so UI can still visualize output.
            bands = _fallback_live_bands(lat, lon, size=IMG_SIZE, radius_km=radius_km)
            image_source = "Synthetic fallback"
            if last_exc is not None:
                ctx.errors.append(f"LiveDataFallback: {last_exc}")

        rgb = bands["rgb"]
        b08 = bands["B08"]
        b11 = bands["B11"]
        b12 = bands["B12"]
        pixel_area_m2 = float(bands.get("pixel_area_m2", 400.0))
        bbox_vals = bands.get("bbox")
        radius_km = bands.get("radius_km", radius_km)
        swir_ratio = compute_swir_ratio((b11 * 255).astype(np.uint8), (b12 * 255).astype(np.uint8))
        wind_speed = float(wind_speed_ms) if wind_speed_ms is not None else WIND_SPEED

        # Model inference (required)
        inference_mode = "model"
        model_threshold_used = 0.5
        model_prob_stats = {"min": 0.0, "max": 0.0, "mean": 0.0}
        try:
            # Use SWIR/NIR composite for methane sensitivity
            model_rgb = np.stack([b12, b11, b08], axis=2)
            prob_map = predict_plume_prob(model_rgb)
            model_prob_stats = {
                "min": float(np.min(prob_map)),
                "max": float(np.max(prob_map)),
                "mean": float(np.mean(prob_map)),
            }
            model_mask = (prob_map >= model_threshold_used).astype(np.uint8) * 255
            model_pixels = int(np.sum(model_mask > 0))
            prob_max = float(model_prob_stats["max"])
            prob_mean = float(model_prob_stats["mean"])

            # Non-strict mode: adapt threshold when model is too conservative.
            if mask_mode != "strict" and model_pixels < 20:
                # Guardrail: if logits are nearly flat and low-confidence, do not force detections.
                if prob_max < 0.6 and (prob_max - prob_mean) < 0.08:
                    model_mask = np.zeros_like(model_mask)
                else:
                    # Use extreme tail to avoid turning near-uniform logits into full-scene masks.
                    adaptive_thr = float(np.clip(np.percentile(prob_map, 99.8), 0.35, 0.95))
                    if adaptive_thr <= float(np.max(prob_map)):
                        model_threshold_used = adaptive_thr
                        model_mask = (prob_map >= model_threshold_used).astype(np.uint8) * 255
        except Exception as exc:
            total_ms = round((time.perf_counter() - t_start) * 1000, 1)
            return {
                "error": "Model inference unavailable",
                "details": str(exc),
                "plume_detected": False,
                "processing_time_ms": total_ms,
                "pipeline_errors": ctx.errors,
            }

        # Concentration proxy from SWIR bands (NDMI-like)
        c_raw = (b12 - b11) / (b12 + b11 + 1e-6)
        c_min = float(np.min(c_raw))
        c_max = float(np.max(c_raw))
        c_norm = (c_raw - c_min) / max(c_max - c_min, 1e-6)
        c_noise = float(np.std(c_norm))

        # Plume mask: require SWIR signal + model agreement to reduce false positives
        scene_brightness = float(np.mean(rgb))
        swir_thresh = 0.6 + (scene_brightness - 0.35) * 0.2
        swir_thresh = float(np.clip(swir_thresh, 0.4, 0.75))
        swir_mask = (c_norm > swir_thresh).astype(np.uint8) * 255
        swir_pixels = int(np.sum(swir_mask > 0))
        raw_mask = cv2.bitwise_and(model_mask, swir_mask)
        raw_pixels = int(np.sum(raw_mask > 0)) if raw_mask is not None else 0

        # If the strict AND mask is empty, fall back to a percentile-based SWIR mask
        if mask_mode != "strict" and (raw_mask is None or raw_pixels == 0):
            try:
                # Relax fusion before abandoning model guidance.
                p_thresh = float(np.percentile(c_norm, 97))
                swir_relaxed = (c_norm > p_thresh).astype(np.uint8) * 255
                candidate = cv2.bitwise_and(model_mask, swir_relaxed)
                candidate_pixels = int(np.sum(candidate > 0))
                if candidate_pixels > 0:
                    raw_mask = candidate
                    swir_mask = swir_relaxed
                    swir_thresh = p_thresh
                else:
                    # Keep empty mask when model has no positive support.
                    raw_mask = np.zeros_like(model_mask)
            except Exception:
                pass

        # Guardrail: if relaxed logic yields an overly large mask, tighten to spectral tail.
        if mask_mode != "strict" and raw_mask is not None:
            max_pixels = int(IMG_SIZE * IMG_SIZE * 0.12)  # 12% of frame
            if int(np.sum(raw_mask > 0)) > max_pixels:
                high_tail = float(np.percentile(c_norm, 99.5))
                tight_swir = (c_norm > high_tail).astype(np.uint8) * 255
                if int(np.sum(model_mask > 0)) > 0:
                    raw_mask = cv2.bitwise_and(model_mask, tight_swir)
                else:
                    raw_mask = tight_swir
                swir_thresh = high_tail

        # Apply false-positive filter using a grayscale band proxy
        is_synthetic = (image_source == "Synthetic fallback")
        if is_synthetic:
            # Force the mask to capture the synthetic gaussian plume for demo purposes
            raw_mask = swir_mask
            gray_band = cv2.cvtColor((rgb * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY)
            final_mask = raw_mask
            fp_report = {"bypassed_for_synthetic": True}
        else:
            gray_band = cv2.cvtColor((rgb * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY)
            final_mask, fp_report = filter_false_positives(raw_mask, gray_band)
            # If filtering removes everything in non-strict mode, keep cleaned raw candidates.
            if (
                mask_mode != "strict"
                and raw_mask is not None
                and int(np.sum(raw_mask > 0)) > 0
                and (final_mask is None or int(np.sum(final_mask > 0)) == 0)
            ):
                kernel = np.ones((3, 3), np.uint8)
                final_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_OPEN, kernel)
                final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, kernel)
                if int(np.sum(final_mask > 0)) == 0:
                    final_mask = raw_mask
        ctx.plume_mask = final_mask
        ctx.fp_report = fp_report

        # Save mask (optional visualization)
        _save_mask_image(final_mask)
        _save_satellite_image(rgb)
        _save_swir_false_color(rgb, swir_ratio, final_mask)

        plume_pixels = int(np.sum(final_mask > 0)) if final_mask is not None else 0
        # If no plume pixels, return clean zero-result (avoid division by zero)
        if final_mask is None or plume_pixels == 0:
            # Detection-limit style upper-bound estimate for no-plume cases.
            det_area_m2 = float(120) * pixel_area_m2
            det_conc = float(np.clip(c_noise * 3.0, 0.01, 0.2))
            det_phys = physics_emission(
                plume_area_m2=det_area_m2,
                concentration_proxy=det_conc,
                wind_speed_ms=wind_speed,
                wind_direction_deg=90.0,
                pixel_area_m2=pixel_area_m2,
                gwp_factor=METHANE_GWP,
                gas_price_usd_per_kg=GAS_PRICE_USD_PER_KG,
            )
            det_upper = float(det_phys.get("emission_kghr", 0.0) or 0.0)
            quantification = {
                "available": True,
                "method": "no_signal",
                "emission_kghr": 0.0,
                "cost_loss_usd_per_hour": 0.0,
                "estimated_leak_upper_bound_kghr": round(det_upper, 4),
                "estimated_cost_upper_bound_usd_per_hour": round(det_upper * GAS_PRICE_USD_PER_KG, 2),
                "formulas": {
                    "ime": "Q (kg/s) = (U_eff / L) * IME ; Q (kg/hr) = Q (kg/s) * 3600",
                    "cost": "Cost_loss (USD/hr) = Emission_kg_hr * Gas_price_USD_per_kg",
                },
                "assumptions": {
                    "wind_speed_ms": wind_speed,
                    "pixel_area_m2": pixel_area_m2,
                    "gas_price_usd_per_kg": GAS_PRICE_USD_PER_KG,
                    "gwp_factor": METHANE_GWP,
                    "noise_std_c_norm": round(c_noise, 6),
                },
                "note": "No plume mask available from model+spectral fusion.",
            }

            total_ms = round((time.perf_counter() - t_start) * 1000, 1)
            return {
                "plume_detected": False,
                "emission_kghr": float(quantification.get("emission_kghr", 0.0)),
                "cost_loss_usd_per_hour": float(quantification.get("cost_loss_usd_per_hour", 0.0)),
                "source": "unknown",
                "confidence": 0.0,
                "image_source": image_source,
                "inference_mode": inference_mode,
                "model_available": model_available(),
                "model_loaded": model_loaded(),
                "torch_available": torch_available(),
                "inference_reliability": "medium" if model_loaded() else "low",
                "plume_pixels": plume_pixels,
                "model_pixels": int(np.sum(model_mask > 0)),
                "swir_pixels": swir_pixels,
                "raw_pixels": int(np.sum(raw_mask > 0)) if raw_mask is not None else 0,
                "model_threshold_used": round(float(model_threshold_used), 6),
                "model_probability_stats": {
                    "min": round(float(model_prob_stats["min"]), 6),
                    "max": round(float(model_prob_stats["max"]), 6),
                    "mean": round(float(model_prob_stats["mean"]), 6),
                },
                "quantification": quantification,
                "used_coordinates": {"lat": float(lat), "lon": float(lon)},
                "emit_status": emit_status,
                "processing_time_ms": total_ms,
                "pipeline_errors": ctx.errors,
            }

        # Physics emission + attribution
        plume_area = float(plume_pixels) * pixel_area_m2
        # Use SWIR normalized ratio inside plume as concentration proxy
        conc_proxy = float(np.mean(c_norm[final_mask > 0])) if plume_pixels > 0 else 0.0

        if is_synthetic:
            # Scale down the synthetic proxy so it yields realistic, varying emission values (e.g. 800 - 2500 kg/hr)
            # instead of astronomical values that always hit the 6000.0 kg/hr hard cap.
            conc_proxy = conc_proxy * 0.02
            c_norm = c_norm * 0.02

        inversion = invert_emission(plume_area, c_norm, final_mask, wind_speed)
        ime = ime_emission(c_norm, final_mask, pixel_area_m2, wind_speed)
        ime_emission_kghr_raw = float(ime.get("emission_kghr", 0.0) or 0.0)

        phys = physics_emission(
            plume_area_m2=plume_area,
            concentration_proxy=conc_proxy,
            wind_speed_ms=wind_speed,
            wind_direction_deg=90.0,
            pixel_area_m2=PIXEL_AREA,
            gwp_factor=METHANE_GWP,
            gas_price_usd_per_kg=GAS_PRICE_USD_PER_KG,
        )
        ctx.physics_result = phys
        physics_emission_kghr_raw = float(phys.get("emission_kghr", 0.0) or 0.0)
        emission_kghr, calib_meta = _calibrated_emission_kghr(
            ime_kghr=ime_emission_kghr_raw,
            physics_kghr=physics_emission_kghr_raw,
            plume_area_m2=plume_area,
            wind_speed_ms=wind_speed,
        )

        plume = PlumeObservation(
            centroid_lat=lat,
            centroid_lon=lon,
            area_m2=plume_area,
            intensity=conc_proxy,
            wind_speed_ms=wind_speed,
            wind_dir_deg=90.0,
        )
        graph_res = graph_attribution(plume, PLANT_DB, top_k=3)
        ctx.graph_result = graph_res

        primary = graph_res.get("primary_source")
        source_name = primary.get("plant_name") if primary else "unknown"
        confidence = float(primary.get("confidence", 0.0)) if primary else 0.0

        total_ms = round((time.perf_counter() - t_start) * 1000, 1)
        quantification = {
            "available": True,
            "method": "fused_model_swir_calibrated",
            "emission_kghr": round(float(emission_kghr), 4),
            "cost_loss_usd_per_hour": round(float(emission_kghr) * GAS_PRICE_USD_PER_KG, 2),
            "raw_estimates": {
                "ime_emission_kghr": round(ime_emission_kghr_raw, 4),
                "physics_emission_kghr": round(physics_emission_kghr_raw, 4),
            },
            "calibration": calib_meta,
            "plume_area_m2": round(float(plume_area), 2),
            "concentration_proxy": round(float(conc_proxy), 6),
            "formulas": {
                "ime": "Q (kg/s) = (U_eff / L) * IME ; Q (kg/hr) = Q (kg/s) * 3600",
                "ime_terms": "IME = sum((DeltaOmega) * pixel_area * k_column)",
                "physics": "Q (kg/s) = (M * U * A_align * S_spread) / A_plume ; Q (kg/hr)=Q*3600",
                "cost": "Cost_loss (USD/hr) = Emission_kg_hr * Gas_price_USD_per_kg",
            },
            "ime_details": ime,
            "physics_details": phys,
            "assumptions": {
                "wind_speed_ms": wind_speed,
                "pixel_area_m2": pixel_area_m2,
                "gas_price_usd_per_kg": GAS_PRICE_USD_PER_KG,
                "gwp_factor": METHANE_GWP,
            },
        }
        return {
            "plume_detected": bool(np.any(final_mask > 0)),
            "emission_kghr": round(emission_kghr, 4),
            "cost_loss_usd_per_hour": round(float(emission_kghr) * GAS_PRICE_USD_PER_KG, 2),
            "source": source_name,
            "confidence": confidence,
            "image_source": image_source,
            "inference_mode": inference_mode,
            "model_available": model_available(),
            "model_loaded": model_loaded(),
            "torch_available": torch_available(),
            "inference_reliability": "medium" if model_loaded() else "low",
            "plume_pixels": plume_pixels,
            "model_pixels": int(np.sum(model_mask > 0)),
            "swir_pixels": swir_pixels,
            "raw_pixels": int(np.sum(raw_mask > 0)) if raw_mask is not None else 0,
            "plume_area_m2": round(plume_area, 1),
            "concentration_proxy": round(conc_proxy, 4),
            "pixel_area_m2": round(pixel_area_m2, 3),
            "bbox": bbox_vals,
            "radius_km": radius_km,
            "emission_model": "ime_proxy_v1",
            "inversion_details": inversion,
            "ime_details": ime,
            "physics_details": phys,
            "graph_attribution": graph_res,
            "fp_filter_report": fp_report,
            "emit_status": emit_status,
            "model_threshold_used": round(float(model_threshold_used), 6),
            "model_probability_stats": {
                "min": round(float(model_prob_stats["min"]), 6),
                "max": round(float(model_prob_stats["max"]), 6),
                "mean": round(float(model_prob_stats["mean"]), 6),
            },
            "quantification": quantification,
            "used_coordinates": {"lat": float(lat), "lon": float(lon)},
            "swir_threshold": round(float(swir_thresh), 6),
            "c_norm_stats": {
                "min": round(float(np.min(c_norm)), 6),
                "max": round(float(np.max(c_norm)), 6),
                "mean": round(float(np.mean(c_norm)), 6),
            },
            "processing_time_ms": total_ms,
            "pipeline_errors": ctx.errors,
        }

    def get_plant_history(self, plant_id: str) -> Dict[str, Any]:
        h = self._history.get(plant_id, [])
        return {"plant_id": plant_id, "readings": len(h),
                "history": h, "analysis": analyze_time_series(h)}

    def _build_response(self, ctx: PipelineContext, total_ms: float) -> Dict[str, Any]:
        ins    = ctx.insights
        images = _encode_images(ctx)

        emission_kghr = ctx.emission.get("emission_kghr", 0.0)
        anomaly       = ctx.temporal.get("anomaly_flag", False)
        alert         = bool(emission_kghr > ALERT_THRESHOLD or anomaly)
        alert_type    = ("High emission" if emission_kghr > ALERT_THRESHOLD else "") + \
                        (" + Anomaly" if anomaly else "")
        priority      = "Critical" if emission_kghr > SEV_HIGH else \
                        "High"     if emission_kghr > SEV_MODERATE else "Normal"

        return {
            # ── Core fields (v1-compatible) ───────────────────────────────────
            "methane_detected":    ins.get("methane_detected", False),
            "emission":            ctx.emission,
            "risk_score":          ins.get("risk_score", 0.0),
            "confidence":          ins.get("confidence", 0.0),
            "uncertainty":         ins.get("uncertainty", 0.0),
            "uncertainty_note":    ins.get("uncertainty_note", ""),
            "impact":              ins.get("impact", {}),
            "recommendation":      ins.get("recommendation", ""),
            "source":              ctx.source,
            "temporal_analysis":   ctx.temporal,
            "attribution_method":  ctx.source.get("attribution_method", ""),
            "processing_time_ms":  total_ms,
            "fp_filter_report":    ctx.fp_report,
            "images":              images,
            "agent_timings":       ctx.agent_timings,
            "data_source":         ctx.data_source,
            "pipeline_errors":     ctx.errors,

            # ── v2 new fields ──────────────────────────────────────────────────
            "alert":               alert,
            "alert_type":          alert_type.strip(" +"),
            "priority":            priority,
            "graph_attribution":   ctx.graph_result,
            "physics_details":     ctx.physics_result,

            # ── Metadata ──────────────────────────────────────────────────────
            "metadata": {
                "model":          "UNet-EN02-v2" if ctx.model else "threshold-only",
                "device":         ctx.device,
                "wind_speed_ms":  WIND_SPEED,
                "pixel_res_m":    30,
                "gwp_factor":     METHANE_GWP,
                "pipeline":       "agent-based v2 (physics + graph)",
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _recommendation(severity: str, plant_type: str) -> str:
    r = {
        "None":     "No action required. Continue scheduled monitoring.",
        "Low":      f"Flag for inspection at {plant_type}. Dispatch ground team within 72 hours.",
        "Moderate": f"Immediate inspection required at {plant_type}. Notify facility operator.",
        "High":     f"URGENT: Partial shutdown of {plant_type} recommended. Contact environmental authority.",
        "Critical": f"EMERGENCY: Evacuate vicinity. Full shutdown of {plant_type}. Regulatory notification required.",
    }
    return r.get(severity, r["Low"])


def _zero_emission() -> Dict[str, Any]:
    return {"emission_kghr": 0.0, "plume_area_m2": 0, "coverage_pct": 0.0,
            "severity": "None", "co2_equivalent_kghr": 0.0, "financial_loss_usd_hr": 0.0}


def _synthetic_prob_map() -> np.ndarray:
    mask = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.float32)
    for _ in range(random.randint(1, 3)):
        cx = random.randint(IMG_SIZE // 4, 3 * IMG_SIZE // 4)
        cy = random.randint(IMG_SIZE // 4, 3 * IMG_SIZE // 4)
        cv2.ellipse(mask, (cx, cy), (random.randint(25, 70), random.randint(20, 55)),
                    random.uniform(0, 180), 0, 360, random.uniform(0.6, 1.0), -1)
    return np.clip(cv2.GaussianBlur(mask, (41, 41), 0), 0, 1)


def _encode_images(ctx: PipelineContext) -> Dict[str, Optional[str]]:
    def enc(arr):
        if arr is None: return None
        if arr.ndim == 2: arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
        _, buf = cv2.imencode(".png", arr)
        return base64.b64encode(buf).decode()

    def heatmap(mask, base):
        if mask is None or base is None: return None
        colored = cv2.applyColorMap(mask, cv2.COLORMAP_JET)
        base3   = base if base.ndim == 3 else cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
        return enc(cv2.addWeighted(base3, 0.48, colored, 0.52, 0))

    rgb = ctx.cleaned_bands.get("rgb")
    if rgb is None:
        rgb = ctx.bands.get("rgb")
    return {
        "original":   enc(rgb),
        "cleaned":    enc(rgb),
        "ch4_band":   enc(ctx.ch4_band),
        "swir_ratio": enc(ctx.swir_ratio),
        "heatmap":    heatmap(ctx.final_mask, rgb),
    }


def _load_aviris_or_fallback(lat: float, lon: float) -> Optional[np.ndarray]:
    """
    Try to load a local AVIRIS sample. If unavailable, fall back to Sentinel-2 stub RGB.
    """
    # AVIRIS local sample
    try:
        from ai.data.aviris_loader import load_aviris_folder

        samples = load_aviris_folder("ai/data/raw", max_samples=1)
        if samples:
            rgb, _ = samples[0]
            rgb = (rgb * 255).astype(np.uint8) if rgb.max() <= 1.0 else rgb.astype(np.uint8)
            return rgb
    except Exception as exc:
        logger.info("AVIRIS load failed; falling back to sentinel stub (%s)", exc)

    # Sentinel-2 fallback (stub)
    try:
        bands = fetch_sentinel_data(lat, lon)
        rgb = bands.get("rgb")
        if rgb is not None:
            return rgb
    except Exception as exc:
        logger.info("Sentinel fallback failed (%s)", exc)

    return None


def _save_mask_image(mask: Optional[np.ndarray]) -> None:
    if mask is None:
        return
    try:
        out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "outputs")
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "mask.png")
        cv2.imwrite(out_path, mask)
    except Exception as exc:
        logger.info("Mask save failed (%s)", exc)


def _save_satellite_image(rgb: Optional[np.ndarray]) -> None:
    if rgb is None:
        return
    try:
        out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "outputs")
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "latest_satellite.png")
        img = _normalize_rgb_for_display(rgb)
        img = _enhance_rgb_for_display(img)
        img = _resize_for_display(img, target=960)
        cv2.imwrite(out_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    except Exception as exc:
        logger.info("Satellite save failed (%s)", exc)


def _save_swir_false_color(
    rgb: Optional[np.ndarray],
    swir_ratio: Optional[np.ndarray],
    mask: Optional[np.ndarray],
) -> None:
    if rgb is None or swir_ratio is None:
        return
    try:
        out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "outputs")
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "swir_false.png")

        base = _normalize_rgb_for_display(rgb)
        base = _enhance_rgb_for_display(base)
        heat_in = _normalize_gray_for_display(swir_ratio)
        heat = cv2.applyColorMap(heat_in, cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(base, 0.55, heat, 0.45, 0)
        if mask is not None and np.any(mask > 0):
            overlay[mask > 0] = [255, 0, 0]
        overlay = _resize_for_display(overlay, target=960)
        cv2.imwrite(out_path, cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    except Exception as exc:
        logger.info("SWIR save failed (%s)", exc)


def _normalize_gray_for_display(arr: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    lo = float(np.percentile(x, 1))
    hi = float(np.percentile(x, 99))
    if hi - lo < 1e-6:
        return np.zeros_like(x, dtype=np.uint8)
    y = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return (y * 255).astype(np.uint8)


def _normalize_rgb_for_display(rgb: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(rgb.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    if x.max() > 1.5:
        x = x / 255.0
    out = np.zeros_like(x, dtype=np.float32)
    for c in range(3):
        ch = x[:, :, c]
        lo = float(np.percentile(ch, 1))
        hi = float(np.percentile(ch, 99))
        if hi - lo < 1e-6:
            out[:, :, c] = np.clip(ch, 0.0, 1.0)
        else:
            out[:, :, c] = np.clip((ch - lo) / (hi - lo), 0.0, 1.0)
    # Mild gamma lift improves dark scenes while keeping contrast.
    out = np.power(np.clip(out, 0.0, 1.0), 0.85)
    return (out * 255).astype(np.uint8)


def _enhance_rgb_for_display(img: np.ndarray) -> np.ndarray:
    """
    Improve visual readability for UI display (no impact on model inference).
    """
    x = np.clip(img.astype(np.uint8), 0, 255)

    # Gray-world white balance.
    bgr = cv2.cvtColor(x, cv2.COLOR_RGB2BGR).astype(np.float32)
    means = np.mean(bgr.reshape(-1, 3), axis=0)
    gray_mean = float(np.mean(means)) + 1e-6
    scales = gray_mean / (means + 1e-6)
    bgr = np.clip(bgr * scales, 0, 255).astype(np.uint8)

    # Local contrast enhancement on luminance.
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    lab2 = cv2.merge([l2, a, b])
    enhanced = cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)

    # Unsharp mask for clearer edges.
    blur = cv2.GaussianBlur(enhanced, (0, 0), 1.1)
    sharp = cv2.addWeighted(enhanced, 1.45, blur, -0.45, 0)
    sharp = np.clip(sharp, 0, 255).astype(np.uint8)
    return cv2.cvtColor(sharp, cv2.COLOR_BGR2RGB)


def _resize_for_display(img: np.ndarray, target: int = 960) -> np.ndarray:
    h, w = img.shape[:2]
    if min(h, w) >= target:
        return img
    scale = target / max(min(h, w), 1)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)


def _calibrated_emission_kghr(
    ime_kghr: float,
    physics_kghr: float,
    plume_area_m2: float,
    wind_speed_ms: float,
) -> tuple[float, Dict[str, Any]]:
    """
    Calibrate IME and physics estimates to avoid implausible outliers.
    Keeps both raw estimates available in response.
    """
    ime = max(float(ime_kghr), 0.0)
    phys = max(float(physics_kghr), 0.0)

    if ime <= 0 and phys <= 0:
        return 0.0, {
            "strategy": "no_signal",
            "ime_to_physics_cap_factor": 6.0,
            "global_scale": float(os.getenv("EN02_EMISSION_CALIBRATION_SCALE", "0.12")),
            "max_emission_cap_kghr": float(os.getenv("EN02_EMISSION_MAX_KGHR", "6000")),
            "hard_cap_kghr": 0.0,
            "pre_cap_kghr": 0.0,
        }

    if phys <= 0:
        pre_cap = ime
    elif ime <= 0:
        pre_cap = phys
    else:
        ime_capped = min(ime, phys * 6.0)
        # Physics leads; IME contributes after outlier cap.
        pre_cap = 0.65 * phys + 0.35 * ime_capped

    # Conservative normalization for realistic operational ranges.
    global_scale = float(os.getenv("EN02_EMISSION_CALIBRATION_SCALE", "0.12"))
    size_factor = float(np.clip(math.sqrt(max(plume_area_m2, 1.0)) / 450.0, 0.65, 1.35))
    wind_factor = float(np.clip(max(wind_speed_ms, 0.1) / 6.0, 0.75, 1.40))
    scaled = pre_cap * global_scale * size_factor * wind_factor

    # Scenario-aware hard cap + global project cap.
    area_cap = max(400.0, plume_area_m2 / 12.0)
    wind_cap = max(400.0, wind_speed_ms * 900.0)
    scenario_cap = min(max(area_cap, wind_cap), 25000.0)
    max_cap = float(os.getenv("EN02_EMISSION_MAX_KGHR", "6000"))
    hard_cap = min(scenario_cap, max_cap)
    calibrated = min(scaled, hard_cap)

    return float(calibrated), {
        "strategy": "physics_weighted_with_ime_cap_and_conservative_scale",
        "ime_to_physics_cap_factor": 6.0,
        "pre_cap_kghr": round(float(pre_cap), 4),
        "scaled_kghr": round(float(scaled), 4),
        "global_scale": round(float(global_scale), 6),
        "size_factor": round(float(size_factor), 6),
        "wind_factor": round(float(wind_factor), 6),
        "hard_cap_kghr": round(float(hard_cap), 4),
        "scenario_cap_kghr": round(float(scenario_cap), 4),
        "max_emission_cap_kghr": round(float(max_cap), 4),
        "area_cap_kghr": round(float(area_cap), 4),
        "wind_cap_kghr": round(float(wind_cap), 4),
    }


def _fallback_live_bands(
    lat: float,
    lon: float,
    size: int = 256,
    radius_km: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Deterministic local fallback when live satellite fetch is unavailable.
    Produces normalized pseudo-spectral bands compatible with the live pipeline.
    """
    seed = int((abs(lat) * 10_000 + abs(lon) * 10_000)) % (2**32 - 1)
    rng = np.random.default_rng(seed)

    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    x = x / max(size - 1, 1)
    y = y / max(size - 1, 1)

    # Smooth scene + weak noise, then add a soft plume-like anomaly.
    base = 0.25 + 0.35 * (0.6 * x + 0.4 * y)
    noise = rng.normal(0.0, 0.02, size=(size, size)).astype(np.float32)

    cx = int(size * 0.55)
    cy = int(size * 0.45)
    
    # Use seed to vary plume size and intensity per coordinate
    size_factor = 0.02 + 0.03 * rng.random()
    intensity_factor = 0.4 + 0.6 * rng.random()
    
    # 30% chance to simulate a completely clean area (e.g., pristine forest)
    if rng.random() > 0.7:
        intensity_factor = 0.0
        
    plume = np.exp(-(((x * size - cx) ** 2) / (2 * (size * size_factor) ** 2)
                     + ((y * size - cy) ** 2) / (2 * (size * (size_factor * 0.7)) ** 2))).astype(np.float32)

    b08 = np.clip(base + noise + 0.05 * plume, 0.0, 1.0)
    b11 = np.clip(base + 0.02 * noise + (0.18 * intensity_factor) * plume, 0.0, 1.0)
    b12 = np.clip(base + 0.02 * noise + (0.28 * intensity_factor) * plume, 0.0, 1.0)
    rgb = np.stack(
        [
            np.clip(0.85 * b12 + 0.05, 0.0, 1.0),
            np.clip(0.95 * b11 + 0.03, 0.0, 1.0),
            np.clip(1.05 * b08, 0.0, 1.0),
        ],
        axis=2,
    ).astype(np.float32)

    if radius_km is not None:
        rkm = max(float(radius_km), 0.1)
        dlat = rkm / 111.32
        dlon = rkm / (111.32 * max(math.cos(math.radians(lat)), 0.01))
        bbox_vals = [lon - dlon, lat - dlat, lon + dlon, lat + dlat]
        width_m = (bbox_vals[2] - bbox_vals[0]) * (111_320.0 * max(math.cos(math.radians(lat)), 0.01))
        height_m = (bbox_vals[3] - bbox_vals[1]) * 111_320.0
        px_x = max(width_m / size, 1.0)
        px_y = max(height_m / size, 1.0)
        pixel_area_m2 = float(px_x * px_y)
    else:
        bbox_vals = [lon - 0.01, lat - 0.01, lon + 0.01, lat + 0.01]
        pixel_area_m2 = 400.0

    return {
        "rgb": rgb,
        "B08": b08.astype(np.float32),
        "B11": b11.astype(np.float32),
        "B12": b12.astype(np.float32),
        "bbox": bbox_vals,
        "radius_km": radius_km,
        "pixel_area_m2": pixel_area_m2,
        "pixel_size_m": float(max(math.sqrt(pixel_area_m2), 1.0)),
    }


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    mgr    = PipelineManager()
    result = mgr.run_pipeline(lat=19.076, lon=72.877)
    print(json.dumps({
        "methane_detected":  result["methane_detected"],
        "emission_kghr":     result["emission"]["emission_kghr"],
        "severity":          result["emission"]["severity"],
        "spread_factor":     result["emission"].get("spread_factor"),
        "stability_class":   result["emission"].get("stability_class"),
        "uncertainty_band":  result["emission"].get("uncertainty_band"),
        "graph_top1":        result["graph_attribution"].get("primary_source", {}).get("plant_name"),
        "graph_confidence":  result["graph_attribution"].get("overall_confidence"),
        "alert":             result["alert"],
        "alert_type":        result["alert_type"],
        "priority":          result["priority"],
        "agent_timings":     result["agent_timings"],
        "total_ms":          result["processing_time_ms"],
        "errors":            result["pipeline_errors"],
    }, indent=2))
    print("✓ PipelineManager v2 self-test complete")
