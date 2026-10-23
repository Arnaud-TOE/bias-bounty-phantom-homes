# Phantom homes: destroyed homes still on the map

Best Bias Discovery entry for the Zindi **Bias Bounty Mapping Equity Challenge**
(Zindi user **Arnaud_TOE**, associated leaderboard submission `iu1dZ8Hf`).

Of the 6,868 structures destroyed by Northern California wildfires from 2020 to 2025 (CAL FIRE
damage inspections), **2,063 (30.0 %) are still drawn as standing buildings** in Overture
release 2026-08-19.0, each with a source date earlier than the fire. Net of chance proximity
the excess is **24.3 % (95 % CI 17.4-35.8 %, clustered by fire)**. For fires up to 2019 the
rate is 0.2 %. The write-up is `writeup/bias_discovery.md` (PDF in `writeup/pdf/`).

## Reproduce (about 2 minutes after the download)

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -I get_data.py                # challenge files (~470 MB) + the two external files, all SHA-256 checked
python -I discovery/reproduce.py     # every number, table (discovery/out/) and figure (writeup/figures/)
```

`get_data.py` downloads the challenge extract from the public Source Cooperative bucket and
decompresses the two external files shipped in `discovery/external/` (CAL FIRE DINS, CC-BY;
CMS Nursing Home Provider Information, public domain). Their original URLs and retrieval dates
are in `discovery/external/SOURCES.md`.

## Scope and compliance

- External data is used for this discovery only, as the challenge rules allow for this prize.
- No withdrawn reference layer (TIGER, Microsoft footprints, HIFLD/USGS, CBP) is read.
- The scored leaderboard pipeline is a separate code base, published after the leaderboard
  closes (31 October 2026).

## Licences

Code: MIT (`LICENSE`). Data: see `DATA_LICENCES.md`.
