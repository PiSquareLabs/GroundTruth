# Seed image sources

All seed images are **synthetic, computer-generated demo data** (procedurally rendered by `scripts/generate_synthetic_seed.py`). The locations and dates in `metadata.csv` are
**fictional**, generated for demonstration. They are not photographs of real places or real work, and no pair
in the demo is evidence of real-world change.

`scripts/seed_cloudinary.py` appends a row for every file in `metadata.csv` that is not listed yet; it never
overwrites rows that were filled in.

| File | Generator | Prompt / scene |
|---|---|---|
| drain_before_01.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Concrete storm drain, site 1, clogged with plastic waste, silt and weeds |
| drain_after_01.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Same drain, site 1, cleared; removed silt in sacks on the bank |
| drain_after_01_copy.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Near-duplicate of drain_after_01.jpg (cropped, rescaled, brightened) |
| drain_before_02.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Concrete storm drain, site 2, blocked with plastic waste |
| drain_after_02.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Same drain, site 2, cleared and flowing |
| drain_signboard.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Roadside project signboard for the fictional drive |
| lakeside_before_01.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Bare, dry plot on a lake shore before planting |
| lakeside_after_01.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Same plot, six weeks later: rows of staked saplings in mulch basins |
| lakeside_after_01_late.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Same plot, three months later: saplings taller, grass returning |
| lakeside_before_02.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Second bare lake-shore plot before planting |
| lakeside_after_02.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Second plot after planting |
| lakeside_nursery.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Top-down view of sapling nursery trays (no date or GPS on purpose) |
| park_before_01.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Park lawn with scattered litter and an overflowing bin |
| park_after_01.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Same lawn after the clean-up the same evening |
| park_after_01_offsite.jpg | Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py` | Same lawn next morning (GPS missing on purpose) |
