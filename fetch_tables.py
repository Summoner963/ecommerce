import sqlite3

def fetch_tables_and_columns(db_path):
    # Connect to the SQLite database
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    
    # Fetch all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    # Dictionary to store tables and their columns
    tables_and_columns = {}
    
    for table in tables:
        table_name = table[0]
        # Fetch column details for the table
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        # Extract column names
        column_names = [column[1] for column in columns]
        tables_and_columns[table_name] = column_names
    
    # Close the connection
    connection.close()
    
    return tables_and_columns

if __name__ == "__main__":
    db_path = "db.sqlite3"  # Replace with your Django SQLite database path
    tables_columns = fetch_tables_and_columns(db_path)

    # Print the results
    for table, columns in tables_columns.items():
        print(f"Table: {table}")
        print(f"Columns: {columns}")
        print()
