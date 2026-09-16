import pandas as pd
import urllib.request
import urllib.parse

def get_performance_stats(url):
    """
    Descarga y procesa el historial de viajes para obtener 
    el promedio de km recorridos por 1% de batería.
    """
    try:
        # Extraer el ID del documento para armar la URL
        import re
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
        if not match:
            return {'success': False, 'error': 'URL inválida.'}
        
        doc_id = match.group(1)
        # Buscar si hay un gid específico en la URL (para la hoja del historial)
        gid_match = re.search(r'gid=([0-9]+)', url)
        gid_param = f"&gid={gid_match.group(1)}" if gid_match else ""
        
        clean_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv{gid_param}"
            
        df = pd.read_csv(clean_url)
        
        # Filtrar filas vacas y buscar la cabecera real
        # En la planilla de ejemplo, la cabecera estaba en la fila 7 (index 6)
        # Haremos una bsqueda dinmica de la columna 'Distancia'
        header_idx = None
        for i, row in df.iterrows():
            if 'Distancia' in str(row.values) or 'Distancia' in df.columns:
                header_idx = i
                break
                
        if header_idx is not None and not 'Distancia' in df.columns:
            df.columns = df.iloc[header_idx]
            df = df[header_idx+1:]
            
        # Nos quedamos con las columnas que nos importan
        if 'Distancia' in df.columns and 'Batería' in df.columns and 'Batería Restante' in df.columns:
            # Limpiar datos
            df['dist_km'] = df['Distancia'].astype(str).str.replace('km', '').str.replace(',', '.').str.strip()
            df['dist_km'] = pd.to_numeric(df['dist_km'], errors='coerce')
            
            df['bat_start'] = df['Batería'].astype(str).str.replace('%', '').str.strip()
            df['bat_start'] = pd.to_numeric(df['bat_start'], errors='coerce')
            
            df['bat_end'] = df['Batería Restante'].astype(str).str.replace('%', '').str.strip()
            df['bat_end'] = pd.to_numeric(df['bat_end'], errors='coerce')
            
            # Limpiar NaNs
            df = df.dropna(subset=['dist_km', 'bat_start', 'bat_end'])
            
            df['bat_used'] = df['bat_start'] - df['bat_end']
            
            # Filtrar filas donde la batería consumida sea <= 0 para evitar divisiones por cero
            df = df[df['bat_used'] > 0]
            
            # Calcular el rendimiento por viaje (km por 1% de batería)
            df['rendimiento'] = df['dist_km'] / df['bat_used']
            
            # Eliminar outliers (valores atípicos): viajes donde te olvidaste anotar un tramo
            # Usaremos los cuantiles 10% y 90% para descartar los viajes con rendimientos extremos
            q_low = df['rendimiento'].quantile(0.10)
            q_hi  = df['rendimiento'].quantile(0.90)
            
            df_filtered = df[(df['rendimiento'] >= q_low) & (df['rendimiento'] <= q_hi)]
            
            total_dist = df_filtered['dist_km'].sum()
            total_bat = df_filtered['bat_used'].sum()
            
            if total_bat > 0:
                avg_efficiency = total_dist / total_bat
                return {
                    'success': True,
                    'efficiency_km_per_percent': avg_efficiency,
                    'max_range_km': avg_efficiency * 100,
                    'trips_analyzed': len(df_filtered),
                    'trips_discarded': len(df) - len(df_filtered)
                }
        return {'success': False, 'error': 'No se encontraron las columnas necesarias'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_pending_routes(url, sheet_name='relevamientos soto', target_date=None, time_start=None, time_end=None):
    """
    Descarga la planilla de relevamientos pendientes.
    """
    try:
        import re
        # Si es un enlace publicado en la web (/d/e/...)
        if '/d/e/' in url:
            match = re.search(r'/d/e/([a-zA-Z0-9-_]+)', url)
            if not match:
                return {'success': False, 'error': 'URL publicada inválida.'}
            doc_id = match.group(1)
            # Para exportar un enlace publicado en la web se usa pub?output=xlsx
            export_url = f"https://docs.google.com/spreadsheets/d/e/{doc_id}/pub?output=xlsx"
        else:
            match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
            if not match:
                return {'success': False, 'error': 'URL inválida. No se encontró el ID del documento.'}
            
            doc_id = match.group(1)
            export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=xlsx"
            
        # Descargamos como excel y leemos la hoja específica
        try:
            df = pd.read_excel(export_url, sheet_name=sheet_name, engine='openpyxl')
        except Exception as e:
            # Si falla al buscar por nombre de pestaña en un archivo publicado, intentamos leer la primer hoja disponible
            # ya que a veces los pub?output=xlsx de una sola hoja pierden el nombre de la pestaña original
            if '/d/e/' in url:
                df = pd.read_excel(export_url, engine='openpyxl')
            else:
                raise e
        
        # Asumiendo que la primera fila o la segunda tiene la palabra "direcion" o "dirección"
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # En la hoja soto, vimos 'cliente', 'direcion', 'fecha visita', 'hora'
        col_dir = None
        col_hora = None
        col_fecha = None
        for col in df.columns:
            if 'direci' in col or 'direcc' in col: col_dir = col
            if 'hora' in col: col_hora = col
            if 'fecha' in col: col_fecha = col
            
        if col_dir:
            # Filtrar vacios
            df = df.dropna(subset=[col_dir])
            
            # Filtro por fecha si el usuario lo solicita
            if target_date and col_fecha:
                # Convertimos las fechas de Excel a formato texto (AAAA-MM-DD) para comparar fácil
                df['fecha_str'] = pd.to_datetime(df[col_fecha], errors='coerce').dt.strftime('%Y-%m-%d')
                df = df[df['fecha_str'] == str(target_date)]
                
                if df.empty:
                    return {'success': False, 'error': f'No hay relevamientos agendados para la fecha seleccionada ({target_date}).'}
            
            # Filtro por rango horario
            if time_start and time_end and col_hora:
                def parse_time(val):
                    if pd.isna(val): return ''
                    try:
                        if hasattr(val, 'strftime'):
                            return val.strftime('%H:%M')
                        val_str = str(val).strip()
                        if len(val_str) >= 4 and ':' in val_str:
                            parts = val_str.split(':')
                            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
                        return ''
                    except:
                        return ''
                
                df['hora_str'] = df[col_hora].apply(parse_time)
                # Conservar solo los que están en el rango
                df = df[(df['hora_str'] >= time_start) & (df['hora_str'] <= time_end) & (df['hora_str'] != '')]
                
                if df.empty:
                    return {'success': False, 'error': f'No hay relevamientos agendados entre las {time_start} y las {time_end}.'}
            
            # Ordenar por hora si existe
            if col_hora:
                if 'hora_str' in df.columns:
                    df = df.sort_values(by='hora_str')
                else:
                    df = df.sort_values(by=col_hora)
            
            addresses = df[col_dir].tolist()
            # Limpiar de textos extras (como pisos), dejamos la calle y numero
            clean_addresses = []
            for a in addresses:
                a_str = str(a).split('-')[0].split(',')[0].strip()
                a_lower = a_str.lower()
                
                # Cortar palabras clave que confunden al mapa
                for kw in [' piso', ' depto', ' dpto', ' pb', ' planta', ' departamento', ' ph', ' of ', ' oficina', ' local']:
                    idx = a_lower.find(kw)
                    if idx != -1:
                        a_str = a_str[:idx]
                        a_lower = a_str.lower()
                        
                clean_addresses.append(a_str.strip() + ", CABA, Argentina")
                
            return {'success': True, 'addresses': clean_addresses, 'raw_data': df}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}
    return {'success': False, 'error': 'Estructura no reconocida'}
