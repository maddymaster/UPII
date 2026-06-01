---
author: Maddy
---
# Ambee Strategic Roadmap 2026: The "Planetary Pulse" Initiative

**Owner:** Maddy (CTO)
**Last Updated:** Oct 24, 2025
**Confidentiality:** INTERNAL ONLY

## Vision
To build the world's first "Real-Time Planetary Nervous System" by fusing hyperspectral optical data (NASA PACE) with Synthetic Aperture Radar (ICEYE).

## Q1 2026 Objectives
1.  **Project "Clear Air" (PACE Integration)**
    *   **Goal**: Reduce Air Quality Index (AQI) latency from 60 mins to 15 mins.
    *   **Method**: Ingest NASA PACE's OCI (Ocean Color Instrument) data for aerosol characterization.
    *   **Status**: Alpha capabilities proven. Need to scale data pipeline to handle 10TB/day.

2.  **Project "Firewatch" (ICEYE Partnership)**
    *   **Goal**: Detect wildfire progressions *through* smoke clouds.
    *   **Method**: Use ICEYE's X-band SAR (Synthetic Aperture Radar) to image ground topology changes during active burn events.
    *   **Blockers**: API rate limits on ICEYE's side.

3.  **Data Science Architecture**
    *   Migrate from current batch processing to `Stream-First` architecture (Kafka + Flink).
    *   Hire 2 Sr. Geospatial Engineers.

## Competitive Landscape
*   **BreezoMeter**: Strong in consumer app integration, but lacks our raw satellite fidelity.
*   **Plume Labs**: Good hardware, but weak on global coverage.
*   **Our Moat**: The fusion of proprietary ground sensors + PACE hyperspectral data.
