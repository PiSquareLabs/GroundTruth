# Seed image sources

Demo dataset: the **before** photos are real photos supplied by the maintainer; the **after** images are
**AI-generated or edited** illustrations of the intended repair. Locations (Kochi, Kerala) and dates in
`metadata.csv` are **fictional**, assigned for the demo. Nothing here is evidence of a real-world repair.

`scripts/seed_cloudinary.py` appends a row for every file in `metadata.csv` that is not listed yet; it never
overwrites rows that were filled in.

| File | Generator | Prompt |
|---|---|---|
| electrical_cable_before.jpg | Real photo (maintainer) | n/a |
| electrical_cable_after.jpg | AI-generated / edited (maintainer: _fill in tool_) | _fill in prompt_ |
| gutter_cover_before.jpg | Real photo (maintainer) | n/a |
| gutter_cover_after.jpg | AI-generated / edited (maintainer: _fill in tool_) | _fill in prompt_ |
| wiring_before.jpg | Real photo (maintainer) | n/a |
| wiring_after.png | AI-generated / edited (maintainer: _fill in tool_) | _fill in prompt_ |
| utility_hatch_before.jpg | Real photo (maintainer) | n/a |
| utility_hatch_after.jpg | AI-generated / edited (maintainer: _fill in tool_) | _fill in prompt_ |
