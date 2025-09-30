"""
A module to create and manage socat proxy processes.

This module provides functionality to start and stop socat proxy
processes that forward traffic between a local port and a target host.
"""

import subprocess
import logging
import os
import re
import signal
import sqlite3
import psutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database file path
default_db_path = Path.home() / ".tailrelay.db"
DB_PATH = os.getenv("DB_PATH", default_db_path)

def get_socat_processes():
    """
    Finds all running `socat` processes and returns a mapping
    from listening port to the lowest PID that owns it.

    Returns:
        dict[int, int]: {port: pid}
    """
    try:
        # Capture the output of `pgrep -a socat`
        raw = subprocess.check_output(
            ["pgrep", "-a", "socat"], text=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        # No socat processes found
        return {}

    port_to_pid = {}
    for line in raw.strip().splitlines():
        # Each line is: "<pid> <command>"
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        pid_str, cmd = parts
        pid = int(pid_str)

        # Find the listening port in the command (tcp-listen:<port>...)
        match = re.search(r"tcp-listen:(\d+)", cmd)
        if not match:
            continue
        port = int(match.group(1))

        # Keep the lowest PID for this port
        if port not in port_to_pid or pid < port_to_pid[port]:
            port_to_pid[port] = pid

    return port_to_pid

@dataclass
class SocatRelay:
    listening_port: int
    target_host: str
    target_port: int
    timeout: Optional[int] = None

    def start(self) -> subprocess.Popen:
        # Build the socat command
        cmd = [
            'socat',
            f'tcp-listen:{self.listening_port},fork,reuseaddr',
            f'tcp:{self.target_host}:{self.target_port}'
        ]
        
        # Add timeout if specified
        if self.timeout:
            cmd.extend(['timeout', str(self.timeout)])
        
        try:
            # Start the socat process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid  # Create new process group
            )
            
            logger.info(f"Started socat relay on port {self.listening_port} "
                    f"forwarding to {self.target_host}:{self.target_port}")
            
            return process
            
        except FileNotFoundError:
            raise subprocess.SubprocessError("socat is not installed or not in PATH")
        except Exception as e:
            raise subprocess.SubprocessError(f"Failed to start socat: {str(e)}")

    def stop(self) -> Tuple[int, str, str]:
        if self.pid:
            proc = psutil.Process(self.pid)

            # ? Query its status
            # print(proc.status())          # 'running', 'sleeping', 'zombie', …
            # print(proc.create_time())     # epoch timestamp
            # print(proc.cpu_times())       # user + system time

            # > Send a graceful SIGTERM
            os.killpg(os.getpgid(self.pid), signal.SIGTERM)

            # ~ Wait for it to exit
            proc.wait(timeout=10)         # raises psutil.TimeoutExpired if still running
            logger.info("Stopped socat relay")
        else:
            logger.info("socat relay is not running!")

    @property
    def pid(self) -> Optional[int]:
        """Return a mapping of listening ports to the lowest PID."""
        return get_socat_processes().get(self.listening_port)

    @property
    def status(self) -> str:
        """Return the status of the process"""
        return "running" if self.pid else "stopped"

    @status.setter
    def status(self, value):
        """Setter for attribute with validation."""
        # Perform validation or transformation here
        if value not in ['stopped', 'running']:
            raise ValueError("Status can only be set to 'stopped' or 'running'")
        self._attribute = value

def init_db():
    """Initialize the SQLite database for process tracking."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Create table for proxy processes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS socat_relays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listening_port INTEGER NOT NULL UNIQUE,
                    target_host TEXT NOT NULL,
                    target_port INTEGER NOT NULL,
                    status TEXT DEFAULT stopped,
                    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
    except sqlite3.Error as e:
        print(f"Database initialization failed: {e}")

def get_db_connection():
    """Create and return a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_insert_socat_relay(socat_relay:SocatRelay):
    """Insert a new socat relay into the database."""
    listening_port = socat_relay.listening_port
    target_host = socat_relay.target_host
    target_port = socat_relay.target_port

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO socat_relays 
        (listening_port, target_host, target_port)
        VALUES (?, ?, ?)
    ''', (
        listening_port,
        target_host,
        target_port
    ))
    
    id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return id

def db_get_socat_relay(id):
    """Retrieve socat relay db entry by id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    relay = cursor.execute(
        'SELECT * FROM socat_relays WHERE id = ?', 
        (id,)
    ).fetchone()
    conn.close()
    return dict(relay)

def db_list_socat_relays():
    """Retrieve all socat relays from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    relays = cursor.execute('SELECT * FROM socat_relays').fetchall()
    conn.close()
    
    return [dict(row) for row in relays]

def db_delete_socat_selay(id):
    """Delete a socat relay from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM socat_relays WHERE id = ?', (id,))
    conn.commit()
    conn.close()

def db_update_socat_relay(relay:SocatRelay, relay_id:int) -> None:
    """
    Updates an existing server record based on its name.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE socat_relays
        SET listening_port = ?, target_host = ?, target_port = ?, status = ?
        WHERE id = ?
        """,
        (
            relay.listening_port,
            relay.target_host,
            relay.target_port,
            relay.status,
            relay_id,
        ),
    )
    conn.commit()
    conn.close()

def socat_relay_from_db(relay_id: int) -> Optional[SocatRelay]:
    """
    Fetch a relay entry by its database id and return a populated
    SocatRelay object.
    """
    row = db_get_socat_relay(relay_id)
    if not row:
        return None

    return SocatRelay(
        listening_port=row["listening_port"],
        target_host=row["target_host"],
        target_port=row["target_port"],
        timeout=None  # you could store timeout in the DB as well
    )

init_db()