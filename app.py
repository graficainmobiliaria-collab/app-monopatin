import streamlit as st
import pandas as pd
from data_analyzer import get_performance_stats, get_pending_routes
from route_calculator import calculate_route_distance

st.set_page_config(page_title="Monopatin Route Planner", page_icon="🛴", layout="centered")

st.title("🛴 Monopatín Route Planner")
st.markdown("Calcula si tu monopatín tiene suficiente batería para los relevamientos del día.")

import datetime

import streamlit.components.v1 as components

# --- SIDEBAR CONFIGURACIÓN ---
st.sidebar.header("⚙️ Configuración")
historial_url = st.sidebar.text_input("URL Planilla Historial", value="https://docs.google.com/spreadsheets/d/1xDRFfCaykjw6r_moteOBU7IsoiwSpPnwH7k6VuRcNkg/edit#gid=85739281")
relevamientos_url = st.sidebar.text_input("URL Planilla Relevamientos", value="https://docs.google.com/spreadsheets/d/e/2PACX-1vTAi4PDT9o6QukcQwzEOr8H7CeUfoJxh6notUWT3IaYH5QGsMXv6yoLIJ6q0C9KBL0HSfwbeZyr0yZq/pubhtml?gid=1001&single=true")
relevamientos_sheet = st.sidebar.text_input("Nombre de la Pestaña", value="relevamientos soto")
origen = st.sidebar.text_input("📍 Punto de Origen/Fin", value="Miró 531, CABA, Argentina")

st.sidebar.markdown("---")
st.sidebar.subheader("📅 Filtro de Viajes")
fecha_filtro = st.sidebar.date_input("Fecha a calcular", value=datetime.date(2026, 9, 16))
hora_inicio = st.sidebar.time_input("Hora desde", value=datetime.time(8, 0))
hora_fin = st.sidebar.time_input("Hora hasta", value=datetime.time(15, 0))

# --- PESTAÑAS (TABS) ---
tab_planificador, tab_relevamientos, tab_historial = st.tabs(["🗺️ Planificador", "📝 Relevamientos (Sheets)", "🔋 Historial (Sheets)"])

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
                
                # Cálculo de autonomía útil (reservando el último 10%)
                autonomia_util = res['max_range_km'] * 0.9
                st.session_state['autonomia_util'] = autonomia_util
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Autonomía Max (100%)", f"{res['max_range_km']:.1f} km")
                col2.metric("Autonomía Útil (90%)", f"{autonomia_util:.1f} km", help="Rango óptimo antes de que el monopatín pierda rendimiento (al bajar del 10% de batería).")
                col3.metric("Consumo", f"{res['efficiency_km_per_percent']:.3f} km/%")
                
                st.caption(f"📊 Se analizaron {res['trips_analyzed']} viajes válidos. Se descartaron automáticamente {res['trips_discarded']} registros anómalos o extremos.")
            else:
                st.error(f"Error cargando historial: {res['error']}")
    
    # --- PASO 2: RUTA ---
    st.header("🗺️ 2. Planificar Ruta")
    
    if 'max_range' not in st.session_state:
        st.info("Primero carga el rendimiento histórico para poder calcular la viabilidad.")
    else:
        if st.button("Cargar Relevamientos y Calcular Ruta"):
            with st.spinner("Leyendo relevamientos y calculando ruta..."):
                # Convertir a string para pasarlo
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
                    
                    # Armar ruta completa
                    ruta_completa = [origen] + direcciones + [origen]
                    
                    # Calcular distancias
                    res_dist = calculate_route_distance(ruta_completa)
                    
                    if res_dist['success']:
                        dist = res_dist['distance_km']
                        st.write("---")
                        st.subheader("🏁 Resultado de Viabilidad")
                        st.metric("Distancia Total de la Ruta", f"{dist:.1f} km")
                        
                        bateria_necesaria = dist / st.session_state['efficiency']
                        st.metric("Batería Estimada a Consumir", f"{bateria_necesaria:.1f} %")
                        
                        bateria_restante = 100 - bateria_necesaria
                        
                        if bateria_necesaria > 100:
                            st.error("🚨 Imposible realizar la ruta sin cargar el monopatín. ¡La distancia supera la capacidad total de la batería!")
                        elif bateria_necesaria > 90:
                            st.warning(f"⚠️ Alerta: El viaje consumirá el {bateria_necesaria:.1f}% de la batería. Llegarías con un {bateria_restante:.1f}%, entrando en la zona de pérdida de prestaciones (< 10%). ¡Te recomendamos cargar en el camino!")
                        elif bateria_necesaria > 80:
                            st.info(f"ℹ️ Viaje viable, pero justo. Llegarías con un {bateria_restante:.1f}%. Usar modo Eco para asegurar no caer por debajo del 10%.")
                        else:
                            st.success(f"✅ Ruta viable. Llegarías cómodamente con un {bateria_restante:.1f}% de batería (manteniendo el rendimiento óptimo).")
                            
                    else:
                        st.error(f"Error calculando la ruta con el mapa: {res_dist['error']}")
                else:
                    st.error(f"Error cargando relevamientos: {res_rutas['error']}")

def format_iframe_url(url):
    # Si ya es un enlace publicado en la web (pubhtml), lo dejamos como está o le aseguramos widget=true
    if '/pubhtml' in url:
        if 'widget=true' not in url:
            separator = '&' if '?' in url else '?'
            return f"{url}{separator}widget=true&headers=false"
        return url
        
    # Google bloquea htmlembed por seguridad en algunos navegadores si no está publicado en la web.
    # La solución oficial es usar el editor normal pero con rm=minimal (Render Mode = Minimal)
    if 'rm=minimal' not in url:
        if '?' in url:
            url = url.replace('?', '?rm=minimal&')
        elif '#' in url:
            url = url.replace('#', '?rm=minimal#')
        else:
            url = url + '?rm=minimal'
            
    return url

with tab_relevamientos:
    st.info("Desde aquí podés ver y editar tu planilla de relevamientos directamente.")
    iframe_rel = format_iframe_url(relevamientos_url)
    components.iframe(iframe_rel, height=700, scrolling=True)

with tab_historial:
    st.info("Desde aquí podés ver y editar tu historial de viajes y consumo.")
    iframe_hist = format_iframe_url(historial_url)
    components.iframe(iframe_hist, height=700, scrolling=True)
