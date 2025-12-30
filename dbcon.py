# database_processor.py
import mysql.connector
from typing import Optional, List, Tuple, Dict, Any
import logging
from dataclasses import dataclass
import contextlib

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('html_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Database configuration dataclass"""
    host: str
    user: str
    password: str
    database: str
    port: int = 3306
    charset: str = 'utf8mb4'
    use_ssl: bool = False
    ssl_ca: Optional[str] = None
    ssl_cert: Optional[str] = None
    ssl_key: Optional[str] = None


class DatabaseConnection:
    """Handles database connection and disconnection"""
    
    def __init__(self, config: DatabaseConfig):
        """
        Initialize database connection configuration
        
        Args:
            config: DatabaseConfig object with connection details
        """
        self.config = config
        self.connection = None
        self.cursor = None
        
    def connect(self) -> bool:
        """
        Establish database connection
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Prepare connection parameters
            connection_params = {
                'host': self.config.host,
                'user': self.config.user,
                'password': self.config.password,
                'database': self.config.database,
                'port': self.config.port,
                'charset': self.config.charset,
                'use_unicode': True,
                'autocommit': False  # We'll handle commits manually
            }
            
            # Add SSL if configured
            if self.config.use_ssl:
                ssl_config = {}
                if self.config.ssl_ca:
                    ssl_config['ca'] = self.config.ssl_ca
                if self.config.ssl_cert:
                    ssl_config['cert'] = self.config.ssl_cert
                if self.config.ssl_key:
                    ssl_config['key'] = self.config.ssl_key
                if ssl_config:
                    connection_params['ssl_ca'] = ssl_config.get('ca')
                    connection_params['ssl_cert'] = ssl_config.get('cert')
                    connection_params['ssl_key'] = ssl_config.get('key')
            
            # Establish connection
            self.connection = mysql.connector.connect(**connection_params)
            self.cursor = self.connection.cursor(dictionary=True)  # Return results as dictionaries
            
            # Test connection
            self.cursor.execute("SELECT 1")
            self.cursor.fetchone()
            
            logger.info(f"Connected to database '{self.config.database}' on {self.config.host}:{self.config.port}")
            return True
            
        except mysql.connector.Error as err:
            logger.error(f"Database connection error: {err}")
            return False
        except Exception as e:
            logger.error(f"Unexpected connection error: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                if self.connection.is_connected():
                    self.connection.close()
                    logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
    
    def is_connected(self) -> bool:
        """Check if database connection is active"""
        try:
            if self.connection and self.connection.is_connected():
                # Execute a simple query to verify connection
                self.cursor.execute("SELECT 1")
                return True
            return False
        except:
            return False
    
    @contextlib.contextmanager
    def get_connection(self):
        """Context manager for database connection"""
        try:
            if not self.is_connected():
                self.connect()
            yield self
        finally:
            pass  # Don't disconnect here - let the main class handle it
    
    def commit(self) -> None:
        """Commit the current transaction to the database"""
        try:
            if self.connection:
                self.connection.commit()
                logger.info("Transaction committed successfully")
            else:
                logger.warning("No active database connection to commit")
        except mysql.connector.Error as err:
            logger.error(f"Error committing transaction: {err}")
        except Exception as e:
            logger.error(f"Unexpected error during commit: {e}")


class DatabaseReader(DatabaseConnection):
    """Handles reading operations from the database"""
    
    def fetch_single_entry(self, table: str, id_column: str, id_value: Any, 
                          content_column: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single entry from the database
        
        Args:
            table: Name of the table
            id_column: Name of the ID column
            id_value: Value to search for in the ID column
            content_column: Name of the column containing base64 HTML
            
        Returns:
            Dictionary with column names as keys, or None if not found
            
        Example:
            result = reader.fetch_single_entry(
                table='articles',
                id_column='article_id',
                id_value=123,
                content_column='html_content'
            )
            # Returns: {'article_id': 123, 'html_content': 'SGVsbG8gV29ybGQ='}
        """
        try:
            # Validate inputs
            if not all([table, id_column, content_column]):
                logger.error("Missing required parameters")
                return None
            
            # Create parameterized query to prevent SQL injection
            query = f"""
                SELECT {id_column}, {content_column}
                FROM {table}
                WHERE {id_column} = %s
                LIMIT 1
            """
            
            # Execute query
            self.cursor.execute(query, (id_value,))
            result = self.cursor.fetchone()
            
            if result:
                logger.info(f"Fetched entry: {id_column}={id_value} from {table}")
                return result
            else:
                logger.warning(f"No entry found with {id_column}={id_value} in {table}")
                return None
                
        except mysql.connector.Error as err:
            logger.error(f"MySQL error fetching entry: {err}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching entry: {e}")
            return None
    
    def fetch_multiple_entries(self, table: str, id_column: str, id_values: List[Any], 
                              content_column: str) -> List[Dict[str, Any]]:
        """
        Fetch multiple entries by their IDs
        
        Args:
            table: Name of the table
            id_column: Name of the ID column
            id_values: List of ID values to fetch
            content_column: Name of the column containing base64 HTML
            
        Returns:
            List of dictionaries for each row found
        """
        try:
            if not id_values:
                logger.warning("No ID values provided")
                return []
            
            # Create placeholders for IN clause
            placeholders = ', '.join(['%s'] * len(id_values))
            query = f"""
                SELECT {id_column}, {content_column}
                FROM {table}
                WHERE {id_column} IN ({placeholders})
                ORDER BY {id_column}
            """
            
            self.cursor.execute(query, tuple(id_values))
            results = self.cursor.fetchall()
            
            logger.info(f"Fetched {len(results)} entries from {table}")
            return results
            
        except Exception as e:
            logger.error(f"Error fetching multiple entries: {e}")
            return []
    
    def fetch_all_entries(self, table: str, content_column: str, 
                         id_column: str = 'id', 
                         limit: Optional[int] = None,
                         offset: int = 0) -> List[Dict[str, Any]]:
        """
        Fetch all entries from a table (use with caution for large tables)
        
        Args:
            table: Name of the table
            content_column: Name of the column containing base64 HTML
            id_column: Name of the ID column (for ordering)
            limit: Maximum number of rows to fetch (None for all)
            offset: Number of rows to skip
            
        Returns:
            List of dictionaries for each row
        """
        try:
            query = f"""
                SELECT {id_column}, {content_column}
                FROM {table}
                ORDER BY {id_column}
            """
            
            # Add LIMIT and OFFSET if specified
            if limit is not None:
                query += f" LIMIT {limit} OFFSET {offset}"
            
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            logger.info(f"Fetched {len(results)} entries from {table}")
            return results
            
        except Exception as e:
            logger.error(f"Error fetching all entries: {e}")
            return []
    
    def fetch_entries_batch(self, table: str, content_column: str, 
                           id_column: str = 'id',
                           batch_size: int = 100,
                           last_id: Optional[Any] = None) -> Tuple[List[Dict[str, Any]], Any]:
        """
        Fetch entries in batches for large tables using cursor-based pagination
        
        Args:
            table: Name of the table
            content_column: Name of the column containing base64 HTML
            id_column: Name of the ID column
            batch_size: Number of rows per batch
            last_id: Last ID from previous batch (None for first batch)
            
        Returns:
            Tuple of (list of rows, last_id from this batch)
        """
        try:
            if last_id is not None:
                query = f"""
                    SELECT {id_column}, {content_column}
                    FROM {table}
                    WHERE {id_column} > %s
                    ORDER BY {id_column}
                    LIMIT %s
                """
                params = (last_id, batch_size)
            else:
                query = f"""
                    SELECT {id_column}, {content_column}
                    FROM {table}
                    ORDER BY {id_column}
                    LIMIT %s
                """
                params = (batch_size,)
            
            self.cursor.execute(query, params)
            results = self.cursor.fetchall()
            
            # Get the last ID for next batch
            next_last_id = results[-1][id_column] if results else None
            
            logger.debug(f"Fetched batch of {len(results)} entries, last_id={next_last_id}")
            return results, next_last_id
            
        except Exception as e:
            logger.error(f"Error fetching batch: {e}")
            return [], None
    
    def count_entries(self, table: str, condition: Optional[str] = None) -> int:
        """
        Count total entries in a table
        
        Args:
            table: Name of the table
            condition: Optional WHERE condition
            
        Returns:
            Total count of entries
        """
        try:
            query = f"SELECT COUNT(*) as count FROM {table}"
            if condition:
                query += f" WHERE {condition}"
            
            self.cursor.execute(query)
            result = self.cursor.fetchone()
            return result['count'] if result else 0
            
        except Exception as e:
            logger.error(f"Error counting entries: {e}")
            return 0
    
    def get_table_info(self, table: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a table structure
        
        Args:
            table: Name of the table
            
        Returns:
            Dictionary with table information
        """
        try:
            # Get column information
            self.cursor.execute(f"DESCRIBE {table}")
            columns = self.cursor.fetchall()
            
            # Get row count
            count = self.count_entries(table)
            
            return {
                'table_name': table,
                'row_count': count,
                'columns': columns
            }
            
        except Exception as e:
            logger.error(f"Error getting table info: {e}")
            return None


def create_database_reader(config: DatabaseConfig) -> Optional[DatabaseReader]:
    """
    Factory function to create and connect a DatabaseReader instance
    
    Args:
        config: Database configuration
        
    Returns:
        Connected DatabaseReader instance or None if connection fails
    """
    try:
        reader = DatabaseReader(config)
        if reader.connect():
            return reader
        else:
            logger.error("Failed to connect to database")
            return None
    except Exception as e:
        logger.error(f"Error creating database reader: {e}")
        return None


# Example usage
if __name__ == "__main__":
    # Example configuration
    config = DatabaseConfig(
        host='localhost',
        user='your_username',
        password='your_password',
        database='your_database',
        port=3306
    )
    
    # Create and use database reader
    reader = create_database_reader(config)
    
    if reader:
        try:
            # Example 1: Fetch single entry
            entry = reader.fetch_single_entry(
                table='articles',
                id_column='article_id',
                id_value=123,
                content_column='html_content'
            )
            
            if entry:
                print(f"Found entry: ID={entry['article_id']}")
            
            # Example 2: Fetch all entries (first 100)
            all_entries = reader.fetch_all_entries(
                table='articles',
                content_column='html_content',
                id_column='article_id',
                limit=100
            )
            print(f"Total entries fetched: {len(all_entries)}")
            
            # Example 3: Fetch in batches
            batch, last_id = reader.fetch_entries_batch(
                table='articles',
                content_column='html_content',
                id_column='article_id',
                batch_size=50
            )
            print(f"First batch: {len(batch)} entries")
            
        finally:
            # Always disconnect when done
            reader.disconnect()