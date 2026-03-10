from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import json
import os

app = Flask(__name__, static_folder='.')
CORS(app)  # Permitir conexiones desde las tablets

# 📊 Almacenamiento de datos de tablets
tablets_data = {}
DATA_FILE = 'tablets_data.json'

# Cargar datos guardados (si existen)
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            tablets_data = json.load(f)
        print(f"✅ Datos cargados: {len(tablets_data)} tablets")
    except:
        tablets_data = {}

# Guardar datos en archivo
def guardar_datos():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(tablets_data, f, indent=2, ensure_ascii=False)

# 🌐 Página del dashboard
@app.route('/')
def dashboard():
    return send_from_directory('.', 'dashboard.html')

# 📡 Endpoint para recibir heartbeats de las tablets
@app.route('/api/heartbeat', methods=['POST'])
def receive_heartbeat():
    try:
        data = request.json
        device_id = data.get('device_id', 'unknown')
        
        # Agregar timestamp de recepción
        data['received_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data['last_seen'] = datetime.now().timestamp()
        
        # Guardar/actualizar datos de la tablet
        tablets_data[device_id] = data
        guardar_datos()
        
        print(f"❤️ Heartbeat recibido de: {device_id[:8]}...")
        print(f"   Impresiones: {data.get('total_impressions', 0)}")
        print(f"   Red: {data.get('network_type', 'unknown')}")
        
        return jsonify({'status': 'ok', 'message': 'Heartbeat recibido'}), 200
        
    except Exception as e:
        print(f"❌ Error recibiendo heartbeat: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 📊 Endpoint para obtener datos de todas las tablets
@app.route('/api/tablets', methods=['GET'])
def get_tablets():
    return jsonify(tablets_data), 200

# 🗑️ Endpoint para borrar datos de una tablet
@app.route('/api/tablets/<device_id>', methods=['DELETE'])
def delete_tablet(device_id):
    if device_id in tablets_data:
        del tablets_data[device_id]
        guardar_datos()
        return jsonify({'status': 'ok', 'message': 'Tablet eliminada'}), 200
    return jsonify({'status': 'error', 'message': 'Tablet no encontrada'}), 404

# 🚀 Iniciar servidor
if __name__ == '__main__':
    print("=" * 50)
    print("🚗 UBER ADS IQUIQUE - SERVIDOR DASHBOARD")
    print("=" * 50)
    print("📡 Servidor iniciado en: http://localhost:5000")
    print("🌐 Dashboard disponible en: http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)