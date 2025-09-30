#!/usr/bin/env python3
"""
caddy.py
A tiny interactive tool to create Caddy reverse‑proxy
configurations via the Caddy admin API.
"""
import json
import logging
import os
import requests
import sqlite3
import sys
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default Caddy admin API URL
ADMIN_URL = os.getenv("CADDY_ADMIN_URL", "http://localhost:2019")

# Database file path
default_db_path = Path.home() / ".tailrelay.db"
DB_PATH = os.getenv("DB_PATH", default_db_path)

@dataclass
class CaddyServer:
    """Represents a single Caddy reverse‑proxy server."""

    hostname: str
    port: int
    upstream_url: str
    tls_trust_pool: Optional[str] = None
    trusted_proxies: Optional[List[str]] = None
    server_config: Dict[str, Dict] = field(init=False)

    # Flag to prevent rebuild during initialization
    _initialized: bool = field(default=False, init=False, repr=False)
    
    def __post_init__(self) -> None:
        if not self._initialized:
            server_hash = str(abs(hash((self.hostname, self.port))))[:8]
            self.name = f'srv{server_hash}'
        self.server_config = self._build_config()
        self._initialized = True

    def _build_config(self) -> Dict[str, Dict]:
        """Return a dictionary mapping a unique server name to its block."""
        reverse_proxy = {
            "handler": "reverse_proxy",
            "headers": {
                "request": {
                    "set": {
                        "Host": [
                            "{http.reverse_proxy.upstream.hostport}"
                        ],
                    },
                },
            },
            "upstreams": [{"dial": self.upstream_url}],
        }
        
        if self.tls_trust_pool:
            reverse_proxy["transport"] = {
                "protocol": "http",
                "tls": {
                    "ca": {
                        "pem_files": [self.tls_trust_pool],
                        "provider": "file",
                    },
                },
            }

        if self.trusted_proxies:
            reverse_proxy["trusted_proxies"] = self.trusted_proxies

        subroute = {
            "handler": "subroute",
            "routes": [{"handle": [reverse_proxy]}],
        }

        route = {
            "match": [{"host": [self.hostname]}],
            "handle": [subroute],
            "terminal": True,
        }

        server = {
            "listen": [f":{self.port}"],
            "routes": [route],
        }

        return {self.name: server}

    @property
    def status(self):
        return 'running' if get_caddy_server(self.name) else 'stopped'

    @status.setter
    def status(self, value):
        """Setter for attribute with validation."""
        # Perform validation or transformation here
        if value not in ['stopped', 'running']:
            raise ValueError("Status can only be set to 'stopped' or 'running'")
        self._attribute = value

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        if not getattr(self, "_initialized", False):
            return
        if name in {"name", "hostname", "port", "upstream_url", "tls_trust_pool", "trusted_proxies"}:
            self.server_config = self._build_config()

def get_caddy_config(caddy_admin_url:str = ADMIN_URL) -> bool:
    """
    Fetches the current configuration from Caddy's admin API.
    
    Args:
        server_name (str): the name of the sever in the Caddy config
        caddy_admin_url (str): The base URL of the Caddy admin API. Defaults to http://localhost:2019.
        
    Returns:
        dict: The current Caddy configuration as a Python dictionary.
        
    Raises:
        requests.exceptions.RequestException: If the HTTP request fails.
        json.JSONDecodeError: If the response is not valid JSON.
    """
    try:
        response = requests.get(f"{caddy_admin_url}/config")
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Caddy config: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        raise

def get_caddy_server(server_name:str, caddy_admin_url:str = ADMIN_URL) -> bool:
    """
    Fetches the current configuration from Caddy's admin API.
    
    Args:
        server_name (str): the name of the sever in the Caddy config
        caddy_admin_url (str): The base URL of the Caddy admin API. Defaults to http://localhost:2019.
        
    Returns:
        dict: The current Caddy configuration as a Python dictionary.
        
    Raises:
        requests.exceptions.RequestException: If the HTTP request fails.
        json.JSONDecodeError: If the response is not valid JSON.
    """
    try:
        if server_name == "ALL":
            url = f"{caddy_admin_url}/config/apps/http/servers/"
        else:
            url = f"{caddy_admin_url}/config/apps/http/servers/{server_name}"
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Caddy config: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        raise

def delete_caddy_server(server_name:str, stop_server:bool = False, caddy_admin_url:str = ADMIN_URL) -> bool:
    """
    Fetches the current configuration from Caddy's admin API.
    
    Args:
        server_name (str): the name of the sever in the Caddy config
        caddy_admin_url (str): The base URL of the Caddy admin API. Defaults to http://localhost:2019.
        
    Returns:
        dict: The current Caddy configuration as a Python dictionary.
        
    Raises:
        requests.exceptions.RequestException: If the HTTP request fails.
        json.JSONDecodeError: If the response is not valid JSON.
    """
    try:
        response = requests.delete(f"{caddy_admin_url}/config/apps/http/servers/{server_name}")
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Caddy config: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        raise

def create_caddy_server(caddy_server:CaddyServer, start_server:bool = False, caddy_admin_url:str = ADMIN_URL) -> bool:
    """
    Send the configuration to Caddy's admin API.
    """
    try:
        # Get current config to check if it's empty
        current_config = get_caddy_config()
        
        # If config is empty or None, push a blank initial config first
        if not current_config or not current_config.get("apps", {}).get("http", {}).get("servers"):
            current_config = {
                "apps": {
                    "http": {
                        "servers": {}
                    }
                }
            }
            
        # Push the new server to existing config using path traversal
        logger.info("Adding new server to existing configuration...")
        
        # Get the current full config
        full_config = current_config
        
        # Extract the server data from the config parameter
        for server_name, server_data in caddy_server.server_config.items():
            full_config["apps"]["http"]["servers"][server_name] = server_data
        
        # Push the updated config back to Caddy
        url = f"{caddy_admin_url}/load"
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(full_config))
        if response.status_code != 200:
            logger.error(f"Caddy returned {response.status_code}: {response.text}")
            return False
        logger.info("Configuration applied successfully!")

        if not start_server:
            db_insert_caddy_server(caddy_server)
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"Error pushing config: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in push_config: {e}")
        return False

def update_caddy_server(caddy_server:CaddyServer, caddy_admin_url:str = ADMIN_URL) -> bool:
    try:
        url = f"{caddy_admin_url}/config/apps/http/servers/{caddy_server.name}/"
        data = caddy_server.server_config[caddy_server.name]
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        
        db_update_caddy_server(caddy_server)
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Caddy config: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        raise

def start_caddy_server(server_name: str) -> None:
    """
    Start a Caddy server with the given name.
    
    Args:
        server_name (str): The name of the server to start
    """
    try:
        running_server = get_caddy_server(server_name)
        if running_server:
            db_running_server = db_build_caddy_server(server_name)
            db_running_server.status = 'running'
            db_update_caddy_server(db_running_server)
            logger.info(f"Server '{server_name}' is already running.")
            return json.dumps(db_running_server)
    except Exception as e:
        logger.error(f"Unable to retrieve running servers: {e}")

    try:
        server_to_start = db_build_caddy_server(server_name)
        response = create_caddy_server(server_to_start, start_server=True)
        response.raise_for_status()  # Raises an HTTPError for bad responses
    except sqlite3.DatabaseError as e:
        logger.error("Unable to build Caddy server from database.")
        raise
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Caddy config: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        raise
    
    if response.status_code == 200:
        server_to_start.status = 'running'
        db_update_caddy_server(server_to_start)
        logger.info(f"Server '{server_name}' loaded from DB into Caddy and started.")
    
    return response or None

def stop_caddy_server(server_name: str) -> None:
    """
    Stop a Caddy server with the given name.
    
    Args:
        server_name (str): The name of the server to stop
    """
    try:
        running_server = get_caddy_server(server_name)
        if not running_server:
            logger.info(f"Server '{server_name}' is already stopped.")
            return
    except Exception as e:
        logger.error(f"Unable to retrieve running servers: {e}")

    try:
        if not db_get_caddy_server(server_name):
            logger.info(f"""
                        Server '{server_name}' not found in database.
                        Loading CaddyServer object from running Caddy config.
                        """)
            server_to_stop = load_caddy_server_to_object(server_name)
            db_server_id = db_insert_caddy_server(server_to_stop)
        else:
            db_server_id = db_get_caddy_server(server_name).get('id')
            logger.info(f"Server '{server_name}' found in database. Attemping to stop it...")
        if db_server_id:
            response = delete_caddy_server(server_name, stop_server=True)
            response.raise_for_status()  # Raises an HTTPError for bad responses
    except sqlite3.DatabaseError as e:
        logger.error("Unable to insert Caddy server into database.")
        raise
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Caddy config: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        raise
    
    server_to_stop = db_build_caddy_server(server_name)
    server_to_stop.status = 'stopped'
    db_update_caddy_server(server_to_stop)

    logger.info(f"Server '{server_name}' stopped.")
    
    return True

def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    """
    Initializes the SQLite database and creates the caddy_servers table if it
    does not already exist.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS caddy_servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            hostname TEXT NOT NULL,
            port INTEGER NOT NULL,
            upstream_url TEXT NOT NULL,
            tls_trust_pool TEXT,
            trusted_proxies TEXT,      -- Stored as JSON string
            status TEXT DEFAULT stopped,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    return conn

def get_db_connection():
    """Create and return a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_insert_caddy_server(server: CaddyServer) -> int:
    """
    Inserts a new CaddyServer into the database.
    Returns the newly created row id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO caddy_servers
        (name, hostname, port, upstream_url, tls_trust_pool, trusted_proxies)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            server.name,
            server.hostname,
            server.port,
            server.upstream_url,
            server.tls_trust_pool,
            json.dumps(server.trusted_proxies) if server.trusted_proxies else None,
        ),
    )
    conn.commit()
    return cursor.lastrowid

def db_get_caddy_server(name: str) -> Optional[Dict]:
    """
    Retrieves a server configuration by name.
    Returns a dictionary of the row or None if not found.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM caddy_servers WHERE name = ?", (name,)
    )
    row = cursor.fetchone()
    print(row)
    if row:
        server = dict(row)
        server["trusted_proxies"] = json.loads(server["trusted_proxies"]) if server["trusted_proxies"] else None
        return server
    return None

def db_update_caddy_server(server: CaddyServer) -> None:
    """
    Updates an existing server record based on its name.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE caddy_servers
        SET hostname = ?, port = ?, upstream_url = ?, tls_trust_pool = ?, trusted_proxies = ?, status = ?
        WHERE name = ?
        """,
        (
            server.hostname,
            server.port,
            server.upstream_url,
            server.tls_trust_pool,
            json.dumps(server.trusted_proxies) if server.trusted_proxies else None,
            server.status,
            server.name,
        ),
    )
    conn.commit()

def db_delete_caddy_server(name: str) -> None:
    """
    Deletes a server configuration by name.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM caddy_servers WHERE name = ?", (name,))
    conn.commit()

def db_list_caddy_servers() -> List[Dict]:
    """
    Returns a list of all server configurations stored in the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM caddy_servers ORDER BY create_time DESC")
    rows = cursor.fetchall()
    servers = []
    for row in rows:
        server = dict(row)
        server["trusted_proxies"] = json.loads(server["trusted_proxies"]) if server["trusted_proxies"] else None
        servers.append(server)
    return servers

def db_build_caddy_server(name: str) -> Optional[CaddyServer]:
    """
    Construct a CaddyServer instance from a database entry.

    Args:
        name (str): The unique server name stored in the database.

    Returns:
        Optional[CaddyServer]: The constructed instance, or None if not found.
    """
    record = db_get_caddy_server(name)
    if not record:
        return None

    server = CaddyServer(
        hostname=record["hostname"],
        port=record["port"],
        upstream_url=record["upstream_url"],
        tls_trust_pool=record.get("tls_trust_pool"),
        trusted_proxies=record.get("trusted_proxies"),
    )
    # Preserve the original database name
    server.name = record["name"]
    return server

def load_caddy_server_to_object(server_name: str) -> int:
    """
    """
    # Retrieve the live server configuration from Caddy
    server_cfg = get_caddy_server(server_name)

    if not server_cfg:
        logger.error(f"No configuration found for server '{server_name}'.")
        raise ValueError(f"Server '{server_name}' not found in Caddy.")

    # --- Parse the Caddy API response into the fields needed for CaddyServer --------------
    # The server block structure returned by Caddy is something like:
    # {
    #   "listen": [":8080"],
    #   "routes": [
    #     {
    #       "match": [{"host": ["example.com"]}],
    #       "handle": [
    #         {"handler": "subroute", "routes": [{"handle": [reverse_proxy_obj]}]}
    #       ],
    #       "terminal": true
    #     }
    #   ]
    # }

    # Extract the listening port
    port: int | None = None
    if "listen" in server_cfg and server_cfg["listen"]:
        m = re.search(r":(\d+)", server_cfg["listen"][0])
        if m:
            port = int(m.group(1))

    # Extract the hostname and the reverse‑proxy settings
    hostname: str | None = None
    upstream_url: str | None = None
    tls_trust_pool: str | None = None
    trusted_proxies: List[str] | None = None

    routes = server_cfg.get("routes", [])
    for route in routes:
        # hostname
        if "match" in route and route["match"]:
            host_list = route["match"][0].get("host", [])
            if host_list:
                hostname = host_list[0]

        # reverse‑proxy sub‑route
        handle = route.get("handle", [])
        for h in handle:
            if h.get("handler") == "subroute":
                subroutes = h.get("routes", [])
                for subroute in subroutes:
                    for sh in subroute.get("handle", []):
                        if sh.get("handler") == "reverse_proxy":
                            # upstream dial address
                            upstreams = sh.get("upstreams", [])
                            if upstreams:
                                upstream_url = upstreams[0].get("dial")

                            # TLS configuration
                            tls = sh.get("tls")
                            if tls:
                                tls_trust_pool = tls.get("cert_file")

                            # Trusted proxies (if any)
                            trusted_proxies = sh.get("trusted_proxies")
                            if isinstance(trusted_proxies, list):
                                # The Caddy API returns proxies as a list of str
                                trusted_proxies = trusted_proxies

    # Validation – ensure we have the minimal required data
    if not all([hostname, port, upstream_url]):
        logger.error(
            f"Failed to parse required fields from Caddy server '{server_name}'."
        )
        raise ValueError(f"Incomplete data for server '{server_name}'.")

    # Construct a CaddyServer instance
    server_object = CaddyServer(
        hostname=hostname,
        port=port,
        upstream_url=upstream_url,
        tls_trust_pool=tls_trust_pool,
        trusted_proxies=trusted_proxies,
    )
    # Preserve the original name reported by Caddy
    server_object.name = server_name

    return server_object

init_db()