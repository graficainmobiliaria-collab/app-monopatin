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
    osrm_url = f'http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=false'
    
    try:
        req = urllib.request.Request(osrm_url, headers={'User-Agent': 'MonopatinApp/1.0'})
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        
        if data['code'] == 'Ok':
            dist_m = data['routes'][0]['distance']
            dur_s = data['routes'][0]['duration']
            return {
                'success': True, 
                'distance_km': dist_m / 1000,
                'duration_min': dur_s / 60
            }
        else:
            return {'success': False, 'error': data.get('message', 'Error en OSRM')}
    except Exception as e:
        return {'success': False, 'error': str(e)}
