import urllib.request
import urllib.parse
import json
import time
import ssl

from geopy.geocoders import ArcGIS

def get_coordinates(address):
    geolocator = ArcGIS(user_agent="MonopatinApp_1.0")
    try:
        location = geolocator.geocode(address)
        if location:
            return location.longitude, location.latitude
    except Exception as e:
        print(f"Error geocoding {address}: {e}")
    return None

def calculate_route_distance(addresses):
    coords = []
    for addr in addresses:
        c = get_coordinates(addr)
        if c:
            coords.append(c)
        else:
            return {'success': False, 'error': f'No se pudo encontrar: {addr}'}
        time.sleep(1) # Polite delay
        
    coords_str = ';'.join([f'{c[0]},{c[1]}' for c in coords])
    # Pedir geometry en formato geojson para poder dibujarla en el mapa
    osrm_url = f'http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson'
    
    try:
        req = urllib.request.Request(osrm_url, headers={'User-Agent': 'MonopatinApp/1.0'})
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        
        if data['code'] == 'Ok':
            dist_m = data['routes'][0]['distance']
            dur_s = data['routes'][0]['duration']
            
            # Extraer la geometría de la ruta y los waypoints
            # OSRM devuelve [lon, lat], para Folium necesitamos [lat, lon]
            geometry_coords = data['routes'][0]['geometry']['coordinates']
            route_path = [[coord[1], coord[0]] for coord in geometry_coords]
            waypoints = [[c[1], c[0]] for c in coords]
            
            return {
                'success': True, 
                'distance_km': dist_m / 1000,
                'duration_min': dur_s / 60,
                'route_path': route_path,
                'waypoints': waypoints
            }
        else:
            return {'success': False, 'error': data.get('message', 'Error en OSRM')}
    except Exception as e:
        return {'success': False, 'error': str(e)}
