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
import csv
import io

# ========================================
# CONFIGURACIÓN DE LA APP
# ========================================
app = Flask(__name__, static_folder='.')  # Servir archivos estáticos desde raíz
CORS(app)  # Habilitar CORS para todas las rutas

# ========================================
# CONFIGURACIÓN DE SEGURIDAD
# ========================================
API_KEY = os.environ.get('API_KEY', 'adride_iquique_2024_secreto')

# ========================================
# ALMACENAMIENTO DE DATOS
# ========================================
# Diccionario en memoria para almacenar datos de tablets
tablets_data = {}

# ✅ NUEVO: Reporte de kilómetros por conductor
km_reports = {}

# Archivos para persistencia
DATA_FILE = 'tablets_data.json'
KM_FILE = 'km_reports.json'


# ========================================
# FUNCIONES DE PERSISTENCIA
# ========================================
def guardar_datos():
    """Guarda tablets_data y km_reports en archivos JSON"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(tablets_data, f, indent=2, ensure_ascii=False)
        
        with open(KM_FILE, 'w', encoding='utf-8') as f:
            json.dump(km_reports, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Datos guardados: {len(tablets_data)} tablets, {len(km_reports)} conductores")
    except Exception as e:
        print(f"⚠️ Error guardando datos: {e}")


def cargar_datos():
    """Carga tablets_data y km_reports desde archivos JSON al iniciar"""
    global tablets_data, km_reports
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                tablets_data = json.load(f)
            print(f"✅ Tablets cargadas: {len(tablets_data)}")
        
        if os.path.exists(KM_FILE):
            with open(KM_FILE, 'r', encoding='utf-8') as f:
                km_reports = json.load(f)
            print(f"✅ Reportes de km cargados: {len(km_reports)} conductores")
    except Exception as e:
        print(f"⚠️ Error cargando datos: {e}")
        tablets_data = {}
        km_reports = {}


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
    """
    try:
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
    """Endpoint para obtener estadísticas resumidas"""
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
        if not verificar_api_key():
            print(f"⚠️ Intento no autorizado desde: {request.remote_addr}")
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON required'}), 400
        
        device_id = data.get('device_id', 'unknown')
        
        data['received_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data['last_seen'] = datetime.datetime.now().timestamp()
        data['server_ip'] = request.remote_addr
        
        tablets_data[device_id] = data
        guardar_datos()
        
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
    """
    try:
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
    Endpoint protegido para resetear todos los datos.
    """
    try:
        if not verificar_api_key():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
        confirm = request.json.get('confirm', '') if request.json else ''
        if confirm != 'RESET_CONFIRM':
            return jsonify({'status': 'error', 'message': 'Confirmación requerida'}), 400
        
        global tablets_data, km_reports
        count_tablets = len(tablets_data)
        count_km = len(km_reports)
        tablets_data = {}
        km_reports = {}
        guardar_datos()
        
        print(f"🔄 Datos reseteados: {count_tablets} tablets, {count_km} reportes de km eliminados")
        return jsonify({'status': 'ok', 'message': f'{count_tablets} tablets y {count_km} reportes eliminados'}), 200
        
    except Exception as e:
        print(f"❌ Error en POST /api/reset: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/km-report', methods=['POST'])
def report_km():
    """
    Endpoint para que conductores reporten km recorridos diariamente.
    Requiere header: X-API-Key: <tu_clave_secreta>
    """
    try:
        if not verificar_api_key():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'JSON required'}), 400
        
        device_id = data.get('device_id')
        km_recorridos = data.get('km_recorridos', 0)
        fecha = data.get('fecha', datetime.datetime.now().strftime('%Y-%m-%d'))
        
        if not device_id:
            return jsonify({'status': 'error', 'message': 'device_id required'}), 400
        
        if km_recorridos < 0 or km_recorridos > 500:
            return jsonify({'status': 'error', 'message': 'Km inválidos (0-500)'}), 400
        
        if device_id not in km_reports:
            km_reports[device_id] = {}
        
        km_reports[device_id][fecha] = km_recorridos
        guardar_datos()
        
        print(f"📍 Km reportados: {device_id[:12]}... | {km_recorridos} km | {fecha}")
        
        return jsonify({
            'status': 'ok',
            'message': f'{km_recorridos} km registrados para {fecha}',
            'device_id': device_id[:12] + '...',
            'fecha': fecha
        }), 200
        
    except Exception as e:
        print(f"❌ Error reportando km: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ========================================
# RUTAS DE PAGOS
# ========================================
@app.route('/api/payments/calculate', methods=['GET'])
def calculate_payments():
    """
    Calcula pagos basados en km + impresiones.
    No requiere API Key para lectura.
    """
    try:
        now = datetime.datetime.now()
        fecha_hoy = now.strftime('%Y-%m-%d')
        
        config = {
            "tarifa_km": 15,
            "tarifa_impresion": 0.03,
            "bono_horas_pico_porcentaje": 0.20,
            "max_impresiones_por_km": 50,
            "km_minimos_bono": 50
        }
        
        payments = []
        
        for device_id, data in tablets_data.items():
            km_recorridos = km_reports.get(device_id, {}).get(fecha_hoy, 0)
            impresiones = data.get('total_impressions', 0)
            
            impresiones_por_km = impresiones / max(1, km_recorridos) if km_recorridos > 0 else impresiones
            es_posible_fraude = impresiones_por_km > config['max_impresiones_por_km'] and impresiones > 100
            
            pago_km = km_recorridos * config['tarifa_km']
            pago_impresiones = impresiones * config['tarifa_impresion']
            
            bono_pico = (pago_km + pago_impresiones) * config['bono_horas_pico_porcentaje'] if km_recorridos >= config['km_minimos_bono'] else 0
            
            pago_total = pago_km + pago_impresiones + bono_pico
            
            penalizacion = 0
            if es_posible_fraude:
                penalizacion = pago_total * 0.5
                pago_total *= 0.5
            
            payments.append({
                "device_id": device_id[:12] + "...",
                "device_id_completo": device_id,
                "km_recorridos": km_recorridos,
                "impresiones": impresiones,
                "impresiones_por_km": round(impresiones_por_km, 1),
                "pago_km": round(pago_km),
                "pago_impresiones": round(pago_impresiones),
                "bono_pico": round(bono_pico),
                "penalizacion_fraude": round(penalizacion),
                "pago_total": round(pago_total),
                "alerta_fraude": es_posible_fraude,
                "fecha": fecha_hoy
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
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/payments/export/csv', methods=['GET'])
def export_payments_csv():
    """
    Exporta pagos en formato CSV para transferencia bancaria.
    """
    try:
        response = calculate_payments()
        data = response[0].json if hasattr(response[0], 'json') else response
        
        if isinstance(data, tuple):
            data = data[0].json if hasattr(data[0], 'json') else data[0]
        
        if data.get('status') != 'ok':
            return jsonify({'error': 'No se pudieron calcular pagos'}), 500
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'Fecha', 'Device ID', 'Km Recorridos', 'Impresiones', 'Imp/Km',
            'Pago Km', 'Pago Impresiones', 'Bono Pico', 'Penalización', 'PAGO TOTAL', 'Alerta Fraude'
        ])
        
        for p in data.get('detalles', []):
            writer.writerow([
                data.get('fecha'),
                p.get('device_id_completo'),
                p.get('km_recorridos'),
                p.get('impresiones'),
                p.get('impresiones_por_km'),
                p.get('pago_km'),
                p.get('pago_impresiones'),
                p.get('bono_pico'),
                p.get('penalizacion_fraude'),
                p.get('pago_total'),
                'SI' if p.get('alerta_fraude') else 'NO'
            ])
        
        output.seek(0)
        
        return output.getvalue(), 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename=pagos_adride_{data.get("fecha")}.csv'
        }
        
    except Exception as e:
        print(f"❌ Error exportando CSV: {e}")
        return jsonify({'error': str(e)}), 500


# ========================================
# HEALTH CHECK
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
# ENTRY POINT PARA DESARROLLO LOCAL
# ========================================
if __name__ == '__main__':
    # 👇 DEFINIR debug_mode PRIMERO (antes de cualquier print que lo use)
    debug_mode = os.environ.get('FLASK_ENV', 'production') == 'development'
    
    print("=" * 60)
    print("🚗 ADRIDE SERVER - Dashboard Backend")
    print("=" * 60)
    print(f"🔑 API Key configurada: {'✅ Sí' if API_KEY != 'adride_iquique_2024_secreto' else '⚠️ Default'}")
    print(f"📊 Tablets cargadas: {len(tablets_data)}")
    print(f"📍 Reportes de km cargados: {len(km_reports)}")
    print(f"🔧 Modo debug: {'✅ Sí' if debug_mode else '❌ No'}")
    print("🌐 Servidor corriendo en: http://0.0.0.0:5000")
    print("🔗 Dashboard: http://localhost:5000")
    print("🔗 API Tablets: http://localhost:5000/api/tablets")
    print("🔗 Health Check: http://localhost:5000/health")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=debug_mode)
    
