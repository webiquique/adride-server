from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import datetime
import requests
from werkzeug.utils import secure_filename

# ✅ CONFIGURACIÓN DE API DE CLIMA
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")
OPENWEATHER_CITY = "Iquique"
CLIMA_CACHE = None  # Cache para no llamar a la API en cada petición
CLIMA_CACHE_TIME = None
CACHE_DURATION_MIN = 5  # Cache por 30 minutos

app = Flask(__name__, static_folder='.')
CORS(app)

# ✅ CONFIGURACIÓN PARA SUBIDA DE ARCHIVOS
UPLOAD_FOLDER = 'uploads/documentos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB máximo por foto
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

# Archivos de datos
DATA_FILE = 'tablets_data.json'
KM_FILE = 'km_reports.json'
PAGOS_FILE = 'pagos_conductores.json'
DOCUMENTOS_FILE = 'documentos_conductores.json'

# Variables globales
tablets_data = {}
km_reports = {}
pagos_conductores = {}
documentos_conductores = {}

# ✅ CONFIGURACIÓN DE NEGOCIO ADRIDE - MODELO 25% + 5% BONO
config = {
    "valor_por_impresion": 30,  # $30 CLP revenue por impresión
    "porcentaje_base_conductor": 0.25,  # 25% base garantizado
    "porcentaje_bono_maximo": 0.05,  # Hasta 5% bono por desempeño
    "porcentaje_maximo_total": 0.30,  # Tope máximo: 30%
    
    # ✅ Métricas para bono (0% a 5%)
    "km_minimos_bono": 50,  # +1.5% si ≥ 50 km/día
    "impresiones_minimas_bono": 100,  # +1.5% si ≥ 100 impresiones/día
    "bono_documentos_aprobados": 0.01,  # +1.0% si todos aprobados
    "bono_conectividad_estable": 0.01,  # +1.0% si heartbeat estable
    "bono_km_porcentaje": 0.015,  # 1.5%
    "bono_impresiones_porcentaje": 0.015  # 1.5%
}

# ✅ CONFIGURACIÓN LEGACY (para compatibilidad con dashboard actual)
config["tarifa_km"] = 15
config["tarifa_hora_activa"] = 500
config["presupuesto_total_mensual"] = 250000
config["porcentaje_para_conductores"] = 0.40
config["porcentaje_para_adride"] = 0.60
config["dias_mes"] = 30
config["bono_horas_pico_porcentaje"] = 0.20

fondo_conductores_mensual = config["presupuesto_total_mensual"] * config["porcentaje_para_conductores"]
fondo_conductores_diario = fondo_conductores_mensual / config["dias_mes"]

# ✅ FUNCIÓN AUXILIAR: Verificar extensión de archivo
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cargar_datos():
    """Carga todos los datos desde archivos JSON al iniciar"""
    global tablets_data, km_reports, pagos_conductores, documentos_conductores
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                tablets_data = json.loads(content) if content else {}
            print(f"✅ Tablets cargadas: {len(tablets_data)}")
        
        if os.path.exists(KM_FILE):
            with open(KM_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                km_reports = json.loads(content) if content else {}
            print(f"✅ Reportes de km cargados: {len(km_reports)}")
        
        if os.path.exists(PAGOS_FILE):
            with open(PAGOS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                pagos_conductores = json.loads(content) if content else {}
            print(f"✅ Pagos cargados: {len(pagos_conductores)}")
        
        if os.path.exists(DOCUMENTOS_FILE):
            with open(DOCUMENTOS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                documentos_conductores = json.loads(content) if content else {}
            print(f"✅ Documentos cargados: {len(documentos_conductores)}")
    except Exception as e:
        print(f"⚠️ Error cargando datos: {e}")
        tablets_data = {}
        km_reports = {}
        pagos_conductores = {}
        documentos_conductores = {}

def guardar_datos():
    """Guarda todos los datos en archivos JSON"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(tablets_data, f, indent=2, ensure_ascii=False)
        with open(KM_FILE, 'w', encoding='utf-8') as f:
            json.dump(km_reports, f, indent=2, ensure_ascii=False)
        with open(PAGOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(pagos_conductores, f, indent=2, ensure_ascii=False)
        with open(DOCUMENTOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(documentos_conductores, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error guardando datos: {e}")

# ✅ HELPER: Calcular bono por desempeño (0.0 a 0.05)

def calcular_bono_desempeno(conductor_id, data):
    """
    Calcula porcentaje de bono (0% a 5%) según métricas del chofer.
    Retorna valor entre 0.0 y 0.05
    """
    bono = 0.0
    
    # 📍 Métrica 1: Kilómetros mínimos (+1.5%)
    # ✅ Usar km_reports para obtener acumulados del día actual
    fecha_hoy = datetime.datetime.now().strftime('%Y-%m-%d')
    km_acumulados = km_reports.get(conductor_id, {}).get(fecha_hoy, 0)
    
    if km_acumulados >= config["km_minimos_bono"]:  # ≥ 50 km
        bono += config["bono_km_porcentaje"]
        print(f"📍 Bono km aplicado: {conductor_id[:12]}... | Km hoy: {km_acumulados}")
    
    # 📺 Métrica 2: Volumen de impresiones (+1.5%)
    total_impressions = int(data.get('total_impressions', 0) or 0)
    if total_impressions >= config["impresiones_minimas_bono"]:  # ≥ 100
        bono += config["bono_impresiones_porcentaje"]
    
    # 📄 Métrica 3: Documentos aprobados (+1.0%)
    if conductor_id in documentos_conductores:
        docs = documentos_conductores[conductor_id]
        if docs and all(doc.get('estado') == 'aprobado' for doc in docs.values()):
            bono += config["bono_documentos_aprobados"]
    
    # ❤️ Métrica 4: Conectividad estable (+1.0%)
    last_seen = data.get('last_seen', 0)
    if last_seen:
        try:
            ahora = datetime.datetime.now().timestamp()
            diferencia_horas = (ahora - float(last_seen)) / 3600
            if diferencia_horas < 2:  # Heartbeat en últimas 2 horas
                bono += config["bono_conectividad_estable"]
        except:
            pass
    
    # ✅ Retornar bono máximo 5%
    return min(bono, config["porcentaje_bono_maximo"])

@app.route('/')
def index():
    """Sirve el dashboard HTML"""
    return send_from_directory('.', 'dashboard.html')

# ✅ AGREGAR AQUÍ:
@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de salud del servicio"""
    return jsonify({
        "status": "healthy",
        "service": "adride-server",
        "tablets_count": len(tablets_data),
        "timestamp": datetime.datetime.now().isoformat()
    }), 200

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    """Recibe heartbeat de las tablets Android"""
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Datos inválidos'}), 400
        
        device_id = data.get('device_id')
        if not device_id:
            return jsonify({'status': 'error', 'message': 'device_id requerido'}), 400
        
        # ✅ NUEVO: Acumular kilómetros por día (no sobrescribir)
        fecha_hoy = datetime.datetime.now().strftime('%Y-%m-%d')
        km_nuevos = float(data.get('kilometros_recorridos', 0) or 0)
        
        # ✅ Inicializar si no existe
        if device_id not in km_reports:
            km_reports[device_id] = {}
        
        # ✅ Acumular km del día actual
        km_acumulados_hoy = km_reports[device_id].get(fecha_hoy, 0)
        km_reports[device_id][fecha_hoy] = km_acumulados_hoy + km_nuevos
        
        tablets_data[device_id] = {
            "device_id": device_id,
            "model": data.get('model', 'Unknown'),
            "android_version": data.get('android_version', 'Unknown'),
            "app_version": data.get('app_version', '1.0'),
            "timestamp": data.get('timestamp', str(datetime.datetime.now().timestamp())),
            "total_impressions": data.get('impresiones', '0'),
            "uptime_hours": data.get('uptime_hours', '0'),
            "network_type": data.get('network_type', 'unknown'),
            "is_charging": data.get('is_charging', 'false'),
            "ads_count": data.get('ads_count', '0'),
            "ad_impressions": data.get('ad_impressions', {}),
            "kilometros_recorridos": str(km_reports[device_id][fecha_hoy]),  # ✅ Acumulado del día
            "received_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "last_seen": datetime.datetime.now().timestamp()
        }
        
        guardar_datos()  # ✅ Guarda tablets_data Y km_reports
        
        print(f"❤️ Heartbeat recibido: {device_id[:12]}... | Impresiones: {data.get('impresiones', 0)} | Km acumulados hoy: {km_reports[device_id][fecha_hoy]}")
        
        return jsonify({
            "status": "ok",
            "message": "Heartbeat recibido",
            "device_id": device_id[:12] + "...",
            "received_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200
        
    except Exception as e:
        print(f"❌ Error en heartbeat: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ CLIMA IQUIQUE - CON API REAL (VERSIÓN FINAL LIMPIA)
# ============================================
@app.route('/api/clima', methods=['GET'])
def get_clima():
    """Retorna clima actual de Iquique desde API real con fallback"""
    global CLIMA_CACHE, CLIMA_CACHE_TIME
    
    try:
        # ✅ Verificar si hay cache válido (5 min)
        if CLIMA_CACHE and CLIMA_CACHE_TIME:
            tiempo_transcurrido = datetime.datetime.now() - CLIMA_CACHE_TIME
            if tiempo_transcurrido.total_seconds() < CACHE_DURATION_MIN * 60:
                print("✅ [AdRide] Usando clima en cache")
                return jsonify(CLIMA_CACHE), 200
        
        # ✅ Si no hay cache o expiró, llamar a la API
        if not OPENWEATHER_API_KEY or OPENWEATHER_API_KEY == "":
            print("⚠️ [AdRide] API Key no configurada, usando fallback")
            return jsonify(get_clima_estatico()), 200
        
        print(f"🔑 [AdRide] API Key presente (longitud: {len(OPENWEATHER_API_KEY)})")
        
        # ✅ Llamar a OpenWeatherMap
        url = f"https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": OPENWEATHER_CITY,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "es"
        }
        
        print(f"🌐 [AdRide] Llamando a API: {OPENWEATHER_CITY}")
        
        response = requests.get(url, params=params, timeout=10)
        
        print(f"📡 [AdRide] Respuesta API: status={response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ [AdRide] API falló: {response.status_code} - {response.text[:200]}")
            return jsonify(get_clima_estatico()), 200
        
        data = response.json()
        
        # ============================================
        # ✅ MAPEO DE CONDICIONES DE CLIMA (MEJORADO)
        # ============================================
        weather_main = data['weather'][0]['main'].lower()
        weather_desc = data['weather'][0]['description'].lower()
        
        condicion_map = {
            'clear': 'Soleado',
            'clouds': 'Nublado',
            'rain': 'Lluvioso',
            'drizzle': 'Llovizna',
            'thunderstorm': 'Tormenta',
            'snow': 'Nieve',
            'mist': 'Neblina',
            'smoke': 'Humo',
            'haze': 'Neblina',
            'dust': 'Polvo',
            'fog': 'Niebla'
        }
        
        # Mapeo detallado según descripción
        if weather_main == 'clear':
            condicion = 'Soleado'
            icono = 'soleado'
        elif weather_main == 'clouds':
            if 'overcast' in weather_desc:
                condicion = 'Muy Nublado'
                icono = 'nublado'
            elif 'broken' in weather_desc:
                condicion = 'Parcialmente Nublado'
                icono = 'parcialmente_nublado'
            elif 'scattered' in weather_desc:
                condicion = 'Algo Nublado'
                icono = 'parcialmente_nublado'
            elif 'few' in weather_desc:
                condicion = 'Pocas Nubes'
                icono = 'parcialmente_nublado'
            else:
                condicion = 'Nublado'
                icono = 'nublado'
        elif weather_main == 'rain':
            if 'heavy' in weather_desc or 'torrential' in weather_desc:
                condicion = 'Lluvia Fuerte'
                icono = 'lluvioso'
            elif 'light' in weather_desc:
                condicion = 'Llovizna'
                icono = 'lluvioso'
            else:
                condicion = 'Lluvioso'
                icono = 'lluvioso'
        elif weather_main == 'drizzle':
            condicion = 'Llovizna'
            icono = 'lluvioso'
        elif weather_main == 'thunderstorm':
            condicion = 'Tormenta'
            icono = 'lluvioso'
        elif weather_main in ['mist', 'haze', 'fog']:
            condicion = 'Neblina'
            icono = 'nublado'
        elif weather_main == 'smoke':
            condicion = 'Humo'
            icono = 'nublado'
        elif weather_main == 'dust':
            condicion = 'Polvo'
            icono = 'nublado'
        elif weather_main == 'snow':
            condicion = 'Nieve'
            icono = 'nublado'
        else:
            condicion = condicion_map.get(weather_main, 'Soleado')
            icono = 'soleado'
        
        # Calcular UV aproximado según hora del día
        hora_actual = datetime.datetime.now().hour
        if 10 <= hora_actual <= 16:
            uv = "Muy Alto"
        elif 8 <= hora_actual <= 10 or 16 <= hora_actual <= 18:
            uv = "Alto"
        else:
            uv = "Moderado"
        
        # ✅ Construir respuesta (SOLO UNA VEZ)
        clima = {
            "ciudad": data['name'],
            "temperatura": int(data['main']['temp']),
            "condicion": condicion,
            "icono": icono,
            "uv": uv,
            "humedad": data['main']['humidity'],
            "viento_km": int(data['wind']['speed'] * 3.6),
            "actualizado": datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        }
        
        # ✅ Guardar en cache
        CLIMA_CACHE = clima
        CLIMA_CACHE_TIME = datetime.datetime.now()
        
        print(f"🌤️ [AdRide] Clima real obtenido: {clima['temperatura']}°C - {clima['condicion']}")
        
        return jsonify(clima), 200  # ← SOLO UN RETURN
        
    except requests.exceptions.InvalidAPIKey as e:
        print(f"❌ [AdRide] API Key inválida: {e}")
        return jsonify({"error": "API Key inválida"}), 401
    except requests.exceptions.Timeout as e:
        print(f"❌ [AdRide] Timeout de API: {e}")
        return jsonify(get_clima_estatico()), 200
    except requests.exceptions.RequestException as e:
        print(f"❌ [AdRide] Error de conexión: {e}")
        return jsonify(get_clima_estatico()), 200
    except Exception as e:
        print(f"❌ [AdRide] Error inesperado: {type(e).__name__} - {e}")
        import traceback
        print(f"📋 [AdRide] Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Error interno del servidor"}), 500
        
    
        
        
   

# ============================================
# ✅ CLIMA ESTÁTICO (FALLBACK)
# ============================================
def get_clima_estatico():
    """Retorna clima estático como fallback si la API falla"""
    return {
        "ciudad": "Iquique",
        "temperatura": 24,
        "condicion": "Soleado",
        "icono": "soleado",
        "uv": "Alto",
        "humedad": 65,
        "viento_km": 18,
        "actualizado": datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    

# ============================================
# ✅ SUBIR DOCUMENTO
# ============================================
@app.route('/api/documentos/subir', methods=['POST'])
def subir_documento():
    """Recibe foto de documento desde app Android"""
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
        
        if 'foto' not in request.files:
            return jsonify({'status': 'error', 'message': 'No se recibió la foto'}), 400
        
        foto = request.files['foto']
        conductor_id = request.form.get('conductor_id')
        tipo_documento = request.form.get('tipo_documento')
        
        if not conductor_id or not tipo_documento:
            return jsonify({'status': 'error', 'message': 'Faltan datos'}), 400
        
        if foto.filename == '' or not allowed_file(foto.filename):
            return jsonify({'status': 'error', 'message': 'Archivo inválido'}), 400
        
        filename = f"{conductor_id}_{tipo_documento}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        foto.save(filepath)
        
        if conductor_id not in documentos_conductores:
            documentos_conductores[conductor_id] = {}
        
        documentos_conductores[conductor_id][tipo_documento] = {
            'tipo_documento': tipo_documento,
            'foto_url': f'/uploads/documentos/{filename}',
            'estado': 'pendiente_validacion',
            'fecha_subida': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'comentario_admin': '',
            'fecha_validacion': ''
        }
        
        guardar_datos()
        
        print(f"📄 Documento subido: {conductor_id[:12]}... - {tipo_documento}")
        
        return jsonify({
            'status': 'ok',
            'message': 'Documento subido',
            'tipo_documento': tipo_documento,
            'estado': 'pendiente_validacion'
        }), 200
    
    except Exception as e:
        print(f"❌ Error subiendo documento: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ VER ESTADO DE DOCUMENTOS
# ============================================
@app.route('/api/documentos/estado/<conductor_id>', methods=['GET'])
def ver_estado_documentos(conductor_id):
    """Obtiene estado de documentos de un conductor"""
    try:
        documentos = documentos_conductores.get(conductor_id, {})
        
        return jsonify({
            'status': 'ok',
            'documentos': documentos
        }), 200
    
    except Exception as e:
        print(f"❌ Error verificando documentos: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ GUARDAR DATOS DE PAGO
# ============================================
@app.route('/api/pago/guardar', methods=['POST'])
def guardar_pago():
    """Recibe datos bancarios del conductor"""
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
        
        data = request.get_json()
        conductor_id = data.get('conductor_id')
        
        if not conductor_id:
            return jsonify({'status': 'error', 'message': 'conductor_id requerido'}), 400
        
        pagos_conductores[conductor_id] = {
            'rut': data.get('rut', ''),
            'nombre_titular': data.get('nombre_titular', ''),
            'banco': data.get('banco', ''),
            'tipo_cuenta': data.get('tipo_cuenta', ''),
            'numero_cuenta': data.get('numero_cuenta', ''),
            'email': data.get('email', ''),
            'fecha_actualizacion': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        guardar_datos()
        
        print(f"💳 Pago configurado: {conductor_id[:12]}... - {data.get('banco', '')}")
        
        return jsonify({
            'status': 'ok',
            'message': 'Datos de pago guardados'
        }), 200
    
    except Exception as e:
        print(f"❌ Error guardando pago: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ VER DATOS DE PAGO
# ============================================
@app.route('/api/pago/ver/<conductor_id>', methods=['GET'])
def ver_pago(conductor_id):
    """Obtiene datos de pago de un conductor"""
    try:
        pago = pagos_conductores.get(conductor_id, None)
        
        if pago:
            return jsonify({
                'status': 'ok',
                'pago': pago
            }), 200
        else:
            return jsonify({
                'status': 'ok',
                'pago': None,
                'message': 'No hay datos de pago registrados'
            }), 200
    
    except Exception as e:
        print(f"❌ Error verificando pago: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ ADMIN - VALIDAR DOCUMENTO
# ============================================
@app.route('/api/admin/documentos/<conductor_id>/<tipo_documento>/validar', methods=['POST'])
def validar_documento(conductor_id, tipo_documento):
    """Admin aprueba o rechaza documento"""
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
        
        data = request.get_json()
        accion = data.get('accion')
        comentario = data.get('comentario', '')
        
        if accion not in ['aprobado', 'rechazado']:
            return jsonify({'status': 'error', 'message': 'Acción inválida'}), 400
        
        if conductor_id not in documentos_conductores:
            return jsonify({'status': 'error', 'message': 'Conductor no encontrado'}), 404
        
        if tipo_documento not in documentos_conductores[conductor_id]:
            return jsonify({'status': 'error', 'message': 'Documento no encontrado'}), 404
        
        documentos_conductores[conductor_id][tipo_documento]['estado'] = accion
        documentos_conductores[conductor_id][tipo_documento]['comentario_admin'] = comentario
        documentos_conductores[conductor_id][tipo_documento]['fecha_validacion'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        guardar_datos()
        
        print(f"✅ Documento {accion}: {conductor_id[:12]}... - {tipo_documento}")
        
        return jsonify({
            'status': 'ok',
            'message': f'Documento {accion}'
        }), 200
    
    except Exception as e:
        print(f"❌ Error validando documento: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ ADMIN - ELIMINAR DOCUMENTO
# ============================================
@app.route('/api/admin/documentos/<conductor_id>/<tipo_documento>/eliminar', methods=['POST'])
def eliminar_documento(conductor_id, tipo_documento):
    """Admin elimina documento permanentemente (foto + registro)"""
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
        
        if conductor_id not in documentos_conductores:
            return jsonify({'status': 'error', 'message': 'Conductor no encontrado'}), 404
        
        if tipo_documento not in documentos_conductores[conductor_id]:
            return jsonify({'status': 'error', 'message': 'Documento no encontrado'}), 404
        
        doc_data = documentos_conductores[conductor_id][tipo_documento]
        foto_url = doc_data.get('foto_url', '')
        
        if foto_url:
            try:
                filename = foto_url.replace('/uploads/documentos/', '')
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"🗑️ Archivo eliminado: {filepath}")
            except Exception as e:
                print(f"⚠️ Error eliminando archivo: {e}")
        
        del documentos_conductores[conductor_id][tipo_documento]
        
        if not documentos_conductores[conductor_id]:
            del documentos_conductores[conductor_id]
        
        guardar_datos()
        
        print(f"🗑️ Documento eliminado: {conductor_id[:12]}... - {tipo_documento}")
        
        return jsonify({
            'status': 'ok',
            'message': 'Documento eliminado permanentemente'
        }), 200
    
    except Exception as e:
        print(f"❌ Error eliminando documento: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ ADMIN - LISTAR DOCUMENTOS PENDIENTES
# ============================================
@app.route('/api/admin/documentos/pendientes', methods=['GET'])
def listar_documentos_pendientes():
    """Obtiene lista de documentos pendientes de validación"""
    try:
        pendientes = []
        
        for conductor_id, docs in documentos_conductores.items():
            for tipo_documento, doc_data in docs.items():
                if doc_data.get('estado') == 'pendiente_validacion':
                    pendientes.append({
                        'conductor_id': conductor_id,
                        'conductor_id_corto': conductor_id[:12] + '...',
                        'tipo_documento': tipo_documento,
                        'foto_url': doc_data.get('foto_url', ''),
                        'fecha_subida': doc_data.get('fecha_subida', '')
                    })
        
        return jsonify({
            'status': 'ok',
            'pendientes': pendientes,
            'total': len(pendientes)
        }), 200
    
    except Exception as e:
        print(f"❌ Error listando pendientes: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/tablets', methods=['GET'])
def get_tablets():
    """Obtiene lista de tablets activas"""
    return jsonify({
        "count": len(tablets_data),
        "tablets": tablets_data
    }), 200

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Obtiene estadísticas resumidas"""
    try:
        total_impressions = sum(
            int(t.get('total_impressions', 0) or 0) 
            for t in tablets_data.values()
        )
        
        online_count = sum(
            1 for t in tablets_data.values() 
            if (datetime.datetime.now().timestamp() - float(t.get('last_seen', 0) or 0)) < 300
        )
        
        documentos_pendientes = sum(
            1 for docs in documentos_conductores.values()
            for doc in docs.values()
            if doc.get('estado') == 'pendiente_validacion'
        )
        
        return jsonify({
            "total_tablets": len(tablets_data),
            "online_tablets": online_count,
            "total_impressions": total_impressions,
            "documentos_pendientes": documentos_pendientes,
            "last_update": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200
    except Exception as e:
        print(f"❌ Error en stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/km-report', methods=['POST'])
def km_report():
    """Recibe reporte de kilómetros de conductores"""
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
        
        data = request.get_json()
        device_id = data.get('device_id')
        fecha = data.get('fecha', datetime.datetime.now().strftime('%Y-%m-%d'))
        km = data.get('km', 0)
        
        if not device_id:
            return jsonify({'status': 'error', 'message': 'device_id requerido'}), 400
        
        if device_id not in km_reports:
            km_reports[device_id] = {}
        
        km_reports[device_id][fecha] = km
        guardar_datos()
        
        return jsonify({
            "status": "ok",
            "message": "Km reportado",
            "device_id": device_id[:12] + "...",
            "fecha": fecha,
            "km": km
        }), 200
        
    except Exception as e:
        print(f"❌ Error en km-report: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500



# ✅ CÁLCULO DE PAGOS POR CONDUCTOR (CORREGIDO CON TRY/EXCEPT)
# ✅ CÁLCULO DE PAGOS POR CONDUCTOR (VERSIÓN FINAL CORREGIDA)
@app.route('/api/payments/calculate/<conductor_id>', methods=['GET'])
def calcular_pago_conductor(conductor_id):
    """Calcula payout para un conductor específico usando fórmula 25% + 5%"""
    try:
        if conductor_id not in tablets_data:
            return jsonify({'error': 'Conductor no encontrado'}), 404
        
        data = tablets_data[conductor_id]
        
        # 📊 Métricas base
        total_impressions = int(data.get('total_impressions', 0) or 0)
        revenue_generado = total_impressions * config['valor_por_impresion']
        
        # 📍 KM ACUMULADOS HOY
        fecha_hoy = datetime.datetime.now().strftime('%Y-%m-%d')
        km_acumulados_hoy = km_reports.get(conductor_id, {}).get(fecha_hoy, 0.0)
        
        # 🧮 Fórmula 25% + 5% (CLAVES CORREGIDAS)
        pago_base = revenue_generado * config['porcentaje_base_conductor']
        
        # 🎁 Calcular bonos
        bono_km = revenue_generado * config['bono_km_porcentaje'] if km_acumulados_hoy >= config['km_minimos_bono'] else 0
        bono_impresiones = revenue_generado * config['bono_impresiones_porcentaje'] if total_impressions >= config['impresiones_minimas_bono'] else 0
        
        bono_documentos = 0
        if conductor_id in documentos_conductores:
            docs = documentos_conductores[conductor_id]
            if docs and all(doc.get('estado') == 'aprobado' for doc in docs.values()):
                bono_documentos = revenue_generado * config['bono_documentos_aprobados']
        
        bono_conectividad = 0
        last_seen = data.get('last_seen', 0)
        if last_seen:
            try:
                ahora = datetime.datetime.now().timestamp()
                if (ahora - float(last_seen)) / 3600 < 2:
                    bono_conectividad = revenue_generado * config['bono_conectividad_estable']
            except:
                pass
        
        pago_bono = min(bono_km + bono_impresiones + bono_documentos + bono_conectividad, 
                       revenue_generado * config['porcentaje_bono_maximo'])
        
        # ✅ CLAVE CORREGIDA: porcentaje_maximo_total
        pago_total = min(pago_base + pago_bono, revenue_generado * config['porcentaje_maximo_total'])
        porcentaje_real = (pago_total / revenue_generado * 100) if revenue_generado > 0 else 0
        
        return jsonify({
            'conductor_id': conductor_id,
            'revenue_generado': round(revenue_generado, 2),
            'total_impressions': total_impressions,
            'km_acumulados_hoy': round(km_acumulados_hoy, 2),
            'pago_base': round(pago_base, 2),
            'bonos_detalle': {
                'km': round(bono_km, 2),
                'impresiones': round(bono_impresiones, 2),
                'documentos': round(bono_documentos, 2),
                'conectividad': round(bono_conectividad, 2)
            },
            'pago_bono': round(pago_bono, 2),
            'pago_total': round(pago_total, 2),
            'porcentaje_real': f"{porcentaje_real:.1f}%"
        }), 200
        
    except KeyError as e:
        print(f"❌ KeyError en pago: {e} - Clave de config no encontrada")
        return jsonify({'error': f'Clave de configuración no encontrada: {e}'}), 500
    except Exception as e:
        print(f"❌ Error calculando pago para {conductor_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500




# ✅ LISTADO DE PAGOS PARA TODOS LOS CONDUCTORES (CORREGIDO CON TRY EXTERNO)
# ✅ LISTADO DE PAGOS PARA TODOS LOS CONDUCTORES (CORREGIDO)
@app.route('/api/payments/calculate', methods=['GET'])
def calcular_pagos_todos():
    """Retorna cálculo de pagos para todos los conductores activos"""
    try:
        detalles = []
        payout_total = 0
        revenue_total = 0
        
        for conductor_id in tablets_data.keys():
            try:
                data = tablets_data[conductor_id]
                total_impressions = int(data.get('total_impressions', 0) or 0)
                revenue_generado = total_impressions * config['valor_por_impresion']
                
                # 📍 KM ACUMULADOS HOY
                fecha_hoy = datetime.datetime.now().strftime('%Y-%m-%d')
                km_acumulados_hoy = km_reports.get(conductor_id, {}).get(fecha_hoy, 0.0)
                
                # 🧮 Cálculo de payout (CLAVES CORREGIDAS)
                pago_base = revenue_generado * config['porcentaje_base_conductor']  # ← CORREGIDO
                
                bono_km = revenue_generado * config['bono_km_porcentaje'] if km_acumulados_hoy >= config['km_minimos_bono'] else 0
                bono_impresiones = revenue_generado * config['bono_impresiones_porcentaje'] if total_impressions >= config['impresiones_minimas_bono'] else 0
                
                bono_documentos = 0
                if conductor_id in documentos_conductores:
                    docs = documentos_conductores[conductor_id]
                    if docs and all(doc.get('estado') == 'aprobado' for doc in docs.values()):
                        bono_documentos = revenue_generado * config['bono_documentos_aprobados']
                
                bono_conectividad = 0
                last_seen = data.get('last_seen', 0)
                if last_seen:
                    try:
                        ahora = datetime.datetime.now().timestamp()
                        if (ahora - float(last_seen)) / 3600 < 2:
                            bono_conectividad = revenue_generado * config['bono_conectividad_estable']
                    except:
                        pass
                
                pago_bono = min(bono_km + bono_impresiones + bono_documentos + bono_conectividad, 
                               revenue_generado * config['porcentaje_bono_maximo'])
                
                # ✅ CLAVE CORREGIDA:
                pago_total_conductor = min(pago_base + pago_bono, revenue_generado * config['porcentaje_maximo_total'])
                
                detalles.append({
                    'conductor_id': conductor_id,
                    'revenue_generado': round(revenue_generado, 2),
                    'total_impressions': total_impressions,
                    'km_acumulados_hoy': round(km_acumulados_hoy, 2),
                    'pago_base': round(pago_base, 2),
                    'pago_bono': round(pago_bono, 2),
                    'pago_total': round(pago_total_conductor, 2),
                    'porcentaje_real': f"{round(pago_total_conductor / revenue_generado * 100, 1) if revenue_generado > 0 else 0}%"
                })
                
                payout_total += pago_total_conductor
                revenue_total += revenue_generado
                
            except Exception as e:
                print(f"⚠️ Error calculando pago para {conductor_id}: {e}")
                continue
        
        adride_retencion = revenue_total - payout_total
        
        return jsonify({
            'detalles': detalles,
            'payout_total': round(payout_total, 2),
            'revenue_total_generado': round(revenue_total, 2),
            'adride_retencion': round(adride_retencion, 2),
            'porcentaje_payout': f"{round(payout_total / revenue_total * 100, 1) if revenue_total > 0 else 0}%",
            'conductores_count': len(detalles),
            'periodo': 'acumulado',
            'fecha_calculo': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200
        
    except KeyError as e:
        print(f"❌ KeyError en pagos: {e}")
        return jsonify({'error': f'Clave de config no encontrada: {e}'}), 500
    except Exception as e:
        print(f"❌ Error calculando pagos: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
# ============================================
# ✅ LEGACY: CALCULAR PAGOS (FÓRMULA ANTIGUA - COMPATIBILIDAD)
# ============================================
@app.route('/api/payments/calculate-legacy', methods=['GET'])
def calculate_payments_legacy():
    """Calcula pagos con fórmula antigua (km + horas + fondo) - Para compatibilidad"""
    try:
        now = datetime.datetime.now()
        fecha_hoy = now.strftime('%Y-%m-%d')
        
        payments = []
        
        impresiones_totales = sum(
            int(t.get('total_impressions', 0) or 0) 
            for t in tablets_data.values()
        )
        
        for device_id, data in tablets_data.items():
            km_recorridos = int(km_reports.get(device_id, {}).get(fecha_hoy, 0) or 0)
            horas_activas = float(data.get('uptime_hours', 0) or 0)
            impresiones_conductor = int(data.get('total_impressions', 0) or 0)
            
            pago_km = km_recorridos * config['tarifa_km']
            pago_horas = horas_activas * config['tarifa_hora_activa']
            
            if impresiones_totales > 0:
                share = impresiones_conductor / impresiones_totales
            else:
                share = 0
            
            pago_fondo = share * fondo_conductores_diario
            subtotal = pago_km + pago_horas + pago_fondo
            bono_pico = subtotal * config['bono_horas_pico_porcentaje'] if km_recorridos >= config['km_minimos_bono'] else 0
            pago_total = subtotal + bono_pico
            
            payments.append({
                "device_id": device_id[:12] + "...",
                "device_id_completo": device_id,
                "km_recorridos": km_recorridos,
                "horas_activas": round(horas_activas, 1),
                "pago_km": round(pago_km),
                "pago_horas": round(pago_horas),
                "pago_fondo": round(pago_fondo),
                "share_impresiones": round(share * 100, 1),
                "bono_pico": round(bono_pico),
                "pago_total": round(pago_total),
                "fecha": fecha_hoy,
                "resumen_negocio": {
                    "presupuesto_total_mensual": config["presupuesto_total_mensual"],
                    "fondo_conductores_diario": round(fondo_conductores_diario),
                    "porcentaje_conductores": f"{int(config['porcentaje_para_conductores']*100)}%"
                }
            })
        
        payments.sort(key=lambda x: x['pago_total'], reverse=True)
        
        return jsonify({
            "status": "ok",
            "fecha": fecha_hoy,
            "total_a_pagar": sum(p['pago_total'] for p in payments),
            "conductores": len(payments),
            "detalles": payments
        }), 200
        
    except Exception as e:
        print(f"❌ Error calculando pagos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/payments/export/csv', methods=['GET'])
def export_csv():
    """Exporta pagos en formato CSV para transferencias bancarias"""
    try:
        now = datetime.datetime.now()
        fecha_hoy = now.strftime('%Y-%m-%d')
        
        csv_content = "conductor_id,revenue_generado,impresiones,pago_base,pago_bono,pago_total,porcentaje_real,fecha\n"
        
        for conductor_id, data in tablets_data.items():
            total_impressions = int(data.get('total_impressions', 0) or 0)
            revenue_generado = total_impressions * config["valor_por_impresion"]
            pago_base = revenue_generado * config["porcentaje_base_conductor"]
            bono_porcentaje = calcular_bono_desempeno(conductor_id, data)
            pago_bono = revenue_generado * bono_porcentaje
            pago_total = min(pago_base + pago_bono, revenue_generado * config['porcentaje_maximo_total'])
            
            csv_content += f"{conductor_id},{revenue_generado},{total_impressions},{round(pago_base)},{round(pago_bono)},{round(pago_total)},{(pago_total/revenue_generado)*100:.1f}%,{fecha_hoy}\n"
        
        return app.response_class(
            response=csv_content,
            status=200,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename=pagos_adride_{fecha_hoy}.csv'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# ✅ SERVIR ARCHIVOS SUBIDOS
# ============================================
@app.route('/uploads/documentos/<filename>', methods=['GET'])
def servir_documento(filename):
    """Sirve fotos de documentos para el dashboard"""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

# Cargar datos al iniciar
cargar_datos()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
