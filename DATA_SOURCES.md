# Data Sources and Method

## Snapshot status

MXatlas currently publishes a static snapshot rather than a continuously refreshed live dataset.

- Municipality-to-domain mappings were curated from Wikidata website hints and additional review steps.
- DNS-derived mail-provider classifications were created from a batch DNS snapshot.
- The published map should be read as an indicative technical assessment, not as an official statement by any municipality.

## Source overview

### Municipality reference data

- Destatis / Statistikportal / official municipality reference data
- Used for municipality keys, names and administrative reference context
- Data used in modified form

Recommended attribution:

`Data: Destatis / Statistikportal, modified`

### Website hints

- Wikidata
- Used for official-website hints and matching support
- License: CC0

Recommended attribution:

`Wikidata (CC0)`

### Geometry

- GeoBasis-DE / BKG VG250
- Used for municipality boundaries
- License: dl-de/by-2-0
- Data used in modified form

Recommended attribution:

`© GeoBasis-DE / BKG (dl-de/by-2-0), modified`

### Basemap

- © OpenStreetMap contributors
- © CARTO

Used only for the visual basemap tiles in the frontend.

## Project-derived data

The following layers are project-derived:

- municipality -> selected domain
- DNS snapshot results
- provider/platform classification
- confidence / review-related fields

These parts are based on public DNS and source data, but are not themselves official government statements.

## Interpretation

The map is intended to show technical indicators derived from public DNS records.

- Results are indicative
- Results may be incomplete
- Results may become outdated
- Shared administrative domains can affect interpretation
- A website domain and the actual mail domain are not always identical

Recommended public wording:

`Based on publicly visible DNS records, MXatlas provides an indicative classification of municipal mail infrastructure. Results are a static snapshot and may be incomplete or outdated.`
