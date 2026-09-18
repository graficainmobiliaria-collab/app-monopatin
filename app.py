import streamlit as st
import pandas as pd
import datetime
import streamlit.components.v1 as components
from data_analyzer import get_performance_stats, get_pending_routes
from route_calculator import calculate_route_distance

# Configuración inicial de la página (debe ser el primer comando)
st.set_page_config(
    page_title="Rutas Monopatín", 
    page_icon="🛴", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS PERSONALIZADO ---
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
    h1 {
        color: #00C853;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛴 Monopatín Route Planner")
st.markdown("Calcula la viabilidad de tu ruta y la autonomía de batería con inteligencia de desvíos.")

# --- SIDEBAR CONFIGURACIÓN ---
st.sidebar.header("⚙️ Configuración")
historial_url = st.sidebar.text_input("URL Planilla Historial", value="https://docs.google.com/spreadsheets/d/1xDRFfCaykjw6r_moteOBU7IsoiwSpPnwH7k6VuRcNkg/edit#gid=85739281")
relevamientos_url = st.sidebar.text_input("URL Planilla Relevamientos", value="https://docs.google.com/spreadsheets/d/e/2PACX-1vTAi4PDT9o6QukcQwzEOr8H7CeUfoJxh6notUWT3IaYH5QGsMXv6yoLIJ6q0C9KBL0HSfwbeZyr0yZq/pubhtml?gid=1001&single=true")
relevamientos_sheet = st.sidebar.text_input("Nombre de la Pestaña", value="relevamientos soto")
origen = st.sidebar.text_input("📍 Punto de Origen/Fin", value="Miró 531, CABA, Argentina")

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Ajuste de Realidad")
margen_seguridad = st.sidebar.slider("Margen de Desvío Urbano (%)", min_value=0, max_value=100, value=30, help="Agrega un porcentaje extra a la distancia del mapa para compensar semáforos, calles cortadas y atajos en la vida real.")

st.sidebar.markdown("---")
st.sidebar.subheader("📅 Filtro de Viajes")
fecha_filtro = st.sidebar.date_input("Fecha a calcular", value=datetime.date(2026, 9, 16))
hora_inicio = st.sidebar.time_input("Hora desde", value=datetime.time(8, 0))
hora_fin = st.sidebar.time_input("Hora hasta", value=datetime.time(15, 0))

# --- PESTAÑAS (TABS) ---
tab_planificador, tab_relevamientos, tab_historial = st.tabs(["🗺️ Planificador", "📝 Relevamientos", "🔋 Historial"])

with tab_planificador:
    # --- PASO 1: RENDIMIENTO ---
    st.header("📊 1. Rendimiento Histórico")
    
    if st.button("Cargar Rendimiento"):
        with st.spinner("Analizando planilla de historial..."):
            res = get_performance_stats(historial_url)
            if res['success']:
                st.session_state['max_range'] = res['max_range_km']
                st.session_state['efficiency'] = res['efficiency_km_per_percent']
                st.success("Historial cargado correctamente!")
                
                autonomia_util = res['max_range_km'] * 0.9
                st.session_state['autonomia_util'] = autonomia_util
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Autonomía Max", f"{res['max_range_km']:.1f} km")
                col2.metric("Autonomía Útil (90%)", f"{autonomia_util:.1f} km")
                col3.metric("Consumo", f"{res['efficiency_km_per_percent']:.3f} km/%")
                
                st.caption(f"📊 Se analizaron {res['trips_analyzed']} viajes válidos.")
            else:
                st.error(f"Error cargando historial: {res['error']}")
    
    # --- PASO 2: RUTA ---
    st.header("🗺️ 2. Planificar Ruta")
    
    if 'max_range' not in st.session_state:
        st.info("Primero carga el rendimiento histórico para calcular la viabilidad.")
    else:
        if st.button("Cargar Relevamientos y Calcular Ruta"):
            with st.spinner("Leyendo relevamientos y calculando ruta..."):
                fecha_str = fecha_filtro.strftime('%Y-%m-%d')
                hora_inicio_str = hora_inicio.strftime('%H:%M')
                hora_fin_str = hora_fin.strftime('%H:%M')
                
                res_rutas = get_pending_routes(
                    relevamientos_url, 
                    relevamientos_sheet, 
                    target_date=fecha_str,
                    time_start=hora_inicio_str,
                    time_end=hora_fin_str
                )
                
                if res_rutas['success']:
                    direcciones = res_rutas['addresses']
                    st.write("**Paradas Encontradas:**")
                    for i, d in enumerate(direcciones):
                        st.write(f"{i+1}. {d}")
                    
                    ruta_completa = [origen] + direcciones + [origen]
                    res_dist = calculate_route_distance(ruta_completa)
                    
                    if res_dist['success']:
                        dist_teorica = res_dist['distance_km']
                        # APLICAMOS EL FACTOR DE DESVÍO DE LA VIDA REAL
                        dist_real = dist_teorica * (1 + (margen_seguridad / 100))
                        
                        st.write("---")
                        st.subheader("🏁 Resultado de Viabilidad (Ajustado)")
                        
                        colA, colB = st.columns(2)
                        colA.metric("Distancia Mapa (Teórica)", f"{dist_teorica:.1f} km")
                        colB.metric(f"Distancia Real (+{margen_seguridad}%)", f"{dist_real:.1f} km")
                        
                        bateria_necesaria = dist_real / st.session_state['efficiency']
                        st.metric("Batería Estimada a Consumir", f"{bateria_necesaria:.1f} %")
                        
                        bateria_restante = 100 - bateria_necesaria
                        
                        if bateria_necesaria > 100:
                            st.error("🚨 Imposible realizar la ruta sin cargar el monopatín. ¡Supera el 100%!")
                        elif bateria_necesaria > 90:
                            st.warning(f"⚠️ Alerta: Consumirá {bateria_necesaria:.1f}%. Llegás con {bateria_restante:.1f}% (zona de pérdida de prestaciones).")
                        elif bateria_necesaria > 80:
                            st.info(f"ℹ️ Viaje viable, pero justo. Llegarías con {bateria_restante:.1f}%.")
                        else:
                            st.success(f"✅ Ruta viable. Llegarías con un {bateria_restante:.1f}% de batería.")
                            
                        st.markdown("---")
                        st.subheader("💡 Modo de Manejo Sugerido")
                        if bateria_necesaria > 80:
                            st.info("**Modo Normal (ECO) 🐢**\nPara asegurar no caer por debajo del 10%.")
                        elif bateria_necesaria > 40:
                            st.info("**Modo Mixto ⚖️**\nAlterná entre Normal y Sport según el tráfico.")
                        else:
                            st.success("**Modo Sport 🏎️**\n¡Ruta corta! Andá a fondo sin problemas.")
                            
                        st.markdown("---")
                        st.subheader("🗺️ Mapa de la Ruta Teórica")
                        import folium
                        
                        m = folium.Map(location=res_dist['waypoints'][0], zoom_start=13)
                        folium.PolyLine(res_dist['route_path'], color="#00C853", weight=5, opacity=0.8).add_to(m)
                        
                        for idx, wp in enumerate(res_dist['waypoints']):
                            if idx == 0 or idx == len(res_dist['waypoints']) - 1:
                                folium.Marker(wp, icon=folium.Icon(color='green', icon='home'), tooltip="Origen/Fin").add_to(m)
                            else:
                                folium.Marker(wp, icon=folium.Icon(color='blue', icon='info-sign'), tooltip=f"Parada {idx}").add_to(m)
                                
                        components.html(m._repr_html_(), height=520)
                        
                    else:
                        st.error(f"Error calculando ruta: {res_dist['error']}")
                else:
                    st.error(f"Error cargando relevamientos: {res_rutas['error']}")

def format_iframe_url(url):
    if '/pubhtml' in url:
        if 'widget=true' not in url:
            separator = '&' if '?' in url else '?'
            return f"{url}{separator}widget=true&headers=false"
        return url
    if 'rm=minimal' not in url:
        if '?' in url:
            url = url.replace('?', '?rm=minimal&')
        elif '#' in url:
            url = url.replace('#', '?rm=minimal#')
        else:
            url = url + '?rm=minimal'
    return url

with tab_relevamientos:
    st.info("Desde aquí podés ver y editar tu planilla de relevamientos.")
    components.iframe(format_iframe_url(relevamientos_url), height=700, scrolling=True)

with tab_historial:
    st.info("Desde aquí podés ver y editar tu historial.")
    components.iframe(format_iframe_url(historial_url), height=700, scrolling=True)
