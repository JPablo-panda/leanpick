from pathlib import Path    
import pandas as pd     
from fifo_core import load_onhand_csv, FifoConfig, cola_consumo_por_sku, ranking_fifo_todo_inventario   
BASE_DIR = Path(__file__).resolve().parent.parent   
DATA_PATH = BASE_DIR / "data" / "onhand.csv"    
OUT_DIR = BASE_DIR / "outpouts" 
OUT_DIR.mkdir(exist_ok=True)    
def main():     
    onhand = load_onhand_csv(str(DATA_PATH))    
    cfg = FifoConfig(modo="FIFO", ubicaciones_validas=None) 
    print("\n=== Ranking FIFO por SKU (todos los elegibles) ===")   
    ranking = ranking_fifo_todo_inventario(onhand, cfg) 
    ranking_path = OUT_DIR / "ranking_fifo.csv" 
    ranking.to_csv(ranking_path, index=False)   
    print(f"\nRanking guardado en: {ranking_path}") 
    print("\n=== Cola de consumo interactiva ===")  
    skus_disponibles = sorted(onhand.loc[onhand['CalidadStatus'].str.upper()=='Libre','SKU'].unique())  
    print(f"SKUs disponibles (LIBRE): {','.join(skus_disponibles)}")    
    sku = input("Escribe el SKU:  ").strip()    
    try:    
        qty = float(input("Cantidad requerida:  ").strip()) 
    except ValueError:  
        print("Cantidad Invalida.") 
        return  
    picks, faltante = cola_consumo_por_sku(onhand, sku, qty, cfg)   
    if picks.empty: 
        print("\nNo hay lotes elegibles para ese SKU o cantidad = 0.")  
        return  
    print(f"\n=== Cola de consumo para SKU {sku}, demanda= {qty} ===")  
    print(picks.to_string(index=False)) 
    if faltante > 0:    
        print(f"\nFaltante: {faltante:.0f} unidades")   
    else:       
        print("\nDemanda cubierta completamente!")  
    picks_path = OUT_DIR / f"picks_{sku}.csv"   
    picks.to_csv(picks_path, index=False)   
    print(f"\nPicks guardados en: {picks_path}")    
if __name__ == "__main__":  
    main()   

