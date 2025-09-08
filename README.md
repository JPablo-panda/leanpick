> The Idea

Manufacturing/maquila environments often lose visibility of which lot to pick first and how much inventory value is being consumed per pick. FIFO Automator solves this with a simple Streamlit UI and a Python engine that ranks by FIFO, calculates aging, and shows USD value KPIs, speeding up shopfloor decisions and avoiding scrap.

> Features

FIFO ranking: sorts by FechaRecepcion while respecting constraints (valid locations, quality, etc.)

Aging: days since receipt + bucketization (0–30, 31–60, 61–90, 90+)

USD value KPI: conversion of Quantity × UnitPrice

Quick filters: SKU, location, quality

Export: results to CSV/XLSX

Configurable: site rules, optional columns, simple validations

Roadmap (short‑term): multi‑user, plant profiles, dataset caching, ERP integration (CSV / API), logs & pick auditing.

> Data model (expected columns)

Required: SKU, LoteID, FechaRecepcion, Ubicacion, Cantidad, CalidadStatus

Optional: FechaCaducidad, PutAwayTS, DocRecepcion, PrecioUnitario, Moneda, Proveedor

Engine auto‑parses dates (YYYY-MM-DD recommended).

> Demo dataset

/data/onhand.csv — minimal reproducible dataset to play with the app.

> Quickstart
# 1) Clone repo
git clone https://github.com/JPablo-panda/leanpick.git
cd leanpick


# 2) Create env & install deps
python -m venv .venv
source .venv/bin/activate # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt


# 3) Run app
streamlit run app.py
