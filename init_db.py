import sqlite3
from pathlib import Path


database_path = Path(__file__).with_name("students.db")
connection = sqlite3.connect(database_path)
cursor = connection.cursor()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        name TEXT NOT NULL,
        program TEXT NOT NULL,
        year INTEGER NOT NULL,
        section TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'Local'
    )
    """
)
columns = {row[1] for row in cursor.execute("PRAGMA table_info(students)")}
if "source" not in columns:
    cursor.execute(
        "ALTER TABLE students ADD COLUMN source TEXT NOT NULL DEFAULT 'Local'"
    )

students = [
    ("SAMPLE-1001", "Alex Rivera", "BSIT", 1, "A", "Local"),
    ("SAMPLE-1002", "Jamie Santos", "BSIT", 1, "B", "Local"),
    ("SAMPLE-1003", "Morgan Lee", "BSCS", 2, "A", "Local"),
    ("SAMPLE-1004", "Casey Flores", "BSIT", 3, "C", "Local"),
    ("SAMPLE-1005", "Taylor Cruz", "BSCS", 4, "B", "Local"),
    ("123", "Raizel Castaneda", "BSIT", 2, "HESTIA", "Local"),
    ("2024-1005", "Rizza Anthea Malacad", "BSED-Filipino", 4, "B", "Classmate API"),
]
for student in students:
    if cursor.execute(
        "SELECT 1 FROM students WHERE student_id = ? LIMIT 1", (student[0],)
    ).fetchone() is None:
        cursor.execute(
            """
            INSERT INTO students (student_id, name, program, year, section, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            student,
        )
connection.commit()
connection.close()
print("Database created successfully.")