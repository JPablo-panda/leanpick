from pathlib import Path
import io
import pandas as pd
import streamlit as st

# Motor FIFO
from src.fifo_core import (
    load_onhand_csv,
    FifoConfig,
    cola_consumo_por_sku,
    ranking_fifo_todo_inventario,
    add_aging,  # usado para el aging en USD
)

# ---------------- Config de página ----------------
st.set_page_config(page_title="LeanPick (Pilot)", page_icon="📦", layout="wide")

# ---------------- Utilidades de ruta ----------------
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = BASE_DIR / "data" / "onhand.csv"

# ---------------- Sidebar ----------------
st.sidebar.title("⚙️ Configuracion")
st.sidebar.markdown("### Fuente de Datos")
uploaded = st.sidebar.file_uploader("Subir CSV (opcional)", type=["csv"])
use_default = st.sidebar.checkbox("Usar CSV de ejemplo (data/onhand.csv)", value=True)

modo = st.sidebar.selectbox("Regla de priorizacion", ["FIFO"], index=0)
ubic_filter_on = st.sidebar.checkbox("Filtrar por ubicaciones", value=False)
ubicaciones = (
    st.sidebar.text_input("Ubicaciones validas (coma)", value="RACK-01,RACK-02")
    if ubic_filter_on else ""
)

# ---------------- Carga de datos ----------------
@st.cache_data(show_spinner=True)
def load_data(filelike_or_path: str | io.BytesIO) -> pd.DataFrame:
    if isinstance(filelike_or_path, (str, Path)):
        return load_onhand_csv(str(filelike_or_path))
    df = pd.read_csv(filelike_or_path)
    tmp = BASE_DIR / "_tmp_onhand_streamlit.csv"
    df.to_csv(tmp, index=False)
    out = load_onhand_csv(str(tmp))
    tmp.unlink(missing_ok=True)
    return out

try:
    if uploaded is not None and not use_default:
        onhand = load_data(uploaded)
    else:
        onhand = load_data(DEFAULT_CSV)
except Exception as e:
    st.error(f"Error cargando datos: {e}")
    st.stop()

cfg = FifoConfig(
    modo=modo,
    ubicaciones_validas=[u.strip() for u in ubicaciones.split(",")] if (ubic_filter_on and ubicaciones.strip()) else None
)

# ---------------- Encabezado ----------------
st.title("📦 FIFO Automator - MVP")
st.caption("CSV esperado: SKU, LoteID, FechaRecepcion, Ubicacion, Cantidad, CalidadStatus (+ opcional PrecioUnitarioUSD).")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("SKUs (LIBRE)", int(onhand.loc[onhand["CalidadStatus"].str.upper()=="LIBRE","SKU"].nunique()))
with col2:
    st.metric("Lotes (LIBRE)", int(onhand.loc[onhand["CalidadStatus"].str.upper()=="LIBRE"].shape[0]))
with col3:
    total_qty = float(onhand.loc[onhand["CalidadStatus"].str.upper()=="LIBRE","Cantidad"].sum())
    st.metric("Cantidad total LIBRE", f"{total_qty:,.0f}")
with col4:
    st.metric("Regla", cfg.modo)

st.divider()

# ---------------- Tabs ----------------
tab_rank, tab_cola, tab_datos = st.tabs(["🧮 Ranking FIFO", "🧰 Cola de Consumo", "🗂️ Datos"])

# ===== TAB: Ranking FIFO =====
with tab_rank:
    st.subheader("🧮 Ranking FIFO por SKU (lotes elegibles)")
    try:
        ranking = ranking_fifo_todo_inventario(onhand, cfg)
    except Exception as e:
        st.error(f"Error al generar ranking: {e}")
        st.stop()

    st.dataframe(ranking, use_container_width=True)

    csv_rank = ranking.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Descargar ranking FIFO (CSV)",
        data=csv_rank,
        file_name="ranking_fifo.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # ---------- Aging en USD ----------
    st.markdown("### 💵 Aging en USD (lotes LIBRE)")
    libre = onhand[onhand["CalidadStatus"].str.upper() == "LIBRE"].copy()

    # Precio unitario (si falta, asumimos 0)
    if "PrecioUnitarioUSD" not in libre.columns:
        libre["PrecioUnitarioUSD"] = 0.0
    libre["PrecioUnitarioUSD"] = pd.to_numeric(libre["PrecioUnitarioUSD"], errors="coerce").fillna(0.0)

    # Edad en días
    libre = add_aging(libre)

    # Buckets
    bins = [-1, 30, 60, 90, 10_000]
    labels = ["0–30", "31–60", "61–90", ">90"]
    libre["AgingBucket"] = pd.cut(libre["EdadDias"], bins=bins, labels=labels)

    # USD por bucket
    libre["MontoUSD"] = libre["Cantidad"] * libre["PrecioUnitarioUSD"]
    aging_usd = (
        libre.groupby("AgingBucket", dropna=False)["MontoUSD"]
        .sum()
        .reindex(labels)
        .fillna(0.0)
        .reset_index()
    )

    c1, c2 = st.columns([2, 3])
    with c1:
        st.dataframe(aging_usd, use_container_width=True)
        csv_aging = aging_usd.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar Aging USD (CSV)",
            data=csv_aging,
            file_name="aging_usd.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with c2:
        st.bar_chart(data=aging_usd, x="AgingBucket", y="MontoUSD", use_container_width=True)

    total_usd = float(aging_usd["MontoUSD"].sum())
    gt90_usd = float(aging_usd.loc[aging_usd["AgingBucket"] == ">90", "MontoUSD"].sum())
    pct_gt90 = (gt90_usd / total_usd * 100.0) if total_usd > 0 else 0.0

    k1, k2 = st.columns(2)
    with k1:
        st.metric("Inventario LIBRE (USD)", f"${total_usd:,.2f}")
    with k2:
        st.metric(">90 días (USD y %)", f"${gt90_usd:,.2f}", f"{pct_gt90:.1f}%")

# ===== TAB: Cola de Consumo =====
with tab_cola:
    st.subheader("🧰 Generar Cola de Consumo por SKU")

    skus_libres = sorted(onhand.loc[onhand["CalidadStatus"].str.upper()=="LIBRE","SKU"].unique())
    colA, colB, colC = st.columns([2,2,1])
    with colA:
        sku_sel = st.selectbox("SKU", options=skus_libres, index=0 if skus_libres else None, placeholder="Selecciona un SKU")
    with colB:
        sugerida = float(onhand.query("SKU == @sku_sel and CalidadStatus.str.upper() == 'LIBRE'", engine="python")["Cantidad"].sum()) if skus_libres else 0
        qty = st.number_input("Cantidad requerida", min_value=0.0, step=10.0, value=min(sugerida, 250.0) if sugerida else 0.0)
    with colC:
        go = st.button("Calcular", use_container_width=True)

    if go and sku_sel:
        picks, faltante = cola_consumo_por_sku(onhand, sku_sel, qty, cfg)

        if picks.empty:
            st.warning("No hay lotes elegibles o cantidad = 0.")
        else:
            # Enriquecer con precio y monto USD
            if "PrecioUnitarioUSD" not in onhand.columns:
                onhand["PrecioUnitarioUSD"] = 0.0
            precios = onhand.loc[:, ["LoteID", "PrecioUnitarioUSD"]].drop_duplicates(subset=["LoteID"])
            picks = picks.merge(precios, on="LoteID", how="left")
            picks["PrecioUnitarioUSD"] = pd.to_numeric(picks["PrecioUnitarioUSD"], errors="coerce").fillna(0.0)
            picks["MontoUSD"] = picks["QtyPick"] * picks["PrecioUnitarioUSD"]
            valor_total = float(picks["MontoUSD"].sum())

            k1, k2 = st.columns([1,3])
            with k1:
                st.metric("Valor de la demanda (USD)", f"${valor_total:,.2f}")
            with k2:
                if faltante > 0:
                    st.error(f"Faltante: {faltante:,.0f} unidades")
                else:
                    st.success("Demanda cubierta completamente ✅")

            st.dataframe(picks, use_container_width=True)

            csv_picks = picks.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Descargar picks (CSV)",
                data=csv_picks,
                file_name=f"picks_{sku_sel}.csv",
                mime="text/csv",
                use_container_width=True,
            )

# ===== TAB: Datos =====
with tab_datos:
    st.subheader("🗂️ Datos cargados (on-hand por lote)")
    st.dataframe(onhand, use_container_width=True)
    st.info("Tip: Usa Ranking FIFO para ver la prioridad por SKU y Cola de Consumo para simular una demanda.")