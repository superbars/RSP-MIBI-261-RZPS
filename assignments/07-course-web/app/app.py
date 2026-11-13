import logging
import os
import secrets
import sys
import tomllib
from functools import wraps
from pathlib import Path

import psycopg
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from psycopg import sql


CONFIG_PATH = Path(__file__).with_name("config.toml")
SESSION_COOKIE = "course_session"
# browser stores only session_id, login and password stay in app memory
SESSIONS = {}

# table structure and allowed names for SQL
# user cannot send any table or column name
TABLES = {
    "teachers": {
        "columns": {"id": int, "name": str, "email": str},
        "insertable": ["name", "email"],
        "editable": ["name", "email"],
    },
    "courses": {
        "columns": {"id": int, "title": str, "teacher_id": int},
        "insertable": ["title", "teacher_id"],
        "editable": ["title", "teacher_id"],
    },
    "students": {
        "columns": {"id": int, "name": str, "email": str},
        "insertable": ["name", "email"],
        "editable": ["name", "email"],
    },
    "enrollments": {
        "columns": {
            "id": int,
            "student_id": int,
            "course_id": int,
            "grade": int,
        },
        "insertable": ["student_id", "course_id", "grade"],
        "editable": ["student_id", "course_id", "grade"],
    },
}

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY is required")


def load_config():
    # read database address and timeouts from config.toml
    with CONFIG_PATH.open("rb") as config_file:
        raw = tomllib.load(config_file)
    return {
        "host": str(raw["host"]),
        "port": int(raw["port"]),
        "dbname": str(raw["dbname"]),
        "connect_timeout": int(raw["connect_timeout"]),
        "statement_timeout_ms": int(raw["statement_timeout_ms"]),
    }


DATABASE = load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    stream=sys.stdout,
)
LOGGER = logging.getLogger("course-web")


def connect_database(credentials):
    # open connection with login and password of current user
    # connect_timeout is for connection, statement_timeout is for SQL query
    return psycopg.connect(
        host=DATABASE["host"],
        port=DATABASE["port"],
        dbname=DATABASE["dbname"],
        user=credentials["username"],
        password=credentials["password"],
        connect_timeout=DATABASE["connect_timeout"],
        options=f"-c statement_timeout={DATABASE['statement_timeout_ms']}",
    )


def current_session():
    # get session_id from cookie and find user data in SESSIONS
    session_id = request.cookies.get(SESSION_COOKIE, "")
    if not session_id:
        return None
    return SESSIONS.get(session_id)


def login_required(view):
    # check login before opening protected page
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_session() is None:
            flash("I don't have credentials", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def choose_table(name):
    # table name cannot use %s, so check it in TABLES
    if name not in TABLES:
        abort(400, "Unknown table")
    return TABLES[name]


def choose_column(table, column, allowed=None):
    # allowed can contain only editable or insertable columns
    columns = allowed if allowed is not None else list(TABLES[table]["columns"])
    if column not in columns:
        raise ValueError("Недоступный столбец")
    return column


def parse_value(table, column, text):
    # HTML form sends strings, convert string to correct type
    value_type = TABLES[table]["columns"][column]
    if table == "enrollments" and column == "grade" and text.strip() == "":
        return None
    if value_type is int:
        try:
            return int(text)
        except ValueError as error:
            raise ValueError(f"Поле {column} должно быть целым числом") from error
    value = text.strip()
    if not value:
        raise ValueError(f"Поле {column} не должно быть пустым")
    return value


def rows_as_dicts(cursor):
    # cursor.description gives column names, fetchall gives row values
    # result example: {"id": 1, "name": "Test teacher", ...}
    columns = [item.name for item in cursor.description or []]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def get_table_rows(user_session, table):
    # get current rows for insert and update pages
    query = sql.SQL("SELECT * FROM {} ORDER BY id").format(sql.Identifier(table))
    try:
        with connect_database(user_session) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                return rows_as_dicts(cursor)
    except psycopg.Error:
        LOGGER.warning("Table read failed: table=%s", table)
        flash("Не удалось получить текущие записи", "error")
        return []


@app.route("/", methods=["GET", "POST"])
def login():
    # GET shows login page, POST gets login and password
    if request.method == "GET":
        if current_session() is not None:
            return redirect(url_for("home"))
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not username or not password:
        flash("Введите логин и пароль PostgreSQL", "error")
        return render_template("login.html"), 400

    try:
        # SELECT 1 only checks database connection
        with connect_database({"username": username, "password": password}) as connection:
            connection.execute("SELECT 1")
    except psycopg.Error:
        LOGGER.warning(
            "Failed login: username=%r remote_address=%r",
            username,
            request.remote_addr,
        )
        flash("Credentials error", "error")
        return render_template("login.html"), 401

    session_id = secrets.token_urlsafe(32)
    # save login and password in app memory, not in browser
    SESSIONS[session_id] = {
        "username": username,
        "password": password,
    }

    LOGGER.info("Successful login: username=%r", username)
    response = redirect(url_for("home"))
    # HttpOnly blocks JavaScript access, SameSite limits other websites
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        httponly=True,
        samesite="Lax",
        secure=False,
        max_age=30 * 60,
    )
    return response


@app.post("/logout")
@login_required
def logout():
    session_id = request.cookies.get(SESSION_COOKIE, "")
    # remove session from app memory and cookie from browser
    SESSIONS.pop(session_id, None)
    response = redirect(url_for("login"))
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/home")
@login_required
def home():
    user_session = current_session()
    return render_template("home.html", user_session=user_session)


@app.get("/tables")
@login_required
def tables():
    user_session = current_session()

    table = request.args.get("table", "teachers")
    table_info = choose_table(table)
    conditions = []
    values = []

    # read first and second optional filters
    for suffix in ("1", "2"):
        column = request.args.get(f"column{suffix}", "").strip()
        text = request.args.get(f"value{suffix}", "")
        if not column and not text:
            continue
        column = choose_column(table, column)
        conditions.append(
            # Identifier is column name, Placeholder is user value
            sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
        )
        values.append(parse_value(table, column, text))

    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))
    if conditions:
        # one filter has no AND, two filters have AND between them
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions)
    query += sql.SQL(" ORDER BY id")

    try:
        with connect_database(user_session) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, values)
                rows = rows_as_dicts(cursor)
    except (psycopg.Error, ValueError) as error:
        LOGGER.warning("Table read failed: %s", type(error).__name__)
        flash(str(error) if isinstance(error, ValueError) else "Ошибка чтения базы", "error")
        rows = []

    return render_template(
        "tables.html",
        selected_table=table,
        table_info=table_info,
        rows=rows,
    )


@app.route("/insert", methods=["GET", "POST"])
@login_required
def insert():
    user_session = current_session()
    table = request.values.get("table", "teachers")
    table_info = choose_table(table)

    if request.method == "POST":
        try:
            columns = table_info["insertable"]
            # get only insertable fields from 
            values = [parse_value(table, column, request.form.get(column, "")) for column in columns]
            query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
                # Identifier for names, Placeholder for user values
                sql.Identifier(table),
                sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            )
            with connect_database(user_session) as connection:
                # RETURNING id gives id of new row
                new_id = connection.execute(query, values).fetchone()[0]
            flash(f"Создана запись с ID {new_id}", "success")
            return redirect(url_for("insert", table=table))
        except ValueError as error:
            flash(str(error), "error")
        except psycopg.Error:
            LOGGER.warning("Insert failed: table=%s user=%r", table, user_session["username"])
            flash("Не удалось добавить запись. Проверьте значения и связи", "error")

    rows = get_table_rows(user_session, table)
    return render_template(
        "insert.html",
        selected_table=table,
        table_info=table_info,
        rows=rows,
    )


@app.route("/update", methods=["GET", "POST"])
@login_required
def update():
    user_session = current_session()
    table = request.values.get("table", "teachers")
    table_info = choose_table(table)

    if request.method == "POST":
        try:
            row_id = int(request.form.get("row_id", ""))
            # id is only for WHERE, user can change only editable columns
            column = choose_column(table, request.form.get("column", ""), table_info["editable"])
            value = parse_value(table, column, request.form.get("new_value", ""))
            query = sql.SQL("UPDATE {} SET {} = {} WHERE id = {}").format(
                sql.Identifier(table),
                sql.Identifier(column),
                sql.Placeholder(),
                sql.Placeholder(),
            )
            with connect_database(user_session) as connection:
                result = connection.execute(query, (value, row_id))
                # rowcount shows how many rows were updated
                changed = result.rowcount
            flash(f"Изменено строк: {changed}", "success")
            return redirect(url_for("update", table=table))
        except ValueError as error:
            flash(str(error), "error")
        except psycopg.Error:
            LOGGER.warning("Update failed: table=%s user=%r", table, user_session["username"])
            flash("Не удалось обновить запись. Проверьте значения и связи", "error")

    rows = get_table_rows(user_session, table)
    return render_template(
        "update.html",
        selected_table=table,
        table_info=table_info,
        rows=rows,
    )


@app.route("/update-many", methods=["GET", "POST"])
@login_required
def update_many():
    user_session = current_session()
    table = request.values.get("table", "enrollments")
    table_info = choose_table(table)

    if request.method == "POST":
        try:
            target_column = choose_column(
                table,
                request.form.get("target_column", ""),
                table_info["editable"],
            )
            filter_column = choose_column(table, request.form.get("filter_column", ""))
            new_value = parse_value(table, target_column, request.form.get("new_value", ""))
            texts = [item.strip() for item in request.form.get("filter_values", "").split(",")]
            # "1, 2, 3" becomes [1, 2, 3]
            filter_values = [
                parse_value(table, filter_column, item) for item in texts if item
            ]
            if not filter_values:
                raise ValueError("We need one more values of filter")

            placeholders = sql.SQL(", ").join(
                # create one %s for every value inside IN (...)
                sql.Placeholder() for _ in filter_values
            )
            query = sql.SQL("UPDATE {} SET {} = {} WHERE {} IN ({})").format(
                sql.Identifier(table),
                sql.Identifier(target_column),
                sql.Placeholder(),
                sql.Identifier(filter_column),
                placeholders,
            )
            with connect_database(user_session) as connection:
                # first value is new value, other values are for filter
                result = connection.execute(query, [new_value, *filter_values])
                changed = result.rowcount
            flash(f"Changed: {changed}", "success")
            return redirect(url_for("update_many", table=table))
        except ValueError as error:
            flash(str(error), "error")
        except psycopg.Error:
            LOGGER.warning("Bulk update failed: table=%s user=%r", table, user_session["username"])
            flash("Could not update", "error")

    return render_template(
        "update_many.html",
        selected_table=table,
        table_info=table_info,
        rows=get_table_rows(user_session, table),
    )


@app.context_processor
def common_template_data():
    # Flask sends this data to every HTML template
    return {
        "tables": TABLES,
        "current_user_session": current_session(),
    }


if __name__ == "__main__":
    # 0.0.0.0 makes server available outside container
    app.run(host="0.0.0.0", port=8080, debug=False)
