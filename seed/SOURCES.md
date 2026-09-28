# Seed image sources

All seed images are **AI-generated synthetic demo data**. The locations and dates in `metadata.csv` are
**fictional**, generated for demonstration. They are not photographs of real places or real work, and no pair
in the demo is evidence of real-world change.

`scripts/seed_cloudinary.py` appends a row for every file in `metadata.csv` that is not listed yet; it never
overwrites rows that were filled in.

| File | Generator | Prompt |
|---|---|---|
