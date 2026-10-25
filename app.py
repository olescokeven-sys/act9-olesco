import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, render_template, request


app = Flask(__name__)
DATABASE_PATH = Path(__file__).resolve().with_name("students.db")


def get_db_connection():
	connection = sqlite3.connect(DATABASE_PATH)
	connection.row_factory = sqlite3.Row
	return connection


def initialize_database():
	connection = get_db_connection()
	try:
		connection.execute(
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
		columns = {
			row["name"]
			for row in connection.execute("PRAGMA table_info(students)").fetchall()
		}
		if "source" not in columns:
			connection.execute(
				"ALTER TABLE students ADD COLUMN source TEXT NOT NULL DEFAULT 'Local'"
			)
		connection.commit()
	finally:
		connection.close()


initialize_database()


def validate_student_data(data):
	fields = ("student_id", "name", "program", "year", "section")
	if not isinstance(data, dict) or any(field not in data for field in fields):
		return None, "Provide student_id, name, program, year, and section."
	if any(not isinstance(data[field], str) or not data[field].strip() for field in fields if field != "year"):
		return None, "Student text fields must be non-empty strings."
	try:
		year = int(data["year"])
	except (TypeError, ValueError):
		return None, "Year must be an integer."
	if year < 1:
		return None, "Year must be greater than zero."
	source = data.get("source", "External API")
	if not isinstance(source, str) or not source.strip():
		return None, "Source must be a non-empty string."
	return (
		data["student_id"].strip(),
		data["name"].strip(),
		data["program"].strip(),
		year,
		data["section"].strip(),
		source.strip(),
	), None


def validate_classmate_url(classmate_url):
	parsed_url = urlparse(classmate_url)
	hostname = parsed_url.hostname or ""
	return (
		parsed_url.scheme == "https"
		and hostname.endswith(".onrender.com")
		and parsed_url.path.rstrip("/") in ("/api/students", "/students")
		and not parsed_url.username
		and not parsed_url.password
		and not parsed_url.query
		and not parsed_url.fragment
	)


@app.route("/")
def home():
	return render_template("index.html")


@app.route("/student")
def get_student():
	return jsonify(
		{
			"student_id": "24-00236",
			"name": "Kheven Olesco",
			"program": "BSIT",
			"year": 3,
			"section": "b",
		}
	)


@app.route("/hello")
def say_hello():
	name = request.args.get("name", "Student")
	return jsonify({"message": f"Hello, {name}!"})


@app.route("/academic")
def get_academic_profile():
	return jsonify(
		{
			"student_id": "24-00236	",
			"program": "BSIT",
			"year": 3,
			"section": "b",
		}
	)


@app.route("/students")
def get_students():
	connection = get_db_connection()
	try:
		students = connection.execute("SELECT * FROM students ORDER BY id").fetchall()
	finally:
		connection.close()
	return jsonify([dict(student) for student in students])


@app.route("/api/students", methods=["GET", "POST"])
def api_students():
	if request.method == "GET":
		return get_students()

	student_data, error = validate_student_data(request.get_json(silent=True))
	if error:
		return jsonify({"error": error}), 400
	connection = get_db_connection()
	try:
		cursor = connection.execute(
			"""INSERT INTO students (student_id, name, program, year, section, source)
			VALUES (?, ?, ?, ?, ?, ?)""",
			student_data,
		)
		connection.commit()
		new_id = cursor.lastrowid
	finally:
		connection.close()
	return jsonify({"message": "Student added", "id": new_id}), 201


@app.route("/api/students/<int:student_id>", methods=["GET", "PUT", "DELETE"])
def api_student_detail(student_id):
	connection = get_db_connection()
	try:
		if request.method == "GET":
			student = connection.execute(
				"SELECT * FROM students WHERE id = ?", (student_id,)
			).fetchone()
			if student is None:
				return jsonify({"error": "Student not found"}), 404
			return jsonify(dict(student))

		if request.method == "PUT":
			student_data, error = validate_student_data(request.get_json(silent=True))
			if error:
				return jsonify({"error": error}), 400
			cursor = connection.execute(
				"""UPDATE students SET student_id=?, name=?, program=?, year=?, section=?
				WHERE id=?""",
				(*student_data[:5], student_id),
			)
			if cursor.rowcount == 0:
				return jsonify({"error": "Student not found"}), 404
			connection.commit()
			return jsonify({"message": "Student updated"})

		cursor = connection.execute("DELETE FROM students WHERE id = ?", (student_id,))
		if cursor.rowcount == 0:
			return jsonify({"error": "Student not found"}), 404
		connection.commit()
		return jsonify({"message": "Student deleted"})
	finally:
		connection.close()


@app.route("/import-student", methods=["POST"])
def import_student():
	student_data, error = validate_student_data(request.get_json(silent=True))
	if error:
		return jsonify({"error": error}), 400
	connection = get_db_connection()
	try:
		cursor = connection.execute(
			"""INSERT INTO students (student_id, name, program, year, section, source)
			VALUES (?, ?, ?, ?, ?, 'Classmate API')""",
			student_data[:5],
		)
		connection.commit()
		new_id = cursor.lastrowid
	finally:
		connection.close()
	return jsonify({"message": "Remote record saved", "id": new_id}), 201


@app.route("/api/classmate", methods=["GET"])
def get_classmate_students():
	classmate_url = request.args.get("url", "")
	if not validate_classmate_url(classmate_url):
		return jsonify({"error": "Use an HTTPS Render /api/students or /students URL."}), 400

	try:
		response = requests.get(classmate_url, timeout=15, allow_redirects=False)
		response.raise_for_status()
		students = response.json()
	except requests.RequestException:
		return jsonify({"error": "Unable to retrieve the classmate API."}), 502
	except ValueError:
		return jsonify({"error": "The classmate API did not return valid JSON."}), 502
	if not isinstance(students, list):
		return jsonify({"error": "The classmate API response must be a JSON list."}), 502
	return jsonify(students)


@app.route("/api/classmate/send", methods=["POST"])
def send_classmate_student():
	data = request.get_json(silent=True)
	if not isinstance(data, dict):
		return jsonify({"error": "Provide a partner_url and student record."}), 400
	classmate_url = data.get("partner_url", "")
	if (
		not isinstance(classmate_url, str)
		or not validate_classmate_url(classmate_url)
		or urlparse(classmate_url).path.rstrip("/") != "/api/students"
	):
		return jsonify({"error": "Use an HTTPS Render /api/students URL."}), 400
	student_data, error = validate_student_data(data.get("student"))
	if error:
		return jsonify({"error": error}), 400
	record = dict(
		zip(("student_id", "name", "program", "year", "section", "source"), student_data)
	)
	record["source"] = "Partner API"
	try:
		response = requests.post(
			classmate_url,
			json=record,
			timeout=15,
			allow_redirects=False,
		)
		response.raise_for_status()
		if not 200 <= response.status_code < 300:
			return jsonify({"error": "The partner API did not accept the record."}), 502
	except requests.RequestException:
		return jsonify({"error": "Unable to send the record to the classmate API."}), 502
	return jsonify({"message": "Practice record sent to the partner API."}), 200


@app.route("/students/<int:student_id>")
def get_student_by_id(student_id):
	connection = get_db_connection()
	try:
		student = connection.execute(
			"SELECT * FROM students WHERE id = ?", (student_id,)
		).fetchone()
	finally:
		connection.close()
	if student is None:
		return jsonify({"error": "Student not found"}), 404
	return jsonify(dict(student))


@app.route("/students/section/<section>")
def get_students_by_section(section):
	connection = get_db_connection()
	try:
		students = connection.execute(
			"SELECT * FROM students WHERE section = ? COLLATE NOCASE ORDER BY id",
			(section,),
		).fetchall()
	finally:
		connection.close()
	return jsonify([dict(student) for student in students])


if __name__ == "__main__":
	app.run(debug=True)