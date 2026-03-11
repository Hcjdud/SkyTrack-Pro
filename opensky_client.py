import requests
import time
from datetime import datetime
from cachetools import TTLCache

class OpenSkyClient:
    """Клиент для работы с OpenSky Network API"""
    
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires = 0
        self.base_url = 'https://opensky-network.org/api'
        
        # Кэши для оптимизации
        self.aircraft_cache = TTLCache(maxsize=10000, ttl=300)  # 5 минут
        self.details_cache = TTLCache(maxsize=5000, ttl=86400)  # 24 часа
        
    def get_token(self):
        """Получение OAuth2 токена"""
        if self.access_token and time.time() < self.token_expires:
            return self.access_token
            
        try:
            response = requests.post(
                'https://opensky-network.org/api/token',
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data['access_token']
                self.token_expires = time.time() + data['expires_in'] - 60
                return self.access_token
        except Exception as e:
            print(f"Token error: {e}")
            
        return None
    
    def get_all_flights(self):
        """Получение всех самолётов"""
        try:
            # Пробуем без токена (анонимный доступ)
            response = requests.get(
                f"{self.base_url}/states/all",
                params={'extended': '1'},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._process_flight_data(data)
            elif response.status_code == 429:
                return {'error': 'rate_limit', 'retry_after': 60}
            else:
                return {'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            print(f"Error fetching flights: {e}")
            return {'error': str(e)}
    
    def _process_flight_data(self, data):
        """Обработка данных о полётах"""
        states = data.get('states', [])
        enriched = []
        in_air_count = 0
        
        for state in states[:5000]:
            try:
                if len(state) < 18:
                    continue
                    
                if state[5] is None or state[6] is None:
                    continue
                
                # Конвертация высоты из метров в футы
                altitude_m = state[7] or 0
                altitude_ft = altitude_m * 3.28084
                
                # Конвертация скорости из м/с в узлы
                speed_ms = state[9] or 0
                speed_knots = speed_ms * 1.94384
                
                # Вертикальная скорость из м/с в фут/мин
                vertical_ms = state[11] or 0
                vertical_fpm = vertical_ms * 196.85
                
                on_ground = bool(state[8])
                if not on_ground:
                    in_air_count += 1
                
                flight = {
                    'icao24': state[0],
                    'callsign': state[1].strip() if state[1] else '-----',
                    'country': state[2] or 'Unknown',
                    'latitude': float(state[6]),
                    'longitude': float(state[5]),
                    'altitude': round(altitude_ft),
                    'velocity': round(speed_knots),
                    'heading': round(state[10] or 0),
                    'vertical_rate': round(vertical_fpm),
                    'on_ground': on_ground,
                    'squawk': state[14] or '----',
                    'timestamp': datetime.now().isoformat(),
                    'typecode': 'B738',
                    'model': 'Boeing 737',
                    'operator': 'Unknown',
                    'from': '???',
                    'to': '???'
                }
                
                enriched.append(flight)
                
                # Сохраняем трек
                if state[0] not in self.aircraft_cache:
                    self.aircraft_cache[state[0]] = []
                
                self.aircraft_cache[state[0]].append({
                    'lat': flight['latitude'],
                    'lon': flight['longitude'],
                    'alt': flight['altitude'],
                    'time': flight['timestamp']
                })
                
                if len(self.aircraft_cache[state[0]]) > 200:
                    self.aircraft_cache[state[0]].pop(0)
                    
            except Exception as e:
                continue
        
        return {
            'success': True,
            'flights': enriched,
            'total': len(enriched),
            'in_air': in_air_count,
            'on_ground': len(enriched) - in_air_count,
            'time': data.get('time', int(time.time()))
        }
    
    def get_flight_details(self, icao24):
        """Детальная информация о самолёте"""
        return {
            'manufacturer': 'Unknown',
            'model': 'Unknown',
            'typecode': '',
            'registration': '',
            'operator': 'Unknown',
            'built': 'Unknown'
        }
    
    def get_track(self, icao24):
        """Получение трека самолёта"""
        return self.aircraft_cache.get(icao24, [])
