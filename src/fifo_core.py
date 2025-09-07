from __future__ import annotations  
import pandas as pd 
from dataclasses import dataclass   
from typing import Optional, Tuple, List    
REQUIRED_COLS = ["SKU","LoteID", "FechaRecepcion", "Ubicacion", "Cantidad", "CalidadStatus"]    
OPTIONAL_COLS = ["FechaCaducidad","PutAwayTS","DocRecepcion"]   
@dataclass  
class FifoConfig:       
    modo: str = "FIFO"  
    ubicaciones_validas: Optional[List[str]] = None 
def _parse_dates(df: pd.DataFrame) -> pd.DataFrame: 
    if "FechaRecepcion" in df.columns:  
        df["FechaRecepcion"] = pd.to_datetime(df["FechaRecepcion"], errors="coerce")    
    if "FechaCaducidad" in df.columns:  
        df["FechaCaducidad"] = pd.to_datetime(df["FechaCaducidad"], errors="coerce")    
    if "PutAwayTS" in df.columns:   
        df["PutAwayTS"] = pd.to_datetime(df["PutAwayTS"], errors="coerce")  
    return df   
def load_onhand_csv(path: str) -> pd.DataFrame: 
    df = pd.read_csv(path)  
    missing = [c for c in REQUIRED_COLS if c not in df.columns] 
    if missing:     
        raise ValueError(f"Faltan columnas obligatorias en {path}: {missing}")  
    df = _parse_dates(df)
    df["SKU"] = df["SKU"].astype(str)   
    df["LoteID"] = df["LoteID"].astype(str)
    df["Ubicacion"] = df["Ubicacion"].astype(str)   
    if (df["Cantidad"] < 0).any():  
        raise ValueError("Hay Cantidades negativas en el on-hand")  
    return df   
def add_aging(df: pd.DataFrame, today: Optional[pd.Timestamp] = None) -> pd.DataFrame:  
    if today is None:   
        today = pd.Timestamp.today().normalize()    
    out = df.copy() 
    out["EdadDias"] = (today - out["FechaRecepcion"]).dt.days   
    return out  
def orden_prioridad(cfg: FifoConfig) -> List[str]:     
    if cfg.modo.upper() == "FEFO" and "FechaCaducidad" in OPTIONAL_COLS:    
        return ["FechaCaducidad","FechaRecepcion","PutAwayTS", "DocReception","LoteID"] 
    return ["FechaRecepcion","PutAwayTS","DocReception","LoteID"]   
def filtrar_elegibles(df: pd.DataFrame, cfg: FifoConfig) -> pd.DataFrame:   
    q = (df["Cantidad"] > 0) & (df["CalidadStatus"].str.upper() == "LIBRE") 
    if cfg.ubicaciones_validas:     
        q &= df["Ubicacion"].isin(cfg.ubicaciones_validas)  
    elegibles = df.loc[q].copy()    
    return elegibles    
def cola_consumo_por_sku(   
    onhand: pd.DataFrame,   
    sku: str,
    qty_requerida: float,   
    cfg: Optional[FifoConfig] = None) -> Tuple[pd.DataFrame, float]:    
    cfg = cfg or FifoConfig()   
    elegibles = filtrar_elegibles(onhand, cfg)  
    elegibles = elegibles[elegibles["SKU"] == sku].copy()   
    if elegibles.empty: 
        return pd.DataFrame(columns=["SKU","LoteID", "Ubicacion","QtyPick","EdadDias"]), qty_requerida  
    orden = orden_prioridad(cfg)    
    orden_existente = [c for c in orden if c in elegibles.columns] 
    elegibles = elegibles.sort_values(orden_existente, ascending=True, kind="mergesort")    
    elegibles = add_aging(elegibles)    
    picks = []      
    restante = float(qty_requerida) 
    for _, r in elegibles.iterrows():   
        if restante <=0:    
            break   
        tomar = min(float(r["Cantidad"]), restante) 
        if tomar > 0:   
            picks.append({"SKU": r["SKU"], "LoteID": r["LoteID"], "Ubicacion": r["Ubicacion"], "QtyPick": tomar, "EdadDias": int(r["EdadDias"])})   
            restante -= tomar   
    picks_df = pd.DataFrame(picks, columns=["SKU","LoteID","Ubicacion","QtyPick","EdadDias"])   
    return picks_df, restante   
def ranking_fifo_todo_inventario(onhand: pd.DataFrame, cfg: Optional[FifoConfig] = None) -> pd.DataFrame:   
    cfg = cfg or FifoConfig()   
    elegibles = filtrar_elegibles(onhand, cfg).copy()   
    if elegibles.empty:
        return elegibles    
    orden = orden_prioridad(cfg)    
    orden_existente = [c for c in orden if c in elegibles.columns]  
    elegibles = elegibles.sort_values (["SKU"] + orden_existente, ascending=True, kind="mergesort") 
    elegibles = add_aging(elegibles)    
    elegibles["RankFIFO"] = elegibles.groupby("SKU")["FechaRecepcion"].rank(method="first", ascending=True).astype(int) 
    return elegibles[["SKU","LoteID","Ubicacion","Cantidad","EdadDias","RankFIFO","FechaRecepcion"]].reset_index(drop=True)

