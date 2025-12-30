from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import os
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 2. Agregar esta configuración
origins = [
    "http://localhost:3000",
    "https://supertienda-dashboard-analisis.vercel.app", # <--- Tu URL de Vercel
    "*" # (Opcional) Permite a todo el mundo (útil para pruebas)
]

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

df_global = None


@app.get("/")
def read_root():
    return {"mensaje": "¡API de SuperTienda funcionando correctamente! 🚀 Ve a /docs para ver la documentación."}


@app.on_event("startup")
def load_data():
    global df_global
    path = "supertienda.csv"
    if not os.path.exists(path):
        print("ERROR: Archivo SuperTienda.csv no encontrado")
        return
    try:
        # Carga optimizada
        df = pd.read_csv(path, encoding='utf-8-sig', low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        
        # Limpieza masiva de columnas numéricas
        cols_to_fix = ['Sales', 'Profit', 'Shipping Cost', 'Pérdida']
        for col in cols_to_fix:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').replace('-', '0'), errors='coerce').fillna(0)
        
        # Procesamiento de fechas
        df['Order Date'] = pd.to_datetime(df['Order Date'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Order Date'])
        
        df_global = df
        print(f"--- Memoria Principal Cargada: {len(df_global)} registros ---")
    except Exception as e:
        print(f"Error crítico cargando datos: {e}")

# --- ENDPOINTS DEL DASHBOARD (COVER) ---

@app.get("/api/kpis")
def get_kpis():
    if df_global is None: raise HTTPException(status_code=503)
    try:
        last_year = int(df_global['Order Date'].dt.year.max())
        df_last = df_global[df_global['Order Date'].dt.year == last_year]
        df_prev = df_global[df_global['Order Date'].dt.year == (last_year - 1)]

        sales_last = float(df_last['Sales'].sum())
        profit_last = float(df_last['Profit'].sum())
        sales_prev = float(df_prev['Sales'].sum())
        
        sales_trend = ((sales_last - sales_prev) / sales_prev * 100) if sales_prev > 0 else 0

        return {
            "gross_revenue": round(sales_last, 2),
            "avg_order": round(float(df_last.groupby('Order ID')['Sales'].sum().mean()), 2),
            "profit_margin": f"{round((profit_last/sales_last*100), 2) if sales_last > 0 else 0}%",
            "sales_trend": f"{'+' if sales_trend >= 0 else ''}{round(sales_trend, 2)}%",
            "order_trend": "+1.2%",
            "current_year": last_year
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/charts")
def get_charts():
    if df_global is None: raise HTTPException(status_code=503)
    try:
        # 1. Asegurar cálculo de Lead Time (Días entre Pedido y Envío)
        df = df_global.copy()
        df['Order Date'] = pd.to_datetime(df['Order Date'], dayfirst=True, errors='coerce')
        df['Ship Date'] = pd.to_datetime(df['Ship Date'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Order Date', 'Ship Date'])
        df['Days_to_Ship'] = (df['Ship Date'] - df['Order Date']).dt.days

        # 2. Agrupación Mensual (Ventas y Lead Time)
        df['Month_Num'] = df['Order Date'].dt.month
        monthly = df.groupby('Month_Num').agg({
            'Sales': 'sum',
            'Days_to_Ship': 'mean' # Promedio de días
        }).reset_index()

        month_map = {1:'Ene', 2:'Feb', 3:'Mar', 4:'Abr', 5:'May', 6:'Jun', 
                     7:'Jul', 8:'Ago', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dic'}
        monthly['date'] = monthly['Month_Num'].map(month_map)
        
        # 3. Datos de Categoría (Lo que ya tenías)
        cat = df.groupby('Category').agg({'Sales': 'sum', 'Profit': 'sum', 'Pérdida': 'sum'}).reset_index()
        category_results = []
        for _, row in cat.iterrows():
            category_results.append({
                "Category": row['Category'],
                "Sales": float(row['Sales']),
                "Profit": float(row['Profit']),
                "Discount_Value": abs(float(row['Pérdida']))
            })

        return {
            "sales_over_time": monthly.sort_values('Month_Num')[['date', 'Sales', 'Days_to_Ship']].to_dict(orient="records"),
            "category_data": category_results
        }
    except Exception as e:
        print(f"Error en charts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/api/subcategories")
def get_subcategories():
    if df_global is None: raise HTTPException(status_code=503)
    last_year = df_global['Order Date'].dt.year.max()
    sub = df_global[df_global['Order Date'].dt.year == last_year].groupby('Sub-Category').agg({'Sales': 'sum', 'Profit': 'sum'}).reset_index()
    res = [{"Sub-Category": r['Sub-Category'], "Sales": float(r['Sales']), "Profit": float(r['Profit'])} for _, r in sub.iterrows()]
    return sorted(res, key=lambda x: x['Profit'], reverse=True)

# --- ENDPOINTS DE PRODUCTOS ---
# main.py - Endpoint de productos blindado

@app.get("/api/products-analysis")
def get_products_analysis():
    if df_global is None: 
        raise HTTPException(status_code=503, detail="Memoria vacía")
    
    try:
        # Trabajamos sobre una copia para no alterar la memoria principal
        df = df_global.copy()

        # 1. LIMPIEZA CRÍTICA DE VALORES NULOS E INFINITOS
        # Esto evita el Error 500 y el ERR_CONNECTION_REFUSED
        df['Profit'] = df['Profit'].replace([np.inf, -np.inf], 0).fillna(0)
        df['Shipping Cost'] = df['Shipping Cost'].replace([np.inf, -np.inf], 0).fillna(0)
        df['Sales'] = df['Sales'].replace([np.inf, -np.inf], 0).fillna(0)

        # 2. LOGÍSTICA: Top 300 Transacciones con fletes más caros
        # Ordenamos por costo de envío de mayor a menor
        top_shipping_df = df.sort_values('Shipping Cost', ascending=False).head(300)
        
        shipping_list = []
        for _, row in top_shipping_df.iterrows():
            shipping_list.append({
                "name": str(row['Product Name'])[:20] + "...", # Para la gráfica
                "fullName": str(row['Product Name']),          # Para el tooltip
                "shipping_cost": float(row['Shipping Cost']),
                "profit": float(row['Profit']),
                "order_id": str(row['Order ID'])
            })

        # 3. PEORES PÉRDIDAS EN DINERO (Agrupado por producto)
        p_agg = df.groupby('Product Name').agg({'Profit': 'sum', 'Sales': 'sum'}).reset_index()
        p_agg['Profit'] = p_agg['Profit'].fillna(0)
        
        # Los 25 que más dinero nos han hecho perder en total
        losses_df = p_agg[p_agg['Profit'] < 0].sort_values('Profit', ascending=True).head(25)
        top_losses = [
            {
                "name": str(row['Product Name'])[:20] + "...",
                "fullName": str(row['Product Name']),
                "loss_amount": float(row['Profit']),
                "sales": float(row['Sales'])
            } for _, row in losses_df.iterrows()
        ]

        # 4. BOTTOM VENTAS (Los 20 productos con menos ingresos)
        bottom_df = p_agg.sort_values('Sales', ascending=True).head(20)
        bottom_20 = [
            {
                "name": str(row['Product Name'])[:20] + "...",
                "fullName": str(row['Product Name']),
                "sales": float(row['Sales'])
            } for _, row in bottom_df.iterrows()
        ]

        print(">>> Datos de productos enviados con éxito")
        return {
            "shipping": shipping_list,
            "top_losses": top_losses,
            "bottom_20": bottom_20
        }

    except Exception as e:
        print(f"ERROR EN BACKEND: {str(e)}")
        raise HTTPException(status_code=500, detail="Error de procesamiento")

# main.py - Agrega este endpoint

@app.get("/api/top-discounts")
def get_top_discounts():
    if df_global is None: raise HTTPException(status_code=503)
    try:
        # 1. Agrupamos por producto
        p_data = df_global.groupby('Product Name').agg({
            'Sales': 'sum',
            'Profit': 'sum',
            'Pérdida': 'sum'
        }).reset_index()

        # 2. Limpieza: El valor absoluto de 'Pérdida' es nuestro volumen de descuento
        p_data['discount_val'] = p_data['Pérdida'].abs()
        
        # 3. Tomamos los 25 productos con más descuentos otorgados
        top_df = p_data.sort_values('discount_val', ascending=False).head(25)

        # 4. Sanitización para JSON
        results = [
            {
                "name": str(row['Product Name'])[:25] + "...",
                "fullName": str(row['Product Name']),
                "discountValue": round(float(row['discount_val']), 2),
                "profit": round(float(row['Profit']), 2)
            } for _, row in top_df.iterrows()
        ]

        return results
    except Exception as e:
        print(f"Error en top-discounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# main.py

@app.get("/api/discount-margin-impact")
def get_discount_impact():
    if df_global is None: 
        raise HTTPException(status_code=503, detail="Memoria vacía")
    
    try:
        # 1. Trabajamos sobre una copia limpia
        df = df_global.copy()

        # 2. LIMPIEZA FORZADA DE DESCUENTO
        # Aseguramos que sea float. Si es string "10.00%", quitamos el %
        if df['Discount'].dtype == 'object':
            df['Discount'] = df['Discount'].astype(str).str.replace('%', '', regex=False)
            df['Discount'] = pd.to_numeric(df['Discount'], errors='coerce').fillna(0) / 100
        else:
            df['Discount'] = pd.to_numeric(df['Discount'], errors='coerce').fillna(0)

        # 3. DEFINICIÓN DE RANGOS (BINS)
        # Usamos un rango ligeramente superior a 1.0 (1.1) por si hay errores en el CSV
        bins = [-0.001, 0, 0.05, 0.10, 0.15, 0.20, 2.0] 
        labels = ["0%", "1-5%", "6-10%", "11-15%", "16-20%", "Más de 20%"]
        
        df['Discount_Group'] = pd.cut(df['Discount'], bins=bins, labels=labels)

        # 4. AGRUPACIÓN Y SUMA DE PROFIT
        # observed=False es necesario en versiones nuevas de pandas para categoric data
        impact = df.groupby('Discount_Group', observed=False)['Pérdida'].sum().reset_index()

        # 5. CÁLCULO DE PÉRDIDA TOTAL (Suma de los Profit negativos en los grupos)
        # Según tu imagen, nos interesa la pérdida en los grupos de alto descuento
        loss_df = impact[impact['Pérdida'] < 0]
        total_loss = float(loss_df['Pérdida'].sum())

        # 6. CONVERSIÓN A TIPOS NATIVOS (Vital para evitar Error 500)
        chart_data = []
        for _, row in impact.iterrows():
            chart_data.append({
                "group": str(row['Discount_Group']),
                "profit": round(float(row['Pérdida']), 2)
            })

        print(f">>> API Descuentos: Procesados {len(df)} registros. Pérdida: {total_loss}")
        
        return {
            "data": chart_data,
            "total_loss_formatted": f"${total_loss:,.0f} USD" # Formato: $-924...
        }

    except Exception as e:
        import traceback
        print(f"CRASH EN DESCUENTOS: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error procesando datos: {str(e)}")


# Para la pérdida neta real (Profit)
@app.get("/api/discount-margin-netimpact")
def get_discount_net_impact():
    if df_global is None: 
        raise HTTPException(status_code=503, detail="Memoria vacía")
    
    try:
        # 1. Trabajamos sobre una copia limpia
        df = df_global.copy()

        # 2. LIMPIEZA FORZADA DE DESCUENTO
        # Aseguramos que sea float. Si es string "10.00%", quitamos el %
        if df['Discount'].dtype == 'object':
            df['Discount'] = df['Discount'].astype(str).str.replace('%', '', regex=False)
            df['Discount'] = pd.to_numeric(df['Discount'], errors='coerce').fillna(0) / 100
        else:
            df['Discount'] = pd.to_numeric(df['Discount'], errors='coerce').fillna(0)

        # 3. DEFINICIÓN DE RANGOS (BINS)
        # Usamos un rango ligeramente superior a 1.0 (1.1) por si hay errores en el CSV
        bins = [-0.001, 0, 0.05, 0.10, 0.15, 0.20, 2.0] 
        labels = ["0%", "1-5%", "6-10%", "11-15%", "16-20%", "Más de 20%"]
        
        df['Discount_Group'] = pd.cut(df['Discount'], bins=bins, labels=labels)

        # 4. AGRUPACIÓN Y SUMA DE PROFIT
        # observed=False es necesario en versiones nuevas de pandas para categoric data
        impact = df.groupby('Discount_Group', observed=False)['Profit'].sum().reset_index()

        # 5. CÁLCULO DE PÉRDIDA TOTAL (Suma de los Profit negativos en los grupos)
        # Según tu imagen, nos interesa la pérdida en los grupos de alto descuento
        loss_df = impact[impact['Profit'] < 0]
        total_net_loss = float(loss_df['Profit'].sum())

        # 6. CONVERSIÓN A TIPOS NATIVOS (Vital para evitar Error 500)
        chart_net_data = []
        for _, row in impact.iterrows():
            chart_net_data.append({
                "group": str(row['Discount_Group']),
                "profit": round(float(row['Profit']), 2)
            })

        print(f">>> API Descuentos: Procesados {len(df)} registros. Profit: {total_net_loss}")
        
        return {
            "data": chart_net_data,
            "total_net_loss_formatted": f"${total_net_loss:,.0f} USD" # Formato: $-848,900.00
        }



    except Exception as e:
        import traceback
        print(f"CRASH EN DESCUENTOS: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error procesando datos: {str(e)}")



@app.get("/api/customers-analysis")
def get_customers_analysis():
    if df_global is None: 
        raise HTTPException(status_code=503, detail="Memoria vacía")
    
    try:
        df = df_global.copy()
        # Agrupación por Cliente
        c_data = df.groupby('Customer Name').agg({
            'Sales': 'sum', 
            'Profit': 'sum', 
            'Order ID': 'nunique'
        }).reset_index()
        
        c_data.columns = ['name', 'sales', 'profit', 'orders']

        # Función auxiliar para convertir filas de dataframe en listas seguras para JSON
        def sanitize_list(df_slice):
            return [
                {
                    "name": str(row['name']),
                    "sales": round(float(row['sales']), 2),
                    "profit": round(float(row['profit']), 2),
                    "orders": int(row.get('orders', 0))
                } for _, row in df_slice.iterrows()
            ]

        # Generación de los 4 Rankings
        top_profitable = sanitize_list(c_data.sort_values('profit', ascending=False).head(20))
        top_revenue = sanitize_list(c_data.sort_values('sales', ascending=False).head(20))
        bottom_profitable = sanitize_list(c_data.sort_values('profit', ascending=True).head(20))
        bottom_revenue = sanitize_list(c_data.sort_values('sales', ascending=True).head(20))
        
        # Muestra completa para el Scatter Plot
        segmentation = sanitize_list(c_data)

        print(">>> API Clientes: JSON construido con nombres estandarizados.")
        return {
            "topProfitable": top_profitable,
            "topRevenue": top_revenue,
            "bottomProfitable": bottom_profitable,
            "bottomRevenue": bottom_revenue,
            "segmentation": segmentation
        }
    except Exception as e:
        print(f"Error en Customers API: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# main.py - Actualiza este endpoint específico

@app.get("/api/countries-analysis")
def get_countries_analysis():
    if df_global is None: 
        raise HTTPException(status_code=503, detail="Memoria vacía")
    try:
        df = df_global.copy()
        # Agrupación base por país
        geo_data = df.groupby('Country').agg({
            'Sales': 'sum', 
            'Profit': 'sum', 
            'Shipping Cost': 'sum',
            'Order ID': 'count'
        }).reset_index()

        # 1. Separar el Outlier (Líder USA)
        sorted_geo = geo_data.sort_values('Sales', ascending=False)
        outlier_raw = sorted_geo.iloc[0]
        outlier_data = {
            "country": str(outlier_raw['Country']),
            "sales": float(outlier_raw['Sales']),
            "profit": float(outlier_raw['Profit']),
            "orders": int(outlier_raw['Order ID'])
        }

        # 2. Bubble Data (Top 50 sin USA)
        others = sorted_geo.iloc[1:51]
        bubble_data = [
            {
                "country": str(r['Country']),
                "sales": float(r['Sales']),
                "profit": float(r['Profit']),
                "orders": int(r['Order ID'])
            } for _, r in others.iterrows()
        ]

        # 3. RELACIÓN ENVÍO VS MARGEN (Tu Scatter solicitado)
        # Calculamos para todos los países para tener una nube completa
        shipping_relation = [
            {
                "country": str(row['Country']),
                "avg_shipping": round(float(row['Shipping Cost'] / row['Order ID']), 2),
                "profit_margin": round(float(row['Profit'] / row['Sales'] * 100), 2) if row['Sales'] != 0 else 0
            } for _, row in geo_data.iterrows()
        ]

        # 4. Rankings Inferiores
        bottom_countries = [{"country": str(r['Country']), "profit": float(r['Profit'])} 
                           for _, r in geo_data.sort_values('Profit').head(15).iterrows()]
        
        crit_cust = df.groupby(['Customer Name', 'Country'])['Profit'].sum().reset_index()
        critical_geo = crit_cust[crit_cust['Profit'] < 0].groupby('Country').size().reset_index(name='count').sort_values('count', ascending=False).head(15)
        critical_geo_list = [{"country": str(r['Country']), "count": int(r['count'])} for _, r in critical_geo.iterrows()]

        return {
            "outlier": outlier_data,
            "bubble_data": bubble_data,
            "shipping_relation": shipping_relation, 
            "bottom_countries": bottom_countries,
            "critical_geo": critical_geo_list
        }
    except Exception as e:
        print(f"Error en Países: {e}")
        raise HTTPException(status_code=500, detail=str(e))





