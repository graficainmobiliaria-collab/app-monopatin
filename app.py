import streamlit as st
import pandas as pd
import datetime
import streamlit.components.v1 as components
from data_analyzer import get_performance_stats, get_pending_routes
from route_calculator import calculate_route_distance

st.set_page_config(
    page_title="Rutas Monopatín", 
    page_icon="🛴", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    div.stButton > button:first-child {
        background-color: #00C853; 
        color: white;
        border-radius: 12px;
        border: none;
        padding: 12px 24px;
        font-weight: bold;
        width: 100%; 
        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
    }
    div.stButton > button:first-child:hover {
        background-color: #00E676;
        transform: translateY(-2px);
    }
    div[data-testid="metric-container"] {
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 15px;
        padding: 15px;
        box-shadow: 2px 4px 10px rgba(0,0,0,0.05);
        text-align: center;
    }
    h1 { color: #00C853; }
</style>
""", unsafe_allow_html=True)

st.title("🛴 Monopatín Route Planner")
st.markdown("Calcula la viabilidad de tu ruta y la autonomía de batería de forma inteligente.")

st.sidebar.header("⚙️ Configuración")
historial_url = st.sidebar.text_input("URL Planilla Historial", value="https://docs.google.com/spreadsheets/d/1xDRFfCaykjw6r_moteOBU7IsoiwSpPnwH7k6VuRcNkg/edit#gid=85739281")
relevamientos_url = st.sidebar.text_input("URL Planilla Relevamientos", value="https://docs.google.com/spreadsheets/d/e/2PACX-1vTAi4PDT9o6QukcQwzEOr8H7CeUfoJxh6notUWT3IaYH5QGsMXv6yoLIJ6q0C9KBL0HSfwbeZyr0yZq/pubhtml?gid=1001&single=true")
relevamientos_sheet = st.sidebar.text_input("Nombre de la Pestaña", value="relevamientos soto")
origen = st.sidebar.text_input("📍 Punto de Origen/Fin", value="Miró 531, CABA, Argentina")
centro_carga = "Jorge Newbery 2564, CABA, Argentina" 
horas_carga_completa = st.sidebar.number_input("⏳ Tiempo carga 0-100% (hs)", value=2.5, step=0.5)

st.sidebar.markdown("---")
st.sidebar.subheader("🔌 Batería y Carga")
ir_centro_carga = st.sidebar.checkbox("Ir al Centro de Carga al final", value=False)

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Filtro de Viajes")
margen_desvio = st.sidebar.slider("Margen de Desvío Urbano (%)", min_value=0, max_value=60, value=28, step=1)
fecha_filtro = st.sidebar.date_input("Fecha a calcular", value=datetime.date(2026, 9, 16))
hora_inicio = st.sidebar.time_input("Hora desde", value=datetime.time(8, 0))
hora_fin = st.sidebar.time_input("Hora hasta", value=datetime.time(15, 0))

tab_planificador, tab_relevamientos, tab_historial, tab_gpx = st.tabs(["🚀 Planificador", "📝 Relevamientos", "📊 Historial", "📡 GPX"])

with tab_planificador:
    st.header("📈 1. Rendimiento Histórico")
    
    if st.button("Cargar Rendimiento del Monopatín"):
        with st.spinner("Analizando planilla de consumos..."):
            res = get_performance_stats(historial_url)
            if res['success']:
                st.session_state['max_range'] = res['max_range_km']
                st.session_state['efficiency'] = res['efficiency_km_per_percent']
                st.success("¡Historial de consumos cargado correctamente!")
                
                autonomia_util = res['max_range_km'] * 0.9
                st.session_state['autonomia_util'] = autonomia_util
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Autonomía Max (100%)", f"{res['max_range_km']:.1f} km")
                col2.metric("Autonomía Útil (90%)", f"{autonomia_util:.1f} km")
                col3.metric("Consumo", f"{res['efficiency_km_per_percent']:.3f} km/%")
                
                st.caption(f"ℹ️ Se analizaron {res['trips_analyzed']} viajes válidos.")
            else:
                st.error(f"Error cargando historial: {res['error']}")
    
    st.header("🗺️ 2. Planificar Ruta")
    if 'max_range' not in st.session_state:
        st.info("Primero carga el rendimiento histórico para poder calcular la viabilidad.")
    else:
        if st.button("Cargar Relevamientos y Calcular Ruta"):
            with st.spinner("Calculando ruta y dibujando mapa..."):
                res_rutas = get_pending_routes(
                    relevamientos_url, 
                    relevamientos_sheet, 
                    target_date=fecha_filtro.strftime('%Y-%m-%d'),
                    time_start=hora_inicio.strftime('%H:%M'),
                    time_end=hora_fin.strftime('%H:%M')
                )
                if res_rutas['success']:
                    st.write("**Paradas Encontradas:**")
                    for i, d in enumerate(res_rutas['addresses']):
                        st.write(f"{i+1}. {d}")
                    
                    # Armar ruta original sin centro de carga primero para evaluarla
                    ruta_original = [origen] + res_rutas['addresses'] + [origen]
                    res_orig = calculate_route_distance(ruta_original)
                    
                    if res_orig['success']:
                        dist_real_orig = res_orig['distance_km'] * (1 + margen_desvio / 100)
                        bateria_necesaria_orig = dist_real_orig / st.session_state['efficiency']
                        
                        # Si la batería necesaria es alta y el usuario pide ir al centro de carga
                        if ir_centro_carga:
                            # Buscar el punto medio del recorrido para sugerir parada
                            dist_acumulada = 0
                            mitad = res_orig['distance_km'] / 2
                            mejor_indice = 1 # Después de la primera parada por defecto
                            
                            for i, d_leg in enumerate(res_orig['leg_distances']):
                                dist_acumulada += d_leg
                                if dist_acumulada >= mitad:
                                    mejor_indice = i
                                    break
                                    
                            lugar_sugerido = "el Origen" if mejor_indice == 0 else f"la Parada {mejor_indice}"
                            
                            # Insertar el centro de carga en la ruta real
                            ruta_completa = [origen] + res_rutas['addresses']
                            ruta_completa.insert(mejor_indice + 1, centro_carga)
                            ruta_completa.append(origen)
                            
                            st.info(f"🤖 **Sugerencia Logística:** Para optimizar la batería, te conviene pasar por el Centro de Cargas (Jorge Newbery) **después de {lugar_sugerido}**.")
                        else:
                            ruta_completa = ruta_original
                            
                        res_dist = calculate_route_distance(ruta_completa)
                        
                        if res_dist['success']:
                            dist_real = res_dist['distance_km'] * (1 + margen_desvio / 100)
                            st.write("---")
                            st.subheader("📊 Resultado de Viabilidad")
                            
                            col_a, col_b, col_c = st.columns(3)
                            col_a.metric("Distancia Real Estimada", f"{dist_real:.1f} km")
                            bateria_necesaria = dist_real / st.session_state['efficiency']
                            col_b.metric("Batería a Consumir Total", f"{bateria_necesaria:.1f} %")
                            
                            # CÁLCULO INTELIGENTE DE RECARGA
                            # Solo cargamos lo que falta para llegar a casa + 10% de margen de seguridad
                            bateria_faltante = bateria_necesaria - 100
                            
                            if bateria_faltante > 0:
                                bateria_a_recargar = bateria_faltante + 10 # 10% de seguridad
                                msg_carga = f"Recargar {bateria_a_recargar:.1f}% para llegar"
                            else:
                                bateria_a_recargar = 20 # Si eligió cargar por gusto, top-up del 20%
                                msg_carga = "Recarga preventiva (20%)"
                                
                            horas_recarga = (bateria_a_recargar / 100) * horas_carga_completa
                            minutos_recarga = int(horas_recarga * 60)
                            
                            if ir_centro_carga:
                                col_c.metric(msg_carga, f"{minutos_recarga} min")
                            
                            if bateria_necesaria > 100 and not ir_centro_carga:
                                st.error("❌ Imposible realizar la ruta. Necesitás tildar 'Ir al Centro de Carga'.")
                            elif bateria_necesaria > 80 and not ir_centro_carga:
                                st.warning(f"⚠️ Llegarías muy justo (consumís {bateria_necesaria:.1f}%). Considerá cargar.")
                            else:
                                st.success("✅ Ruta viable con este plan logístico.")
                                
                            # DIBUJAR EL MAPA
                            st.write("---")
                            st.subheader("🗺️ Mapa Interactivo del Recorrido")
                        try:
                            import folium
                            
                            start_loc = res_dist['waypoints'][0]
                            m = folium.Map(location=start_loc, zoom_start=13)
                            
                            # Línea de la ruta
                            folium.PolyLine(res_dist['route_path'], color="#00C853", weight=5, opacity=0.8).add_to(m)
                            
                            # Marcadores
                            for i, wp in enumerate(res_dist['waypoints']):
                                if i == 0 or i == len(res_dist['waypoints'])-1:
                                    label = "Origen / Fin"
                                    color = "blue"
                                elif ir_centro_carga and i == len(res_dist['waypoints'])-2:
                                    label = "Centro de Carga"
                                    color = "orange"
                                else:
                                    label = f"Parada {i}"
                                    color = "red"
                                folium.Marker(wp, popup=label, tooltip=label, icon=folium.Icon(color=color)).add_to(m)
                                
                            # Usamos components.html en lugar de st_folium para que el mapa no reinicie la página
                            components.html(m._repr_html_(), height=500)
                        except Exception as e:
                            st.error("No se pudo cargar el mapa. Asegurate de tener instalado folium.")
                    else:
                        st.error(f"Error calculando la ruta: {res_dist.get('error', 'Error desconocido')}")
                else:
                    st.error(f"⚠️ {res_rutas['error']}")

def format_iframe_url(url):
    if '/pubhtml' in url:
        if 'widget=true' not in url:
            separator = '&' if '?' in url else '?'
            return f"{url}{separator}widget=true&headers=false"
        return url
    if 'rm=minimal' not in url:
        if '?' in url: url = url.replace('?', '?rm=minimal&')
        elif '#' in url: url = url.replace('#', '?rm=minimal#')
        else: url = url + '?rm=minimal'
    return url

with tab_relevamientos:
    st.info("Planilla de Relevamientos.")
    components.iframe(format_iframe_url(relevamientos_url), height=700, scrolling=True)

with tab_historial:
    st.info("Planilla Excel Histórica de Consumo.")
    components.iframe(format_iframe_url(historial_url), height=700, scrolling=True)

with tab_gpx:
    import os
    st.header("📡 Laboratorio GPX")
    st.info("Tus archivos GPX se cargan automáticamente desde la carpeta del Escritorio.")
    
    gpx_folder = r"C:\Users\sergi\Desktop\scratch\Rutas_Monopatin"
    
    if os.path.exists(gpx_folder):
        gpx_files = [f for f in os.listdir(gpx_folder) if f.lower().endswith('.gpx')]
        if gpx_files:
            selected_gpx = st.selectbox("Selecciona un recorrido:", ["-- Elegí una ruta --"] + gpx_files)
            if selected_gpx != "-- Elegí una ruta --":
                st.success(f"Ruta seleccionada: {selected_gpx}")
                # Aquí más adelante procesaremos el mapa
        else:
            st.warning("La carpeta 'Rutas_Monopatin' está vacía. Guardá ahí tus bajadas de Strava.")
    else:
        st.error("No encontré la carpeta 'Rutas_Monopatin' en tu Escritorio.")