"""
Database proxy for Windows Docker networking issues.

This module provides a workaround for Windows Docker Desktop networking issues
where SQLAlchemy cannot connect to localhost PostgreSQL containers.

Usage:
    from databases.docker_proxy import get_database_connection
    db = get_database_connection()
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional
import platform

logger = logging.getLogger(__name__)

def is_windows_docker_mode() -> bool:
    """
    Detect if we should use Docker exec mode.
    
    Returns True if:
    - Running on Windows
    - DATABASE_URL points to localhost/127.0.0.1
    - Docker container 'NDC_rag' is running
    """
    if platform.system() != 'Windows':
        return False
    
    # Ensure .env is loaded
    from dotenv import load_dotenv
    load_dotenv()
    
    db_url = os.getenv('DATABASE_URL', '')
    if not db_url:
        logger.warning("DATABASE_URL not found in environment")
        return False
    
    if 'localhost' not in db_url and '127.0.0.1' not in db_url:
        return False
    
    # Check if Docker container is running
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=NDC_rag', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        is_running = 'NDC_rag' in result.stdout
        if is_running:
            logger.debug(f"Docker container NDC_rag is running, using Docker proxy mode")
        else:
            logger.warning(f"Docker container NDC_rag not found, falling back to direct connection")
        return is_running
    except Exception as e:
        logger.warning(f"Failed to check Docker status: {e}")
        return False


def execute_sql_via_docker(sql: str, container_name: str = 'NDC_rag') -> list:
    """
    Execute SQL query via docker exec.
    
    Args:
        sql: SQL query to execute
        container_name: Name of Docker container
        
    Returns:
        List of rows (each row is a tuple)
    """
    try:
        # Escape single quotes in SQL
        sql_escaped = sql.replace("'", "'\\''")
        
        cmd = [
            'docker', 'exec', '-i', container_name,
            'psql', '-U', 'climate', '-d', 'climate',
            '-t',  # Tuples only mode
            '-A',  # Unaligned output
            '-F', '\t',  # Tab separated
            '-c', sql
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30
        )
        
        if result.returncode != 0:
            raise Exception(f"Docker exec failed: {result.stderr}")
        
        # Parse output - handle PostgreSQL output format
        rows = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith(('(', '-', 'CREATE', 'INSERT', 'SELECT', 'UPDATE', 'DELETE')):
                # Split by tab and clean up values
                values = line.split('\t')
                # Convert empty strings to None for NULL values and handle None values
                cleaned_values = []
                for val in values:
                    if val is None or val.strip() == '':
                        cleaned_values.append(None)
                    else:
                        cleaned_values.append(val.strip())
                rows.append(tuple(cleaned_values))
        
        return rows
        
    except Exception as e:
        logger.error(f"Failed to execute SQL via Docker: {e}")
        raise


class DockerProxyResult:
    """Mimics SQLAlchemy result object."""
    
    def __init__(self, rows):
        self.rows = rows
        self._index = 0
    
    def fetchone(self):
        if self._index < len(self.rows):
            row = self.rows[self._index]
            self._index += 1
            return row
        return None
    
    def fetchall(self):
        return self.rows
    
    def __iter__(self):
        return iter(self.rows)


def get_database_connection():
    """
    Get appropriate database connection based on environment.
    
    Returns:
        PostgresConnection or DockerProxyConnection
    """
    if is_windows_docker_mode():
        logger.info("Using Docker proxy mode for database connection (Windows workaround)")
        return DockerProxyConnection()
    else:
        logger.info("Using direct PostgreSQL connection")
        from databases.auth import PostgresConnection
        return PostgresConnection()


class DockerProxyConnection:
    """
    Proxy connection that uses docker exec for queries.
    Mimics PostgresConnection interface.
    """
    
    def __init__(self, container_name: str = 'NDC_rag'):
        self.container_name = container_name
        logger.info(f"Initialized Docker proxy connection to container: {container_name}")
    
    def Session(self):
        """Return a mock session that uses docker exec."""
        return DockerProxySession(self.container_name)
    
    def execute(self, sql: str):
        """Execute SQL via docker exec."""
        rows = execute_sql_via_docker(sql, self.container_name)
        return DockerProxyResult(rows)


class DockerProxySession:
    """Mock SQLAlchemy session that uses docker exec."""
    
    def __init__(self, container_name: str):
        self.container_name = container_name
        self._closed = False
    
    def __enter__(self):
        """Enter context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()
        return False  # Don't suppress exceptions
    
    def execute(self, sql, params=None):
        """Execute SQL query with optional parameters."""
        if hasattr(sql, 'text'):
            # SQLAlchemy text() object
            sql_str = str(sql)
        else:
            sql_str = str(sql)
        
        # If parameters are provided, substitute them
        if params:
            # Replace :param_name with actual values for PostgreSQL
            for key, value in params.items():
                placeholder = f":{key}"
                # Format value based on type
                if value is None:
                    formatted_value = "NULL"
                elif isinstance(value, str):
                    # Escape single quotes and wrap in quotes
                    escaped_value = value.replace("'", "''")
                    formatted_value = f"'{escaped_value}'"
                elif isinstance(value, (int, float)):
                    formatted_value = str(value)
                elif hasattr(value, 'isoformat'):  # datetime/date objects
                    formatted_value = f"'{value.isoformat()}'"
                else:
                    # Convert to string and quote
                    formatted_value = f"'{str(value)}'"
                
                sql_str = sql_str.replace(placeholder, formatted_value)
        
        rows = execute_sql_via_docker(sql_str, self.container_name)
        return DockerProxyResult(rows)
    
    def query(self, *args, **kwargs):
        """Mock query method - not fully implemented."""
        raise NotImplementedError(
            "DockerProxySession does not support ORM queries. "
            "Use raw SQL with session.execute(text('SELECT ...')) instead."
        )
    
    def commit(self):
        """No-op for compatibility."""
        pass
    
    def rollback(self):
        """No-op for compatibility."""
        pass
    
    def close(self):
        """Mark session as closed."""
        self._closed = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        self.close()

