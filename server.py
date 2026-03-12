# ========================================
# ADRIDE SERVER - Backend Flask para Render
# ========================================
# Servidor para recibir heartbeats de tablets
# y servir dashboard en tiempo real
# ========================================

# ========================================
# IMPORTS
# ========================================
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
import datetime

# ========================================
# CONFIGURACIÓN DE LA APP
# ========================================
app = Flask(__name__, static_folder='.')  # Servir archivos estáticos desde raíz
CORS(app)  # Habilitar CORS para todas las rutas (necesario para fetch desde el navegador)

# ========================================
# CONFIGURACIÓN DE SEGURIDAD
# ========================================
# API Key para proteger endpoints (se define en Variables de Entorno de Render)
API_KEY = os.environ.get('API_KEY', 'dev_key_123')

# ========================================
# ALMACENAMIENTO DE DATOS
# ========================================
# Diccionario en memoria para almacenar datos de tablets
# Formato: { device_id: { ...datos... } }
tablets_data = {}

# Archivo para persistencia básica (se guarda en el disco efímero de Render)
DATA_FILE = 'tablets_data.json'


# ========================================
# FUNCIONES DE PERSISTENCIA
# ========================================
def guardar_datos():
    """Guarda tablets_data en archivo JSON para persistencia básica"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(tablets_data, f, indent=2, ensure_ascii=False)
        print(f"💾 Datos guardados: {len(tablets_data)} tablets")
    except Exception as e:
        print(f"⚠️ Error guardando datos: {e}")


def cargar_datos():
    """Carga tablets_data desde archivo JSON al iniciar el servidor"""
    global tablets_data
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                tablets_data = json.load(f)
            print(f"✅ Datos cargados: {len(tablets_data)} tablets")
    except Exception as e:
        print(f"⚠️ Error cargando datos: {e}")
        tablets_data = {}  # Resetear en caso de error


# Cargar datos al iniciar el servidor
cargar_datos()


# ========================================
# MIDDLEWARE / UTILIDADES
# ========================================
def verificar_api_key():
    """Verifica que la petición incluya la API Key correcta"""
    request_key = request.headers.get('X-API-Key')
    return request_key == API_KEY


# ========================================
# RUTAS DEL FRONTEND (HTML/JS)
# ========================================
@app.route('/')
def serve_dashboard():
    """Sirve el archivo dashboard.html como página principal"""
    return send_from_directory('.', 'dashboard.html')


@app.route('/<path:filename>')
def serve_static(filename):
    """Sirve archivos estáticos (CSS, JS, imágenes) para el dashboard"""
    return send_from_directory('.', filename)


# ========================================
# RUTAS DE LA API PÚBLICA (GET)
# ========================================
@app.route('/api/tablets', methods=['GET'])
def get_tablets():
    """
    Endpoint público para que el dashboard obtenga los datos de todas las tablets.
    No requiere API Key para lectura (puedes agregarla si quieres más seguridad).
    """
    try:
        # Filtrar datos sensibles si es necesario
        public_data = {}
        for device_id, data in tablets_data.items():
            public_data[device_id] = {
                'device_id': data.get('device_id', 'unknown')[:12] + '...',
                'total_impressions': data.get('total_impressions', 0),
                'network_type': data.get('network_type', 'unknown'),
                'last_seen': data.get('last_seen', 0),
                'received_at': data.get('received_at', 'never'),
                'app_version': data.get('app_version', '1.0')
            }
        return jsonify({'tablets': public_data, 'count': len(public_data)}), 200
    except Exception as e:
        print(f"❌ Error en GET /api/tablets: {e}")
        return jsonify({'error': str(e), 'status': 'failed'}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Endpoint para obtener estadísticas resumidas (opcional)"""
    try:
        total_impressions = sum(t.get('total_impressions', 0) for t in tablets_data.values())
        online_count = sum(1 for t in tablets_data.values() 
                          if (datetime.datetime.now().timestamp() - t.get('last_seen', 0)) < 300)
        
        return jsonify({
            'total_tablets': len(tablets_data),
            'online_tablets': online_count,
            'total_impressions': total_impressions,
            'last_update': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200
    except Exception as e:
        print(f"❌ Error en GET /api/stats: {e}")
        return jsonify({'error': str(e)}), 500


# ========================================
# RUTAS DE LA API PROTEGIDA (POST/DELETE)
# ========================================
@app.route('/api/heartbeat', methods=['POST'])
def receive_heartbeat():
    """
    Endpoint protegido para recibir heartbeats de las tablets Android.
    Requiere header: X-API-Key: <tu_clave_secreta>
    """
    try:
        # 🔐 Verificar API Key
        if not verificar_api_key():
            print(f"⚠️ Intento no autorizado desde: {request.remote_addr}")
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
        # Parsear JSON recibido
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON required'}), 400
        
        device_id = data.get('device_id', 'unknown')
        
        # Agregar metadata de recepción
        data['received_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data['last_seen'] = datetime.datetime.now().timestamp()
        data['server_ip'] = request.remote_addr
        
        # Actualizar/crear registro de la tablet
        tablets_data[device_id] = data
        guardar_datos()
        
        # Log para debugging
        impresiones = data.get('total_impressions', 0)
        red = data.get('network_type', 'unknown')
        print(f"❤️ Heartbeat de: {device_id[:12]}... | Impresiones: {impresiones} | Red: {red}")
        
        return jsonify({
            'status': 'ok', 
            'message': 'Heartbeat recibido',
            'device_id': device_id[:12] + '...',
            'timestamp': data['received_at']
        }), 200
        
    except Exception as e:
        print(f"❌ Error en POST /api/heartbeat: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/tablets/<device_id>', methods=['DELETE'])
def delete_tablet(device_id):
    """
    Endpoint protegido para eliminar una tablet de la lista.
    Útil para mantenimiento o cuando un conductor deja el programa.
    """
    try:
        # 🔐 Verificar API Key
        if not verificar_api_key():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
        if device_id in tablets_data:
            deleted = tablets_data.pop(device_id)
            guardar_datos()
            print(f"🗑️ Tablet eliminada: {device_id[:12]}...")
            return jsonify({
                'status': 'ok', 
                'message': 'Tablet eliminada',
                'deleted_data': deleted
            }), 200
        
        return jsonify({'status': 'error', 'message': 'Tablet no encontrada'}), 404
        
    except Exception as e:
        print(f"❌ Error en DELETE /api/tablets/{device_id}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_data():
    """
    Endpoint protegido para resetear todos los datos (ÚSALO CON CUIDADO).
    Útil para pruebas o reinicio de campaña.
    """
    try:
        # 🔐 Verificar API Key + confirmación explícita
        if not verificar_api_key():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
        confirm = request.json.get('confirm', '') if request.json else ''
        if confirm != 'RESET_CONFIRM':
            return jsonify({'status': 'error', 'message': 'Confirmación requerida'}), 400
        
        global tablets_data
        count = len(tablets_data)
        tablets_data = {}
        guardar_datos()
        
        print(f"🔄 Datos reseteados: {count} tablets eliminadas")
        return jsonify({'status': 'ok', 'message': f'{count} tablets eliminadas'}), 200
        
    except Exception as e:
        print(f"❌ Error en POST /api/reset: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ========================================
# HEALTH CHECK (Para monitoreo de Render)
# ========================================
@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint simple para verificar que el servidor está respondiendo"""
    return jsonify({
        'status': 'healthy',
        'service': 'adride-server',
        'timestamp': datetime.datetime.now().isoformat(),
        'tablets_count': len(tablets_data)
    }), 200


# ========================================
# MANEJO DE ERRORES GLOBAL
# ========================================
@app.errorhandler(404)
def not_found(error):
    """Maneja rutas no encontradas de forma amigable"""
    return jsonify({'error': 'Endpoint no encontrado', 'path': request.path}), 404


@app.errorhandler(500)
def internal_error(error):
    """Maneja errores internos del servidor"""
    print(f"❌ Error interno del servidor: {error}")
    return jsonify({'error': 'Error interno del servidor'}), 500


# ========================================
# ENTRY POINT PARA GUNICORN (Render)
# ========================================
# Esta variable 'app' es la que usa Gunicorn automáticamente
# No necesitas modificar nada aquí para Render

# Bloque para desarrollo local (se ignora en Render)
# ========================================
# ENTRY POINT PARA DESARROLLO LOCAL
# ========================================
if __name__ == '__main__':
    print("=" * 60)
    print("🚗 ADRIDE SERVER - Dashboard Backend")
    print("=" * 60)
    print(f"🔑 API Key configurada: {'✅ Sí' if API_KEY != 'dev_key_123' else '⚠️ Default'}")
    print(f"📊 Tablets cargadas: {len(tablets_data)}")
    print(f"🔧 Modo debug: {'✅ Sí' if debug_mode else '❌ No'}")
    print("🌐 Servidor corriendo en: http://0.0.0.0:5000")
    print("🔗 Dashboard: http://localhost:5000")
    print("🔗 API Tablets: http://localhost:5000/api/tablets")
    print("🔗 Health Check: http://localhost:5000/health")
    print("=" * 60)
    
    # 👇 Determinar modo debug desde variable de entorno
    debug_mode = os.environ.get('FLASK_ENV', 'production') == 'development'
    
    # debug solo en desarrollo local, nunca en producción
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=debug_mode)
    
