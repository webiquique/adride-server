from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import datetime

app = Flask(__name__, static_folder='.')
CORS(app)  # ✅ Habilitar CORS para el dashboard

# Archivos de datos
DATA_FILE = 'tablets_data.json'
KM_FILE = 'km_reports.json'

# Variables globales
tablets_data = {}
km_reports = {}

# ✅ CONFIGURACIÓN DE NEGOCIO ADRIDE - PILOTO
config = {
    # Tarifas base para conductores
    "tarifa_km": 15,                    # $15 CLP por km recorrido
    "tarifa_hora_activa": 500,          # $500 CLP por hora con tablet encendida
    
    # Distribución del presupuesto mensual del piloto
    "presupuesto_total_mensual": 250000,  # $250,000 CLP/mes TOTAL del piloto
    "porcentaje_para_conductores": 0.40,  # 40% para repartir entre conductores
    "porcentaje_para_adride": 0.60,       # 60% para sostenibilidad
    
    # Cálculos auxiliares
    "dias_mes": 30,                      # Para prorrateo mensual → diario
    "km_minimos_bono": 50,              # Km mínimos para bono horas pico
    "bono_horas_pico_porcentaje": 0.20  # 20% bono adicional si km >= 50
}

# Calcular fondo diario para conductores
fondo_conductores_mensual = config["presupuesto_total_mensual"] * config["porcentaje_para_conductores"]
fondo_conductores_diario = fondo_conductores_mensual / config["dias_mes"]  # ~$3,333/día

def cargar_datos():
    """Carga tablets_data y km_reports desde archivos JSON al iniciar"""
    global tablets_data, km_reports
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    tablets_data = json.loads(content)
                else:
                    tablets_data = {}
            print(f"✅ Tablets cargadas: {len(tablets_data)}")
        
        if os.path.exists(KM_FILE):
            with open(KM_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    km_reports = json.loads(content)
                else:
                    km_reports = {}
            print(f"✅ Reportes de km cargados: {len(km_reports)}")
    except Exception as e:
        print(f"⚠️ Error cargando datos: {e}")
        tablets_data = {}
        km_reports = {}

def guardar_datos():
    """Guarda tablets_data y km_reports en archivos JSON"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(tablets_data, f, indent=2, ensure_ascii=False)
        with open(KM_FILE, 'w', encoding='utf-8') as f:
            json.dump(km_reports, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error guardando datos: {e}")

@app.route('/')
def index():
    """Sirve el dashboard HTML"""
    return send_from_directory('.', 'dashboard.html')

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
        
        # Guardar/actualizar datos de la tablet
        tablets_data[device_id] = {
            "device_id": device_id,
            "model": data.get('model', 'Unknown'),
            "android_version": data.get('android_version', 'Unknown'),
            "app_version": data.get('app_version', '1.0'),
            "timestamp": data.get('timestamp', str(datetime.datetime.now().timestamp())),
            "total_impressions": data.get('total_impressions', '0'),
            "uptime_hours": data.get('uptime_hours', '0'),  # ✅ NUEVO: horas activas
            "network_type": data.get('network_type', 'unknown'),
            "is_charging": data.get('is_charging', 'false'),
            "ads_count": data.get('ads_count', '0'),
            "ad_impressions": data.get('ad_impressions', {}),  # ✅ Impresiones por anuncio
            "received_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "last_seen": datetime.datetime.now().timestamp()
        }
        
        guardar_datos()
        
        print(f"❤️ Heartbeat recibido: {device_id[:12]}... | Impresiones: {data.get('total_impressions', 0)}")
        
        return jsonify({
            "status": "ok",
            "message": "Heartbeat recibido",
            "device_id": device_id[:12] + "...",
            "received_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200
        
    except Exception as e:
        print(f"❌ Error en heartbeat: {e}")
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
        
        return jsonify({
            "total_tablets": len(tablets_data),
            "online_tablets": online_count,
            "total_impressions": total_impressions,
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

@app.route('/api/payments/calculate', methods=['GET'])
def calculate_payments():
    """
    Calcula pagos basados en: km + horas activas + share del fondo mensual (40%)
    Fórmula: (km×$15) + (horas×$500) + (share×$3,333) + bono_pico
    """
    try:
        now = datetime.datetime.now()
        fecha_hoy = now.strftime('%Y-%m-%d')
        
        payments = []
        
        # Calcular impresiones totales globales (para share)
        impresiones_totales = sum(
            int(t.get('total_impressions', 0) or 0) 
            for t in tablets_data.values()
        )
        
        for device_id, data in tablets_data.items():
            # ✅ DATOS BÁSICOS DEL CONDUCTOR
            km_recorridos = int(km_reports.get(device_id, {}).get(fecha_hoy, 0) or 0)
            horas_activas = float(data.get('uptime_hours', 0) or 0)
            impresiones_conductor = int(data.get('total_impressions', 0) or 0)
            
            # ✅ 1. PAGO POR KM
            pago_km = km_recorridos * config['tarifa_km']
            
            # ✅ 2. BONO POR HORA ACTIVA
            pago_horas = horas_activas * config['tarifa_hora_activa']
            
            # ✅ 3. SHARE DEL FONDO PARA CONDUCTORES
            if impresiones_totales > 0:
                share = impresiones_conductor / impresiones_totales
            else:
                share = 0
            
            pago_fondo = share * fondo_conductores_diario
            
            # ✅ 4. SUBTOTAL
            subtotal = pago_km + pago_horas + pago_fondo
            
            # ✅ 5. BONO HORAS PICO (si km >= 50)
            bono_pico = subtotal * config['bono_horas_pico_porcentaje'] if km_recorridos >= config['km_minimos_bono'] else 0
            
            # ✅ 6. TOTAL FINAL
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
        
        # Ordenar por pago total descendente
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
        
        csv_content = "device_id,km_recorridos,horas_activas,pago_km,pago_horas,pago_fondo,bono_pico,pago_total,fecha\n"
        
        for device_id, data in tablets_data.items():
            km_recorridos = int(km_reports.get(device_id, {}).get(fecha_hoy, 0) or 0)
            horas_activas = float(data.get('uptime_hours', 0) or 0)
            impresiones_conductor = int(data.get('total_impressions', 0) or 0)
            
            pago_km = km_recorridos * config['tarifa_km']
            pago_horas = horas_activas * config['tarifa_hora_activa']
            
            impresiones_totales = sum(int(t.get('total_impressions', 0) or 0) for t in tablets_data.values())
            share = impresiones_conductor / impresiones_totales if impresiones_totales > 0 else 0
            pago_fondo = share * fondo_conductores_diario
            
            subtotal = pago_km + pago_horas + pago_fondo
            bono_pico = subtotal * config['bono_horas_pico_porcentaje'] if km_recorridos >= config['km_minimos_bono'] else 0
            pago_total = subtotal + bono_pico
            
            csv_content += f"{device_id},{km_recorridos},{horas_activas},{pago_km},{pago_horas},{pago_fondo},{bono_pico},{pago_total},{fecha_hoy}\n"
        
        return app.response_class(
            response=csv_content,
            status=200,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename=pagos_adride_{fecha_hoy}.csv'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Cargar datos al iniciar
cargar_datos()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
    
