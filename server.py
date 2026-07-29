from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
import json
import os
import datetime
import requests
from werkzeug.utils import secure_filename
import time

# ✅ SUPABASE CONFIG
SUPABASE_URL = "https://zwrbqrdeaajpdhvnovbb.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp3cmJxcmRlYWFqcGRodm5vdmJiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODUzNDIwMTksImV4cCI6MjEwMDkxODAxOX0.UmKgD7vecvqP3ys2eeQNG58j_QGCyYjAgo3O8tCINxo"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

os.environ['TZ'] = 'America/Santiago'
try:
    time.tzset()
except AttributeError:
    pass

# ✅ CONFIGURACIÓN DE API DE CLIMA
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")
OPENWEATHER_CITY = "Iquique"
CLIMA_CACHE = None
CLIMA_CACHE_TIME = None
CACHE_DURATION_MIN = 5

app = Flask(__name__, static_folder='.')
CORS(app)

# ✅ CONFIGURACIÓN PARA SUBIDA DE ARCHIVOS
UPLOAD_FOLDER = 'uploads/documentos'
APK_FOLDER = 'uploads/apk'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(APK_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

# Archivos de datos
DATA_FILE = 'tablets_data.json'
KM_FILE = 'km_reports.json'
PAGOS_FILE = 'pagos_conductores.json'
DOCUMENTOS_FILE = 'documentos_conductores.json'
REGISTRO_FILE = 'conductores_registrados.json'
VERSION_FILE = 'version_actual.json'

# Variables globales
tablets_data = {}
km_reports = {}
pagos_conductores = {}
documentos_conductores = {}
conductores_registrados = {}
version_actual = {"version_code": 1, "version_name": "1.0.0", "apk_filename": None}

# ✅ CONFIGURACIÓN DE NEGOCIO ADRIDE - MODELO 25% + 5% BONO
config = {
    "valor_por_impresion": 30,
    "porcentaje_base_conductor": 0.25,
    "porcentaje_bono_maximo": 0.05,
    "porcentaje_maximo_total": 0.30,
    "km_minimos_bono": 50,
    "impresiones_minimas_bono": 100,
    "bono_documentos_aprobados": 0.01,
    "bono_conectividad_estable": 0.01,
    "bono_km_porcentaje": 0.015,
    "bono_impresiones_porcentaje": 0.015
}

config["tarifa_km"] = 15
config["tarifa_hora_activa"] = 500
config["presupuesto_total_mensual"] = 250000
config["porcentaje_para_conductores"] = 0.40
config["porcentaje_para_adride"] = 0.60
config["dias_mes"] = 30
config["bono_horas_pico_porcentaje"] = 0.20

fondo_conductores_mensual = config["presupuesto_total_mensual"] * config["porcentaje_para_conductores"]
fondo_conductores_diario = fondo_conductores_mensual / config["dias_mes"]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cargar_datos():
    global tablets_data, km_reports, pagos_conductores, documentos_conductores, conductores_registrados, version_actual
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
        if os.path.exists(REGISTRO_FILE):
            with open(REGISTRO_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                conductores_registrados = json.loads(content) if content else {}
            print(f"✅ Conductores registrados: {len(conductores_registrados)}")
        if os.path.exists(VERSION_FILE):
            with open(VERSION_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                version_actual = json.loads(content) if content else version_actual
            print(f"✅ Versión actual: {version_actual.get('version_name')}")
    except Exception as e:
        print(f"⚠️ Error cargando datos: {e}")
        tablets_data = {}
        km_reports = {}
        pagos_conductores = {}
        documentos_conductores = {}

def guardar_datos():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(tablets_data, f, indent=2, ensure_ascii=False)
        with open(KM_FILE, 'w', encoding='utf-8') as f:
            json.dump(km_reports, f, indent=2, ensure_ascii=False)
        with open(PAGOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(pagos_conductores, f, indent=2, ensure_ascii=False)
        with open(DOCUMENTOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(documentos_conductores, f, indent=2, ensure_ascii=False)
        with open(REGISTRO_FILE, 'w', encoding='utf-8') as f:
            json.dump(conductores_registrados, f, indent=2, ensure_ascii=False)
        with open(VERSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(version_actual, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error guardando datos: {e}")

def calcular_bono_desempeno(conductor_id, data):
    bono = 0.0
    fecha_hoy = datetime.datetime.now().strftime('%Y-%m-%d')
    km_acumulados = km_reports.get(conductor_id, {}).get(fecha_hoy, 0)
    if km_acumulados >= config["km_minimos_bono"]:
        bono += config["bono_km_porcentaje"]
        print(f"📍 Bono km aplicado: {conductor_id[:12]}... | Km hoy: {km_acumulados}")
    total_impressions = int(data.get('total_impressions', 0) or 0)
    if total_impressions >= config["impresiones_minimas_bono"]:
        bono += config["bono_impresiones_porcentaje"]
    if conductor_id in documentos_conductores:
        docs = documentos_conductores[conductor_id]
        if docs and all(doc.get('estado') == 'aprobado' for doc in docs.values()):
            bono += config["bono_documentos_aprobados"]
    last_seen = data.get('last_seen', 0)
    if last_seen:
        try:
            ahora = datetime.datetime.now().timestamp()
            diferencia_horas = (ahora - float(last_seen)) / 3600
            if diferencia_horas < 2:
                bono += config["bono_conectividad_estable"]
        except:
            pass
    return min(bono, config["porcentaje_bono_maximo"])

@app.route('/')
def index():
    return send_from_directory('.', 'dashboard.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "adride-server",
        "tablets_count": len(tablets_data),
        "timestamp": datetime.datetime.now().isoformat()
    }), 200

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
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
        fecha_hoy = datetime.datetime.now().strftime('%Y-%m-%d')
        km_nuevos = float(data.get('kilometros_recorridos', 0) or 0)
        if device_id not in km_reports:
            km_reports[device_id] = {}
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
            "kilometros_recorridos": str(km_reports[device_id][fecha_hoy]),
            "received_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "last_seen": datetime.datetime.now().timestamp()
        }
        guardar_datos()
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
# ✅ CLIMA IQUIQUE - CON API REAL
# ============================================
@app.route('/api/clima', methods=['GET'])
def get_clima():
    global CLIMA_CACHE, CLIMA_CACHE_TIME
    try:
        if CLIMA_CACHE and CLIMA_CACHE_TIME:
            tiempo_transcurrido = datetime.datetime.now() - CLIMA_CACHE_TIME
            if tiempo_transcurrido.total_seconds() < CACHE_DURATION_MIN * 60:
                print("✅ [AdRide] Usando clima en cache")
                return jsonify(CLIMA_CACHE), 200
        if not OPENWEATHER_API_KEY or OPENWEATHER_API_KEY == "":
            print("⚠️ [AdRide] API Key no configurada, usando fallback")
            return jsonify(get_clima_estatico()), 200
        url = f"https://api.openweathermap.org/data/2.5/weather"
        params = {"q": OPENWEATHER_CITY, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "es"}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return jsonify(get_clima_estatico()), 200
        data = response.json()
        weather_main = data['weather'][0]['main'].lower()
        weather_desc = data['weather'][0]['description'].lower()
        condicion_map = {
            'clear': 'Soleado', 'clouds': 'Nublado', 'rain': 'Lluvioso',
            'drizzle': 'Llovizna', 'thunderstorm': 'Tormenta', 'snow': 'Nieve',
            'mist': 'Neblina', 'smoke': 'Humo', 'haze': 'Neblina',
            'dust': 'Polvo', 'fog': 'Niebla'
        }
        if weather_main == 'clear':
            condicion, icono = 'Soleado', 'soleado'
        elif weather_main == 'clouds':
            if 'overcast' in weather_desc:
                condicion, icono = 'Muy Nublado', 'nublado'
            elif 'broken' in weather_desc or 'scattered' in weather_desc:
                condicion, icono = 'Parcialmente Nublado', 'parcialmente_nublado'
            elif 'few' in weather_desc:
                condicion, icono = 'Pocas Nubes', 'parcialmente_nublado'
            else:
                condicion, icono = 'Nublado', 'nublado'
        elif weather_main == 'rain':
            if 'heavy' in weather_desc or 'torrential' in weather_desc:
                condicion, icono = 'Lluvia Fuerte', 'lluvioso'
            elif 'light' in weather_desc:
                condicion, icono = 'Llovizna', 'lluvioso'
            else:
                condicion, icono = 'Lluvioso', 'lluvioso'
        elif weather_main == 'drizzle':
            condicion, icono = 'Llovizna', 'lluvioso'
        elif weather_main == 'thunderstorm':
            condicion, icono = 'Tormenta', 'lluvioso'
        elif weather_main in ['mist', 'haze', 'fog']:
            condicion, icono = 'Neblina', 'nublado'
        elif weather_main == 'smoke':
            condicion, icono = 'Humo', 'nublado'
        elif weather_main == 'dust':
            condicion, icono = 'Polvo', 'nublado'
        elif weather_main == 'snow':
            condicion, icono = 'Nieve', 'nublado'
        else:
            condicion = condicion_map.get(weather_main, 'Soleado')
            icono = 'soleado'
        hora_actual = datetime.datetime.now().hour
        if 10 <= hora_actual <= 16:
            uv = "Muy Alto"
        elif 8 <= hora_actual <= 10 or 16 <= hora_actual <= 18:
            uv = "Alto"
        else:
            uv = "Moderado"
        clima = {
            "ciudad": data['name'],
            "temperatura": int(data['main']['temp']),
            "condicion": condicion, "icono": icono,
            "uv": uv, "humedad": data['main']['humidity'],
            "viento_km": int(data['wind']['speed'] * 3.6),
            "actualizado": datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        }
        CLIMA_CACHE = clima
        CLIMA_CACHE_TIME = datetime.datetime.now()
        print(f"🌤️ [AdRide] Clima real: {clima['temperatura']}°C - {clima['condicion']}")
        return jsonify(clima), 200
    except Exception as e:
        print(f"❌ [AdRide] Error clima: {e}")
        return jsonify(get_clima_estatico()), 200

def get_clima_estatico():
    return {
        "ciudad": "Iquique", "temperatura": 24, "condicion": "Soleado",
        "icono": "soleado", "uv": "Alto", "humedad": 65, "viento_km": 18,
        "actualizado": datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    }

# ============================================
# ✅ SUBIR DOCUMENTO (FILESYSTEM)
# ============================================
@app.route('/api/documentos/subir', methods=['POST'])
def subir_documento():
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401

        # Support both file upload and Cloudinary URL
        foto_url = None

        # Check for Cloudinary URL in JSON body
        if request.is_json:
            data = request.get_json()
            conductor_id = data.get('conductor_id', '')
            tipo_documento = data.get('tipo_documento', '')
            foto_url = data.get('foto_url', '')
        else:
            conductor_id = request.form.get('conductor_id', '')
            tipo_documento = request.form.get('tipo_documento', '')

        if not conductor_id or not tipo_documento:
            return jsonify({'status': 'error', 'message': 'Faltan datos'}), 400

        final_url = ''
        filename = ''

        if foto_url:
            final_url = foto_url
            filename = foto_url.split('/')[-1] if '/' in foto_url else foto_url
        elif 'foto' in request.files:
            foto = request.files['foto']
            if foto.filename == '' or not allowed_file(foto.filename):
                return jsonify({'status': 'error', 'message': 'Archivo inválido'}), 400
            filename = f"{conductor_id}_{tipo_documento}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            foto.save(filepath)
            final_url = f'/uploads/documentos/{filename}'
        else:
            return jsonify({'status': 'error', 'message': 'No se recibió la foto ni foto_url'}), 400

        if conductor_id not in documentos_conductores:
            documentos_conductores[conductor_id] = {}
        documentos_conductores[conductor_id][tipo_documento] = {
            'tipo_documento': tipo_documento,
            'foto_url': final_url,
            'estado': 'pendiente_validacion',
            'fecha_subida': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'comentario_admin': '',
            'fecha_validacion': ''
        }
        guardar_datos()
        print(f"📄 Documento subido: {conductor_id[:12]}... - {tipo_documento}")
        return jsonify({'status': 'ok', 'message': 'Documento subido', 'tipo_documento': tipo_documento, 'estado': 'pendiente_validacion'}), 200
    except Exception as e:
        print(f"❌ Error subiendo documento: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ VER ESTADO DE DOCUMENTOS
# ============================================
@app.route('/api/documentos/estado/<conductor_id>', methods=['GET'])
def ver_estado_documentos(conductor_id):
    try:
        documentos = documentos_conductores.get(conductor_id, {})
        return jsonify({'status': 'ok', 'documentos': documentos}), 200
    except Exception as e:
        print(f"❌ Error verificando documentos: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ GUARDAR DATOS DE PAGO (Supabase)
# ============================================
@app.route('/api/pago/guardar', methods=['POST'])
def guardar_pago():
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
        data = request.get_json()
        conductor_id = data.get('conductor_id')
        if not conductor_id:
            return jsonify({'status': 'error', 'message': 'conductor_id requerido'}), 400

        payload = {
            'conductor_id': conductor_id,
            'rut': data.get('rut', ''),
            'nombre_titular': data.get('nombre_titular', ''),
            'banco': data.get('banco', ''),
            'tipo_cuenta': data.get('tipo_cuenta', ''),
            'numero_cuenta': data.get('numero_cuenta', ''),
            'email': data.get('email', ''),
            'fecha_actualizacion': datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        # Upsert to Supabase
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/pagos",
            headers=SUPABASE_HEADERS,
            json=payload
        )

        if resp.status_code == 409:
            # Conflict: record exists, update instead
            resp = requests.patch(
                f"{SUPABASE_URL}/rest/v1/pagos?conductor_id=eq.{conductor_id}",
                headers=SUPABASE_HEADERS,
                json=payload
            )

        if resp.status_code >= 400 and resp.status_code != 409:
            print(f"⚠️ Supabase error: {resp.status_code} {resp.text}")

        # Fallback: keep local copy
        pagos_conductores[conductor_id] = payload
        guardar_datos()

        print(f"💳 Pago configurado: {conductor_id[:12]}... - {data.get('banco', '')}")
        return jsonify({'status': 'ok', 'message': 'Datos de pago guardados'}), 200
    except Exception as e:
        print(f"❌ Error guardando pago: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ VER DATOS DE PAGO (Supabase)
# ============================================
@app.route('/api/pago/ver/<conductor_id>', methods=['GET'])
def ver_pago(conductor_id):
    try:
        # Try Supabase first
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/pagos?conductor_id=eq.{conductor_id}&select=*",
            headers=SUPABASE_HEADERS
        )
        if resp.status_code == 200:
            rows = resp.json()
            if rows:
                return jsonify({'status': 'ok', 'pago': rows[0]}), 200

        # Fallback to local
        pago = pagos_conductores.get(conductor_id, None)
        if pago:
            return jsonify({'status': 'ok', 'pago': pago}), 200
        else:
            return jsonify({'status': 'ok', 'pago': None, 'message': 'No hay datos de pago registrados'}), 200
    except Exception as e:
        print(f"❌ Error verificando pago: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ ADMIN - VALIDAR DOCUMENTO
# ============================================
@app.route('/api/admin/documentos/<conductor_id>/<tipo_documento>/validar', methods=['POST'])
def validar_documento(conductor_id, tipo_documento):
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
        return jsonify({'status': 'ok', 'message': f'Documento {accion}'}), 200
    except Exception as e:
        print(f"❌ Error validando documento: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ ADMIN - LISTAR DOCUMENTOS PENDIENTES
# ============================================
@app.route('/api/admin/documentos/pendientes', methods=['GET'])
def listar_documentos_pendientes():
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
        return jsonify({'status': 'ok', 'pendientes': pendientes, 'total': len(pendientes)}), 200
    except Exception as e:
        print(f"❌ Error listando pendientes: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ SERVIR ARCHIVOS SUBIDOS
# ============================================
@app.route('/uploads/documentos/<filename>', methods=['GET'])
def servir_documento(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/tablets', methods=['GET'])
def get_tablets():
    return jsonify({"count": len(tablets_data), "tablets": tablets_data}), 200

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        total_impressions = sum(int(t.get('total_impressions', 0) or 0) for t in tablets_data.values())
        online_count = sum(1 for t in tablets_data.values() if (datetime.datetime.now().timestamp() - float(t.get('last_seen', 0) or 0)) < 300)
        documentos_pendientes = sum(1 for docs in documentos_conductores.values() for doc in docs.values() if doc.get('estado') == 'pendiente_validacion')
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

@app.route('/api/documentos/foto/<conductor_id>/<tipo_documento>', methods=['GET'])
def servir_foto_documento(conductor_id, tipo_documento):
    try:
        docs = documentos_conductores.get(conductor_id, {})
        doc = docs.get(tipo_documento, {})
        foto_url = doc.get('foto_url', '')

        if not foto_url:
            return jsonify({'error': 'Documento no encontrado'}), 404

        # If Cloudinary URL, redirect
        if foto_url.startswith('http'):
            return redirect(foto_url, code=302)

        # Otherwise serve from filesystem
        filename = doc.get('nombre_archivo', '')
        # Extract filename from foto_url
        if not filename and '/' in foto_url:
            filename = foto_url.rsplit('/', 1)[-1]
        if not filename:
            return jsonify({'error': 'Documento no encontrado'}), 404
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/km-report', methods=['POST'])
def km_report():
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
        return jsonify({"status": "ok", "message": "Km reportado", "device_id": device_id[:12] + "...", "fecha": fecha, "km": km}), 200
    except Exception as e:
        print(f"❌ Error en km-report: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ CÁLCULO DE PAGOS 25% + 5%
# ============================================
@app.route('/api/payments/calculate/<conductor_id>', methods=['GET'])
def calcular_pago_conductor(conductor_id):
    try:
        if conductor_id not in tablets_data:
            return jsonify({'error': 'Conductor no encontrado'}), 404
        data = tablets_data[conductor_id]
        total_impressions = int(data.get('total_impressions', 0) or 0)
        revenue_generado = total_impressions * config['valor_por_impresion']
        fecha_hoy = datetime.datetime.now().strftime('%Y-%m-%d')
        km_acumulados_hoy = km_reports.get(conductor_id, {}).get(fecha_hoy, 0.0)
        pago_base = revenue_generado * config['porcentaje_base_conductor']
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
        pago_bono = min(bono_km + bono_impresiones + bono_documentos + bono_conectividad, revenue_generado * config['porcentaje_bono_maximo'])
        pago_total = min(pago_base + pago_bono, revenue_generado * config['porcentaje_maximo_total'])
        porcentaje_real = (pago_total / revenue_generado * 100) if revenue_generado > 0 else 0
        return jsonify({
            'conductor_id': conductor_id,
            'revenue_generado': round(revenue_generado, 2),
            'total_impressions': total_impressions,
            'km_acumulados_hoy': round(km_acumulados_hoy, 2),
            'pago_base': round(pago_base, 2),
            'bonos_detalle': {'km': round(bono_km, 2), 'impresiones': round(bono_impresiones, 2), 'documentos': round(bono_documentos, 2), 'conectividad': round(bono_conectividad, 2)},
            'pago_bono': round(pago_bono, 2),
            'pago_total': round(pago_total, 2),
            'porcentaje_real': f"{porcentaje_real:.1f}%"
        }), 200
    except Exception as e:
        print(f"❌ Error calculando pago: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/payments/calculate', methods=['GET'])
def calcular_pagos_todos():
    try:
        detalles = []
        payout_total = 0
        revenue_total = 0
        for conductor_id in tablets_data.keys():
            try:
                data = tablets_data[conductor_id]
                total_impressions = int(data.get('total_impressions', 0) or 0)
                revenue_generado = total_impressions * config['valor_por_impresion']
                fecha_hoy = datetime.datetime.now().strftime('%Y-%m-%d')
                km_acumulados_hoy = km_reports.get(conductor_id, {}).get(fecha_hoy, 0.0)
                pago_base = revenue_generado * config['porcentaje_base_conductor']
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
                pago_bono = min(bono_km + bono_impresiones + bono_documentos + bono_conectividad, revenue_generado * config['porcentaje_bono_maximo'])
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
    except Exception as e:
        print(f"❌ Error calculando pagos: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ LEGACY: CALCULAR PAGOS (FÓRMULA ANTIGUA)
# ============================================
@app.route('/api/payments/calculate-legacy', methods=['GET'])
def calculate_payments_legacy():
    try:
        now = datetime.datetime.now()
        fecha_hoy = now.strftime('%Y-%m-%d')
        payments = []
        impresiones_totales = sum(int(t.get('total_impressions', 0) or 0) for t in tablets_data.values())
        for device_id, data in tablets_data.items():
            km_recorridos = int(km_reports.get(device_id, {}).get(fecha_hoy, 0) or 0)
            horas_activas = float(data.get('uptime_hours', 0) or 0)
            impresiones_conductor = int(data.get('total_impressions', 0) or 0)
            pago_km = km_recorridos * config['tarifa_km']
            pago_horas = horas_activas * config['tarifa_hora_activa']
            share = impresiones_conductor / impresiones_totales if impresiones_totales > 0 else 0
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
        return jsonify({"status": "ok", "fecha": fecha_hoy, "total_a_pagar": sum(p['pago_total'] for p in payments), "conductores": len(payments), "detalles": payments}), 200
    except Exception as e:
        print(f"❌ Error calculando pagos legacy: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/payments/export/csv', methods=['GET'])
def export_csv():
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
        return app.response_class(response=csv_content, status=200, mimetype='text/csv', headers={'Content-Disposition': f'attachment;filename=pagos_adride_{fecha_hoy}.csv'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# ✅ VERIFICAR AUTORIZACIÓN DEL CONDUCTOR
# ============================================
@app.route('/api/autorizar/<conductor_id>', methods=['GET'])
def verificar_autorizacion(conductor_id):
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401

        # 1) Verificar registro
        registro = conductores_registrados.get(conductor_id)
        if not registro:
            return jsonify({
                'autorizado': False,
                'razon': 'No estás registrado. El administrador debe registrarte primero.',
                'registrado': False,
                'docs_aprobados': 0,
                'docs_pendientes': 0,
                'docs_rechazados': 0,
                'total_docs': 0
            })

        # 2) Verificar documentos
        docs = documentos_conductores.get(conductor_id, {})

        if not docs:
            return jsonify({
                'autorizado': False,
                'razon': 'No has subido documentos. Ve a Configuración > Documentos.',
                'registrado': True,
                'docs_aprobados': 0,
                'docs_pendientes': 0,
                'total_docs': 0
            })

        total = len(docs)
        aprobados = sum(1 for d in docs.values() if d.get('estado') == 'aprobado')
        pendientes = total - aprobados
        rechazados = sum(1 for d in docs.values() if d.get('estado') == 'rechazado')

        if pendientes > 0 or rechazados > 0:
            razon = ''
            if rechazados > 0:
                razon = f'{rechazados} documento(s) rechazado(s). Ve a Documentos y sube nuevos.'
            elif pendientes > 0:
                razon = f'Tienes {pendientes} documento(s) pendiente(s) de aprobación por el administrador.'
            return jsonify({
                'autorizado': False,
                'razon': razon,
                'registrado': True,
                'docs_aprobados': aprobados,
                'docs_pendientes': pendientes,
                'docs_rechazados': rechazados,
                'total_docs': total
            })

        return jsonify({
            'autorizado': True,
            'razon': 'Todos tus documentos están aprobados.',
            'registrado': True,
            'docs_aprobados': aprobados,
            'docs_pendientes': pendientes,
            'docs_rechazados': rechazados,
            'total_docs': total
        })
    except Exception as e:
        print(f"❌ Error verificando autorización: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ REGISTRO DE CONDUCTORES
# ============================================
@app.route('/api/registro/<conductor_id>', methods=['GET'])
def verificar_registro(conductor_id):
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401

        registro = conductores_registrados.get(conductor_id)
        if registro:
            return jsonify({
                'registrado': True,
                'nombre': registro.get('nombre', ''),
                'rut': registro.get('rut', '')
            })
        return jsonify({'registrado': False, 'nombre': '', 'rut': ''})
    except Exception as e:
        print(f"❌ Error verificando registro: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ ADMIN - REGISTRAR CONDUCTOR
# ============================================
@app.route('/api/admin/registrar-conductor', methods=['POST'])
def admin_registrar_conductor():
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401

        data = request.get_json()
        conductor_id = data.get('conductor_id', '').strip()
        nombre = data.get('nombre', '').strip()
        rut = data.get('rut', '').strip()

        if not conductor_id:
            return jsonify({'status': 'error', 'message': 'conductor_id requerido'}), 400
        if not nombre:
            return jsonify({'status': 'error', 'message': 'Nombre del conductor requerido'}), 400
        if not rut:
            return jsonify({'status': 'error', 'message': 'RUT requerido'}), 400

        conductores_registrados[conductor_id] = {
            'nombre': nombre,
            'rut': rut,
            'fecha_registro': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        guardar_datos()
        print(f"✅ Conductor registrado: {conductor_id[:12]}... - {nombre} ({rut})")
        return jsonify({
            'status': 'ok',
            'message': f'Conductor {nombre} registrado exitosamente',
            'conductor_id': conductor_id
        }), 200
    except Exception as e:
        print(f"❌ Error registrando conductor: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ ADMIN - ELIMINAR CONDUCTOR
# ============================================
@app.route('/api/admin/eliminar-conductor/<conductor_id>', methods=['POST'])
def admin_eliminar_conductor(conductor_id):
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401

        if conductor_id not in conductores_registrados:
            return jsonify({'status': 'error', 'message': 'Conductor no encontrado'}), 404

        nombre = conductores_registrados[conductor_id].get('nombre', conductor_id)
        del conductores_registrados[conductor_id]
        guardar_datos()
        print(f"🗑️ Conductor eliminado: {conductor_id[:12]}... - {nombre}")
        return jsonify({'status': 'ok', 'message': f'Conductor {nombre} eliminado'}), 200
    except Exception as e:
        print(f"❌ Error eliminando conductor: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ ADMIN - LISTAR CONDUCTORES REGISTRADOS
# ============================================
@app.route('/api/admin/conductores', methods=['GET'])
def admin_listar_conductores():
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401

        lista = []
        for cid, reg in conductores_registrados.items():
            docs = documentos_conductores.get(cid, {})
            total_docs = len(docs)
            docs_aprobados = sum(1 for d in docs.values() if d.get('estado') == 'aprobado')
            lista.append({
                'conductor_id': cid,
                'conductor_id_corto': cid[:12] + '...',
                'nombre': reg.get('nombre', ''),
                'rut': reg.get('rut', ''),
                'fecha_registro': reg.get('fecha_registro', ''),
                'total_docs': total_docs,
                'docs_aprobados': docs_aprobados,
                'docs_pendientes': total_docs - docs_aprobados
            })
        return jsonify({'status': 'ok', 'conductores': lista, 'total': len(lista)}), 200
    except Exception as e:
        print(f"❌ Error listando conductores: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ VERSIÓN Y ACTUALIZACIÓN REMOTA
# ============================================
@app.route('/api/version', methods=['GET'])
def obtener_version():
    try:
        v = version_actual
        apk_url = f"/api/apk/latest" if v.get('apk_filename') else None
        return jsonify({
            'version_code': v.get('version_code', 1),
            'version_name': v.get('version_name', '1.0.0'),
            'apk_url': apk_url,
            'update_disponible': v.get('apk_filename') is not None
        }), 200
    except Exception as e:
        print(f"❌ Error obteniendo versión: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/apk/latest', methods=['GET'])
def descargar_apk():
    try:
        filename = version_actual.get('apk_filename')
        if not filename:
            return jsonify({'error': 'No hay APK disponible'}), 404
        return send_from_directory(APK_FOLDER, filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/admin/upload-apk', methods=['POST'])
def admin_upload_apk():
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401

        if 'apk' not in request.files:
            return jsonify({'status': 'error', 'message': 'Archivo APK requerido'}), 400

        file = request.files['apk']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'Nombre de archivo vacío'}), 400

        if not file.filename.endswith('.apk'):
            return jsonify({'status': 'error', 'message': 'Solo archivos .apk son permitidos'}), 400

        filename = secure_filename(file.filename)
        # Add timestamp to avoid caching issues
        import random
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        safe_name = f"adride_{timestamp}_{filename}"
        file.save(os.path.join(APK_FOLDER, safe_name))

        # Clean up old APKs
        for old in os.listdir(APK_FOLDER):
            if old != safe_name:
                try:
                    os.remove(os.path.join(APK_FOLDER, old))
                except:
                    pass

        version_code = request.form.get('version_code', str(version_actual['version_code'] + 1))
        version_name = request.form.get('version_name', f"1.{version_code}.0")
        version_actual['version_code'] = int(version_code)
        version_actual['version_name'] = version_name
        version_actual['apk_filename'] = safe_name
        guardar_datos()

        print(f"✅ APK subido: {safe_name} (v{version_name}, code {version_code})")
        return jsonify({
            'status': 'ok',
            'message': f'APK v{version_name} subido exitosamente',
            'version_code': int(version_code),
            'version_name': version_name
        }), 200
    except Exception as e:
        print(f"❌ Error subiendo APK: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ✅ ADMIN - LIMPIAR DATOS DE PRUEBA
# ============================================
@app.route('/api/admin/limpiar-test', methods=['POST'])
def limpiar_test():
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401

        global tablets_data, km_reports, pagos_conductores, documentos_conductores, conductores_registrados

        antes_docs = len(documentos_conductores)
        documentos_conductores = {k: v for k, v in documentos_conductores.items() if not k.startswith('test_')}
        borrados_docs = antes_docs - len(documentos_conductores)

        antes_pagos = len(pagos_conductores)
        pagos_conductores = {k: v for k, v in pagos_conductores.items() if not k.startswith('test_')}
        borrados_pagos = antes_pagos - len(pagos_conductores)

        antes_tablets = len(tablets_data)
        tablets_data = {k: v for k, v in tablets_data.items() if not k.startswith('test_')}
        borrados_tablets = antes_tablets - len(tablets_data)

        antes_km = len(km_reports)
        km_reports = {k: v for k, v in km_reports.items() if not k.startswith('test_')}
        borrados_km = antes_km - len(km_reports)

        antes_reg = len(conductores_registrados)
        conductores_registrados = {k: v for k, v in conductores_registrados.items() if not k.startswith('test_')}
        borrados_reg = antes_reg - len(conductores_registrados)

        guardar_datos()

        print(f"🧹 Limpieza completada: {borrados_docs} docs, {borrados_pagos} pagos, {borrados_tablets} tablets, {borrados_km} km, {borrados_reg} registros")
        return jsonify({
            'status': 'ok',
            'message': 'Datos de prueba eliminados',
            'borrados': {
                'documentos': borrados_docs,
                'pagos': borrados_pagos,
                'tablets': borrados_tablets,
                'km_reports': borrados_km,
                'registros': borrados_reg
            }
        }), 200
    except Exception as e:
        print(f"❌ Error limpiando datos: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


cargar_datos()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
    
    
