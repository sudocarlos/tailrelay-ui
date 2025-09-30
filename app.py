# app.py
from flask import Flask, request, jsonify
import caddy
import socat

app = Flask(__name__)

@app.route('/caddy/config', methods=['GET'])
@app.route('/caddy/config/', methods=['GET'])
def get_caddy_config():
    try:
        return jsonify(caddy.get_caddy_config()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/caddy/servers', methods=['GET'])
@app.route('/caddy/servers/', methods=['GET'])
def get_caddy_servers():
    try:
        return jsonify(caddy.db_list_caddy_servers()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/caddy/servers', methods=['POST'])
@app.route('/caddy/servers/', methods=['POST'])
def post_caddy_servers():
    try:
        data = request.get_json()
        server = caddy.CaddyServer(
            hostname=data["hostname"],
            port=data["port"],
            upstream_url=data["upstream_url"],
            tls_trust_pool=data.get("tls_trust_pool"),
            trusted_proxies=data.get("trusted_proxies"),
        )
        response = caddy.create_caddy_server(server)
        if response:
            server_db_entry = caddy.db_get_caddy_server(server.name)
            return jsonify(server_db_entry), 201
        else:
            return jsonify(error="Unable to configure Caddy server or add it to db."), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/caddy/servers/<server_name>', methods=['GET'])
@app.route('/caddy/servers/<server_name>/', methods=['GET'])
def get_caddy_servers_specific(server_name):
    try:
        return jsonify(caddy.db_get_caddy_server(server_name)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/caddy/servers/<server_name>', methods=['PUT'])
@app.route('/caddy/servers/<server_name>/', methods=['PUT'])
def put_caddy_servers_specific(server_name):
    try:
        data = request.get_json()
        server = caddy.CaddyServer(
            hostname=data["hostname"],
            port=data["port"],
            upstream_url=data["upstream_url"],
            tls_trust_pool=data.get("tls_trust_pool"),
            trusted_proxies=data.get("trusted_proxies"),
        )
        return jsonify(caddy.update_caddy_server(server)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/caddy/actions/start', methods=['POST'])
@app.route('/caddy/actions/start/', methods=['POST'])
def post_caddy_actions_start():
    try:
        data = request.get_json()
        server_name = data['name']
        response = caddy.start_caddy_server(server_name)
        if response.status_code == 200:
            return jsonify(caddy.db_get_caddy_server(server_name)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/caddy/actions/stop', methods=['POST'])
@app.route('/caddy/actions/stop/', methods=['POST'])
def post_caddy_actions_stop():
    try:
        data = request.get_json()
        server_name = data['name']
        if caddy.stop_caddy_server(server_name):
            return jsonify(caddy.db_get_caddy_server(server_name)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/socat/relays', methods=['GET'])
@app.route('/socat/relays/', methods=['GET'])
def get_socat_relays():
    try:
        return jsonify(socat.db_list_socat_relays()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/socat/relays', methods=['POST'])
@app.route('/socat/relays/', methods=['POST'])
def post_socat_relays():
    try:
        data = request.get_json()
        relay = socat.SocatRelay(
            listening_port=data["listening_port"],
            target_host=data["target_host"],
            target_port=data["target_port"],
            timeout=data.get("timeout"),
        )
        if relay.status:
            relay_db_entry = socat.db_insert_socat_relay(relay)
            return jsonify(socat.db_get_socat_relay(relay_db_entry)), 201
        else:
            return jsonify(error="Unable to configure Caddy server or add it to db."), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/socat/relays/<int:id>', methods=['GET'])
@app.route('/socat/relays/<int:id>/', methods=['GET'])
def get_socat_relays_by_id(id):
    try:
        return jsonify(socat.db_get_socat_relay(id)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/socat/relays/<int:id>', methods=['PUT'])
@app.route('/socat/relays/<int:id>/', methods=['PUT'])
def put_socat_relays_by_id(id):
    try:
        data = request.get_json()
        relay = socat.SocatRelay(
            listening_port=data["listening_port"],
            target_host=data["target_host"],
            target_port=data["target_port"],
            timeout=data.get("timeout"),
        )
        if relay.status:
            socat.db_update_socat_relay(relay, id)
            return jsonify(socat.db_get_socat_relay(id)), 201
        else:
            return jsonify(error="Unable to configure Caddy server or add it to db."), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/socat/actions/start', methods=['POST'])
@app.route('/socat/actions/start/', methods=['POST'])
def post_socat_actions_start():
    try:
        data = request.get_json()
        relay_id = data['id']
        relay = socat.socat_relay_from_db(relay_id)
        relay.start()
        if relay.status == 'running':
            socat.db_update_socat_relay(relay, relay_id)
            return jsonify(socat.db_get_socat_relay(relay_id)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/socat/actions/stop', methods=['POST'])
@app.route('/socat/actions/stop/', methods=['POST'])
def post_socat_actions_stop():
    try:
        data = request.get_json()
        relay_id = data['id']
        relay = socat.socat_relay_from_db(relay_id)
        relay.stop()
        if relay.status == 'stopped':
            socat.db_update_socat_relay(relay, relay_id)
            return jsonify(socat.db_get_socat_relay(relay_id)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# @app.route('/backup', methods=['GET'])
# @app.route('/restore', methods=['POST'])

# # Health check
# @app.route('/health', methods=['GET'])
# def health_check():
#     """Health check endpoint"""
#     return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    # Initialize databases
    caddy.init_db()
    
    # Start the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)