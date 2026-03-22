from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import datetime
from werkzeug.utils import secure_filename  # ✅ NUEVO: Para subir archivos

app = Flask(__name__, static_folder='.')
CORS(app)  # ✅ Habilitar CORS para el dashboard y app Android

# ✅ CONFIGURACIÓN PARA SUBIDA DE ARCHIVOS (NUEVO)
UPLOAD_FOLDER = 'uploads/documentos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB máximo por foto
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

# Archivos de datos
DATA_FILE = 'tablets_data.json'
KM_FILE = 'km_reports.json'
PAGOS_FILE = 'pagos_conductores.json'  # ✅ NUEVO: Datos bancarios
DOCUMENTOS_FILE = 'documentos_conductores.json'  # ✅ NUEVO: Documentos subidos

# Variables globales
tablets_data = {}
km_reports = {}
pagos_conductores = {}  # ✅ NUEVO
documentos_conductores = {}  # ✅ NUEVO

# ✅ CONFIGURACIÓN DE NEGOCIO ADRIDE - PILOTO
config = {
    "tarifa_km": 15,
    "tarifa_hora_activa": 500,
    "presupuesto_total_mensual": 250000,
    "porcentaje_para_conductores": 0.40,
    "porcentaje_para_adride": 0.60,
    "dias_mes": 30,
    "km_minimos_bono": 50,
    "bono_horas_pico_porcentaje": 0.20
}

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
        
        # ✅ NUEVO: Cargar pagos
        if os.path.exists(PAGOS_FILE):
            with open(PAGOS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                pagos_conductores = json.loads(content) if content else {}
            print(f"✅ Pagos cargados: {len(pagos_conductores)}")
        
        # ✅ NUEVO: Cargar documentos
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
        # ✅ NUEVO: Guardar pagos
        with open(PAGOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(pagos_conductores, f, indent=2, ensure_ascii=False)
        # ✅ NUEVO: Guardar documentos
        with open(DOCUMENTOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(documentos_conductores, f, indent=2, ensure_ascii=False)
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
        
        tablets_data[device_id] = {
            "device_id": device_id,
            "model": data.get('model', 'Unknown'),
            "android_version": data.get('android_version', 'Unknown'),
            "app_version": data.get('app_version', '1.0'),
            "timestamp": data.get('timestamp', str(datetime.datetime.now().timestamp())),
            "total_impressions": data.get('total_impressions', '0'),
            "uptime_hours": data.get('uptime_hours', '0'),
            "network_type": data.get('network_type', 'unknown'),
            "is_charging": data.get('is_charging', 'false'),
            "ads_count": data.get('ads_count', '0'),
            "ad_impressions": data.get('ad_impressions', {}),
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

# ============================================
# ✅ NUEVO: SUBIR DOCUMENTO (CRÍTICO)
# ============================================
@app.route('/api/documentos/subir', methods=['POST'])
def subir_documento():
    """Recibe foto de documento desde app Android"""
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
        
        # ✅ Verificar que viene la foto
        if 'foto' not in request.files:
            return jsonify({'status': 'error', 'message': 'No se recibió la foto'}), 400
        
        foto = request.files['foto']
        conductor_id = request.form.get('conductor_id')
        tipo_documento = request.form.get('tipo_documento')
        
        if not conductor_id or not tipo_documento:
            return jsonify({'status': 'error', 'message': 'Faltan datos'}), 400
        
        if foto.filename == '' or not allowed_file(foto.filename):
            return jsonify({'status': 'error', 'message': 'Archivo inválido'}), 400
        
        # ✅ Guardar archivo con nombre seguro
        filename = f"{conductor_id}_{tipo_documento}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        foto.save(filepath)
        
        # ✅ Guardar registro en JSON
        if conductor_id not in documentos_conductores:
            documentos_conductores[conductor_id] = {}
        
        documentos_conductores[conductor_id][tipo_documento] = {
            'tipo_documento': tipo_documento,
            'foto_url': f'/uploads/documentos/{filename}',
            'estado': 'pendiente_validacion',  # pendiente, aprobado, rechazado
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
# ✅ NUEVO: VER ESTADO DE DOCUMENTOS
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
# ✅ NUEVO: GUARDAR DATOS DE PAGO (CRÍTICO)
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
        
        # ✅ Guardar datos de pago
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
# ✅ NUEVO: VER DATOS DE PAGO
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
# ✅ NUEVO: ADMIN - VALIDAR DOCUMENTO
# ============================================
@app.route('/api/admin/documentos/<conductor_id>/<tipo_documento>/validar', methods=['POST'])
def validar_documento(conductor_id, tipo_documento):
    """Admin aprueba o rechaza documento"""
    try:
        api_key = request.headers.get('X-API-Key')
        if api_key != 'adride_iquique_2024_secreto':
            return jsonify({'status': 'error', 'message': 'API Key inválida'}), 401
        
        data = request.get_json()
        accion = data.get('accion')  # 'aprobado' o 'rechazado'
        comentario = data.get('comentario', '')
        
        if accion not in ['aprobado', 'rechazado']:
            return jsonify({'status': 'error', 'message': 'Acción inválida'}), 400
        
        if conductor_id not in documentos_conductores:
            return jsonify({'status': 'error', 'message': 'Conductor no encontrado'}), 404
        
        if tipo_documento not in documentos_conductores[conductor_id]:
            return jsonify({'status': 'error', 'message': 'Documento no encontrado'}), 404
        
        # ✅ Actualizar estado
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
# ✅ NUEVO: ADMIN - ELIMINAR DOCUMENTO
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
        
        # ✅ Obtener ruta de la foto para eliminarla
        doc_data = documentos_conductores[conductor_id][tipo_documento]
        foto_url = doc_data.get('foto_url', '')
        
        # ✅ Eliminar archivo físico si existe
        if foto_url:
            try:
                # Extraer nombre del archivo de la URL
                filename = foto_url.replace('/uploads/documentos/', '')
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"🗑️ Archivo eliminado: {filepath}")
            except Exception as e:
                print(f"⚠️ Error eliminando archivo: {e}")
        
        # ✅ Eliminar registro del JSON
        del documentos_conductores[conductor_id][tipo_documento]
        
        # ✅ Si no hay más documentos para este conductor, limpiar entrada
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
# ✅ NUEVO: ADMIN - LISTAR DOCUMENTOS PENDIENTES
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
        
        # ✅ NUEVO: Contar documentos pendientes
        documentos_pendientes = sum(
            1 for docs in documentos_conductores.values()
            for doc in docs.values()
            if doc.get('estado') == 'pendiente_validacion'
        )
        
        return jsonify({
            "total_tablets": len(tablets_data),
            "online_tablets": online_count,
            "total_impressions": total_impressions,
            "documentos_pendientes": documentos_pendientes,  # ✅ NUEVO
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
    """Calcula pagos basados en: km + horas activas + share del fondo mensual"""
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

# ============================================
# ✅ NUEVO: SERVIR ARCHIVOS SUBIDOS
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
    
