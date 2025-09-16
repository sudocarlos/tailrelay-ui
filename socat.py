"""
A module to create and manage socat proxy processes.

This module provides functionality to start and stop socat proxy
processes that forward traffic between a local port and a target host.
"""

import subprocess
import logging
import os
import signal
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

def start_socat_proxy(
    listening_port: int,
    target_host: str,
    target_port: int,
    timeout: Optional[int] = None
) -> subprocess.Popen:
    """
    Start a socat proxy process that forwards traffic between
    a local port and a target host.
    
    Args:
        listening_port: The local port to listen on
        target_host: The target host to forward to
        target_port: The target port to forward to
        timeout: Optional timeout in seconds for the process
        
    Returns:
        A subprocess.Popen object representing the running socat process
        
    Raises:
        subprocess.SubprocessError: If socat is not installed or cannot be started
    """
    # Build the socat command
    cmd = [
        'socat',
        f'tcp-listen:{listening_port},fork,reuseaddr',
        f'tcp:{target_host}:{target_port}'
    ]
    
    # Add timeout if specified
    if timeout:
        cmd.extend(['timeout', str(timeout)])
    
    try:
        # Start the socat process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid  # Create new process group
        )
        
        logger.info(f"Started socat proxy on port {listening_port} "
                   f"forwarding to {target_host}:{target_port}")
        
        return process
        
    except FileNotFoundError:
        raise subprocess.SubprocessError("socat is not installed or not in PATH")
    except Exception as e:
        raise subprocess.SubprocessError(f"Failed to start socat: {str(e)}")


def stop_socat_proxy(process: subprocess.Popen) -> Tuple[int, str, str]:
    """
    Stop a running socat proxy process.
    
    Args:
        process: The subprocess.Popen object representing the socat process
        
    Returns:
        A tuple of (return_code, stdout, stderr)
    """
    if not process:
        return 0, "", ""

    try:
        # Get the process group ID
        pgid = os.getpgid(process.pid)
        
        # Terminate the process group
        os.killpg(pgid, signal.SIGTERM)
        
        # Wait for process to finish with timeout
        stdout, stderr = process.communicate(timeout=5)
        
        logger.info("Stopped socat proxy")
        
        return process.returncode, stdout, stderr
        
    except subprocess.TimeoutExpired:
        # Force kill if it doesn't terminate gracefully
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # Process already terminated
        
        stdout, stderr = process.communicate()
        
        logger.warning("socat proxy terminated with force kill")
        
        return process.returncode, stdout, stderr
    except ProcessLookupError:
        # Process already terminated
        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr


def check_socat_installed() -> bool:
    """
    Check if socat is installed and available in PATH.
    
    Returns:
        True if socat is installed, False otherwise
    """
    try:
        subprocess.run(
            ['socat', '-V'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False