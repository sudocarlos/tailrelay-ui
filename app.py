import sqlite3
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, render_template_string
import json
import os
from socat import start_socat_proxy, stop_socat_proxy, check_socat_installed

# Database file path
DB_PATH = Path.home() / ".socat_proxy.db"

# Global store for active proxy processes
active_processes = {}

app = Flask(__name__)

def init_database():
    """Initialize the SQLite database for process tracking."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Create table for proxy processes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS proxy_processes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listening_port INTEGER NOT NULL,
                    target_host TEXT NOT NULL,
                    target_port INTEGER NOT NULL,
                    process_id INTEGER,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    stop_time TIMESTAMP,
                    status TEXT DEFAULT 'running'
                )
            ''')
            
    except sqlite3.Error as e:
        print(f"Database initialization failed: {e}")

def get_db_connection():
    """Create and return a database connection."""
    return sqlite3.connect(DB_PATH)

def create_proxy_in_db(listening_port, target_host, target_port, process_id):
    """Insert a new proxy into the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO proxy_processes 
        (listening_port, target_host, target_port, process_id, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        listening_port,
        target_host,
        target_port,
        process_id,
        "running"
    ))
    
    proxy_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return proxy_id

def get_proxy_from_db(proxy_id):
    """Retrieve proxy information by ID."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    proxy = cursor.execute(
        'SELECT * FROM proxy_processes WHERE id = ?', 
        (proxy_id,)
    ).fetchone()
    conn.close()
    return proxy

def get_all_proxies_from_db():
    """Retrieve all proxies from the database."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    proxies = cursor.execute('SELECT * FROM proxy_processes').fetchall()
    conn.close()
    
    return proxies

def update_proxy_status_in_db(proxy_id, process_id=None, status='stopped', stop_time=None):
    """Update proxy status in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if stop_time:
        cursor.execute('''
            UPDATE proxy_processes 
            SET process_id = ?, status = ?, stop_time = ?
            WHERE id = ?
        ''', (process_id, status, stop_time, proxy_id))
    else:
        cursor.execute('''
            UPDATE proxy_processes 
            SET process_id = ?, status = ?, stop_time = NULL
            WHERE id = ?
        ''', (process_id, status, proxy_id))
    
    conn.commit()
    conn.close()

def delete_proxy_from_db(proxy_id):
    """Delete a proxy from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM proxy_processes WHERE id = ?', (proxy_id,))
    conn.commit()
    conn.close()

def check_process_status(process_id):
    """Check actual status of a process on the system."""
    if process_id is None:
        return "stopped"
    
    try:
        import os
        os.kill(process_id, 0)  # Check if process exists
        return "running"
    except OSError:
        return "stopped"

def proxy_config_exists(listening_port, target_host, target_port):
    """Check if a proxy with the given configuration already exists in the database."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) as count 
        FROM proxy_processes 
        WHERE listening_port = ? 
        AND target_host = ? 
        AND target_port = ?
    ''', (listening_port, target_host, target_port))
    
    result = cursor.fetchone()
    conn.close()
    
    return result['count'] > 0

@app.before_request
def initialize():
    """Initialize the application before each request."""
    init_database()

# Serve the index.html file at root path
@app.route('/', methods=['GET'])
def index():
    return send_from_directory('static', 'index.html')

@app.route('/proxy', methods=['POST'])
def create_proxy():
    """Configure and start a new socat proxy."""
    try:
        data = request.get_json()

        if proxy_config_exists(data['listening_port'], data['target_host'], data['target_port']):
            return jsonify({"error": "A proxy with this configuration already exists"}), 400

        # Proceed with creation
        process = start_socat_proxy(
            data['listening_port'],
            data['target_host'],
            data['target_port']
        )
        
        proxy_id = create_proxy_in_db(
            data['listening_port'],
            data['target_host'],
            data['target_port'],
            process.pid
        )
        
        # Store in memory
        active_processes[proxy_id] = process
        
        return jsonify({
            "id": proxy_id,
            "listening_port": data['listening_port'],
            "target_host": data['target_host'],
            "target_port": data['target_port'],
            "status": "running"
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/proxy', methods=['GET'])
def list_proxies():
    """Get status of all proxies."""
    proxies = get_all_proxies_from_db()
    
    result = []
    for proxy in proxies:
        # Check actual process status, not the one stored in DB
        actual_status = check_process_status(proxy['process_id'])
        result.append({
            "id": proxy['id'],
            "listening_port": proxy['listening_port'],
            "target_host": proxy['target_host'],
            "target_port": proxy['target_port'],
            "process_id": proxy['process_id'],
            "start_time": proxy['start_time'],
            "stop_time": proxy['stop_time'],
            "status": actual_status
        })
    
    return jsonify(result)

@app.route('/proxy/<int:proxy_id>', methods=['GET'])
def get_proxy(proxy_id):
    """Get status of a specific proxy by ID."""
    proxy = get_proxy_from_db(proxy_id)
    
    if not proxy:
        return jsonify({"error": "Proxy not found"}), 404
        
    # Check actual process status, not the one stored in DB
    actual_status = check_process_status(proxy['process_id'])
    
    return jsonify({
        "id": proxy['id'],
        "listening_port": proxy['listening_port'],
        "target_host": proxy['target_host'],
        "target_port": proxy['target_port'],
        "process_id": proxy['process_id'],
        "start_time": proxy['start_time'],
        "stop_time": proxy['stop_time'],
        "status": actual_status
    })

@app.route('/proxy/<int:proxy_id>', methods=['DELETE'])
def delete_proxy(proxy_id):
    proxy = get_proxy_from_db(proxy_id)

    if not proxy:
        return jsonify({"error": "Proxy not found"}), 404

    # Stop the proxy process if it's running
    if proxy['process_id'] is not None:
        try:
            # Get the process object from memory
            process = active_processes.get(proxy_id)
            if process:
                return_code, stdout, stderr = stop_socat_proxy(process)

                # Clean up process from memory
                active_processes.pop(proxy_id, None)
            else:
                # Even if no process in memory, try to clean DB anyway
                print(f"Warning: Process {proxy_id} not found in active_processes")

        except Exception as e:
            return jsonify({"error": f"Failed to stop proxy: {e}"}), 500

    # Remove from database
    delete_proxy_from_db(proxy_id)

    return jsonify({"message": "Proxy deleted successfully"})

@app.route('/proxy/<int:proxy_id>', methods=['PUT'])
def stop_proxy(proxy_id):
    """Stop a running proxy."""
    proxy = get_proxy_from_db(proxy_id)
    
    if not proxy:
        return jsonify({"error": "Proxy not found"}), 404
    
    # Stop the proxy process if it's running
    if proxy['process_id'] is not None:
        try:
            # Get the process object from memory
            process = active_processes.get(proxy_id)
            if process:
                return_code, stdout, stderr = stop_socat_proxy(process)
                                    
            # Clean up process from memory
            active_processes.pop(proxy_id, None)
            
        except Exception as e:
            return jsonify({"error": f"Failed to stop proxy: {e}"}), 500

    # Update database with stopped status
    update_proxy_status_in_db(proxy_id, process_id=None, status='stopped', stop_time="CURRENT_TIMESTAMP")
    
    return jsonify({
        "id": proxy_id,
        "status": "stopped"
    })

@app.route('/proxy/<int:proxy_id>/start', methods=['POST'])
def start_proxy(proxy_id):
    """Start a stopped proxy."""
    proxy = get_proxy_from_db(proxy_id)
    
    if not proxy:
        return jsonify({"error": "Proxy not found"}), 404
    
    # Re-start the socat process with the same parameters
    try:
        process = start_socat_proxy(
            proxy['listening_port'],
            proxy['target_host'],
            proxy['target_port']
        )
        
        # Update database with new process ID and running status
        update_proxy_status_in_db(proxy_id, process.pid, 'running')
        
        # Store process in memory
        active_processes[proxy_id] = process
        
        return jsonify({
            "id": proxy_id,
            "process_id": process.pid,
            "status": "running"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Backup and restore functionality
@app.route('/backup', methods=['POST'])
def backup_proxies():
    """Create a backup of all proxies"""
    try:
        proxies = get_all_proxies_from_db()
        backup_data = []
        
        for proxy in proxies:
            backup_data.append({
                'id': proxy['id'],
                'listening_port': proxy['listening_port'],
                'target_host': proxy['target_host'],
                'target_port': proxy['target_port'],
                'status': proxy['status']
            })
        
        return jsonify(backup_data)
    except Exception as e:
        return jsonify({"error": f"Failed to create backup: {str(e)}"}), 500

@app.route('/restore', methods=['POST'])
def restore_proxies():
    """Restore proxies from JSON payload"""
    try:
        # Get JSON data from request
        backup_data = request.get_json()
        
        if not backup_data:
            return jsonify({"error": "No backup data provided"}), 400

        # Get the restore options
        mode = request.args.get('mode', 'append')  # Default to append
        
        restored_count = 0
        
        if mode == 'overwrite':
            # Clear existing proxies
            for proxy in get_all_proxies_from_db():
                delete_proxy_from_db(proxy['id'])
                
        # Add each proxy from backup
        for proxy_config in backup_data:

            if proxy_config_exists(proxy_config['listening_port'], proxy_config['target_host'], proxy_config['target_port']):
                return jsonify({"error": "A proxy with this configuration already exists"}), 400

            # Skip the ID when restoring (it will be auto-generated)
            proxy_config.pop('id', None)
            
            # Insert into database with new ID
            create_proxy_in_db(
                proxy_config['listening_port'],
                proxy_config['target_host'],
                proxy_config['target_port'],
                None
            )
            
            restored_count += 1
            
        return jsonify({
            "message": f"Successfully restored {restored_count} proxies in {mode} mode",
            "count": restored_count,
            "mode": mode
        })
    except Exception as e:
        return jsonify({"error": f"Failed to restore proxy: {str(e)}"}), 500

if __name__ == '__main__':
    # Check if socat is installed
    if not check_socat_installed():
        print("Error: socat is not installed or not in PATH")
        exit(1)
    
    app.run(debug=True, host='0.0.0.0', port=5000)