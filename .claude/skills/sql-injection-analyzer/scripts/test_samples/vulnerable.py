import sqlite3
import mysql.connector
from sqlalchemy import text, create_engine
from django.db import connection

# Test 1: SQLite cursor.execute
db = sqlite3.connect(':memory:')
cursor = db.cursor()
user_input = input("Enter ID: ")
query = f"SELECT * FROM users WHERE id = {user_input}"
cursor.execute(query)

# Test 2: SQLite executescript
sql_script = f"CREATE TABLE temp AS SELECT * FROM users WHERE name = '{user_input}'"
cursor.executescript(sql_script)

# Test 3: SQLAlchemy raw SQL
engine = create_engine('mysql://user:pass@localhost/db')
with engine.connect() as conn:
    user_id = request.args.get('id')
    result = conn.execute(text(f"SELECT * FROM users WHERE id = {user_id}"))

# Test 4: Django ORM raw
from django.contrib.auth.models import User
name = request.GET.get('name')
users = User.objects.raw(f"SELECT * FROM auth_user WHERE username = '{name}'")

# Test 5: Django extra
filter_col = request.GET.get('filter')
users = User.objects.extra(select={f'{filter_col}': f"CASE WHEN {filter_col} = '1' THEN 1 END"})
