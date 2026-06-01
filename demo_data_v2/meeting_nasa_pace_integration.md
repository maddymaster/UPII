---
author: Maddy
---
# Sync: NASA PACE Integration
**Date:** Last Week (Oct 24, 2025)
**Participants:** Maddy (Ambee), Dr. Elena (NASA Goddard), Project Leads
**Topic:** Hyperspectral Data Access

## Context
Ambee is an "Early Adopter" for the PACE mission. We are getting access to the OCI (Ocean Color Instrument) data stream.

## Meeting Summary
*   **Calibration Issues**: Dr. Elena confirmed that the 'Blue Band' sensor on PACE needs recalibration. Our AOD (Aerosol Optical Depth) calculations for the last month might be off by 5%.
*   **Pollen Detection**: We discussed using the UV channels to distinguish between *Birch* vs *Oak* pollen grains in the atmosphere. This is a game changer for our Allergy App.
*   **Data Volume**: The new hyperspectral feed is massive. 200 bands vs the 7 bands we used to get from MODIS.

## Decisions
1.  **Prioritize UV Data**: Shift engineering resources to ingest the UV spectrum data first (for Pollen season).
2.  **Ignore Blue Band**: Until NASA issues the patch (ETA: Nov 15), we will fallback to Sentinel-5P for blue-light aerosol data.

## Maddy's Notes
*   "The level of detail in PACE is insane. We can literally see algal blooms shifting in real-time."
*   Need to upgrading our cluster. The current 64-core nodes won't handle the decompression speed needed.
