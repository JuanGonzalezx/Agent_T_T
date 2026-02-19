"""Temporary script to inspect the current database state."""
import sqlite3

conn = sqlite3.connect('data/whatsapp_tracking.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('=== TABLES ===')
for t in tables:
    print(f'  {t[0]}')

# Show schema for each table
for t in tables:
    name = t[0]
    cursor.execute(f'PRAGMA table_info({name})')
    cols = cursor.fetchall()
    print(f'\n=== {name} columns ===')
    for c in cols:
        print(f'  {c["name"]} ({c["type"]}) | NOT NULL={c["notnull"]} | DEFAULT={c["dflt_value"]}')

# Show counts
print('\n=== ROW COUNTS ===')
for t in tables:
    name = t[0]
    cursor.execute(f'SELECT COUNT(*) FROM {name}')
    count = cursor.fetchone()[0]
    print(f'  {name}: {count} rows')

# Show sample data from estudiantes
cursor.execute('SELECT * FROM estudiantes LIMIT 3')
rows = cursor.fetchall()
if rows:
    print('\n=== Sample estudiantes ===')
    for row in rows:
        print(dict(row))

# Show sample data from bootcamps
cursor.execute('SELECT * FROM bootcamps LIMIT 3')
rows = cursor.fetchall()
if rows:
    print('\n=== Sample bootcamps ===')
    for row in rows:
        print(dict(row))

# Show sample data from campanas
try:
    cursor.execute('SELECT * FROM campanas LIMIT 3')
    rows = cursor.fetchall()
    if rows:
        print('\n=== Sample campanas ===')
        for row in rows:
            print(dict(row))
except:
    print('\n(campanas table does not exist)')

# Show sample data from campana_miembros
try:
    cursor.execute('SELECT * FROM campana_miembros LIMIT 3')
    rows = cursor.fetchall()
    if rows:
        print('\n=== Sample campana_miembros ===')
        for row in rows:
            print(dict(row))
except:
    print('\n(campana_miembros table does not exist)')

conn.close()
