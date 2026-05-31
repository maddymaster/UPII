# Meeting Notes: ICEYE Partnership Sync
**Date:** Oct 20, 2025
**Participants:** Maddy (Ambee), Sarah (VP Eng, ICEYE), David (Product, ICEYE)
**Topic:** Wildfire Detection using SAR

## Key Discussion Points
*   **The Problem**: Our optical sensors are blind during heavy smoke events (California/Canada wildfires).
*   **The Solution**: ICEYE's SAR (Synthetic Aperture Radar) can image through clouds and smoke, day/night.
*   **Integration Plan**:
    *   ICEYE will provide a "Tasking API" where Ambee can request a satellite pass over a high-risk coordinate (e.g., Napa Valley).
    *   Latency: Guarantees < 3 hours from request to image delivery.
    *   Format: GeoTIFF images with 50cm resolution.

## Action Items
*   **[Maddy]**: Create a secure S3 bucket for ICEYE to drop GRIB/GeoTIFF files.
*   **[Data Science Team]**: Build a "Change Detection" model to compare pre-fire vs. active-fire SAR images.
*   **[Sarah]**: Send API documentation for the `v3/tasking` endpoint.
*   **[Maddy]**: Schedule a follow-up for Nov 1st to review the first batch of test data (Amazon Rainforest dataset).

## Riskiest Assumptions
*   can we process 50cm resolution SAR data in real-time? (Current pipelines are optimized for 10m Sentinel data).
