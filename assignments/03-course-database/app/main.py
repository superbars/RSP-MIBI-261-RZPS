from __future__ import annotations

import getpass
import os
import sys
import traceback
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg import sql


CONFIG_PATH = Path(__file__).with_name("config.toml")
LOG_FILE = os.environ.get("LOG_FILE", "")


TABLES = {

# editable == update || insertable == insert 

    "teachers": {
        "columns": {"id": int, "name": str, "email": str},
        "editable": ["name", "email"],
        "insertable": ["name", "email"],
    },
    "courses": {
        "columns": {"id": int, "title": str, "teacher_id": int},
        "editable": ["title", "teacher_id"],
        "insertable": ["title", "teacher_id"],
    },
    "students": {
        "columns": {"id": int, "name": str, "email": str},
        "editable": ["name", "email"],
        "insertable": ["name", "email"],
    },
    "enrollments": {
        "columns": {"id": int, "student_id": int, "course_id": int, "grade": int},
        "editable": ["student_id", "course_id", "grade"],
        "insertable": ["student_id", "course_id", "grade"],
    },
}


######### logging, stdout, stderror
def raw_log(message: str) -> None:
    if not LOG_FILE:
        return
    path = Path(LOG_FILE)
    # parents true we can create few dirs, exist_ok == okay not an error
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as log:
        log.write(f"{timestamp} {message}\n")


def report_success(message: str) -> None:
    print(f"Success: {message}")
    raw_log(f"SUCCESS {message}")


def report_error(error: Exception) -> None:
    print("Error, try again", file=sys.stderr)
    raw_log("ERROR " + repr(error) + "\n" + traceback.format_exc())

#### read config.toml
def load_config() -> dict:
    with CONFIG_PATH.open("rb") as file:
        return tomllib.load(file)
########




def parse_value(table: str, column: str, text: str):
    #table_info = TABLES[table]
    #columns_info = table_info["columns"]
    #value_type = columns_info[column]
    value_type = TABLES[table]["columns"][column]
    try:
        if value_type is int:
            return int(text)
        return text
    except ValueError as error:
        raise ValueError(f"Incorrect input for column: {column}") from error


def choose_table() -> str:
    names = list(TABLES)
    for number, name in enumerate(names, start=1):
        print(f"{number}. {name}")
    number = int(input("Num of table: "))
    if not 1 <= number <= len(names):
        raise ValueError("Could not find the table :(")
    # -1 because of list in python
    return names[number - 1]


# allowed is a column which is approved to edit (update/editable)
def choose_column(table: str, allowed: list[str] | None = None) -> str:
    columns = allowed or list(TABLES[table]["columns"])
    print("All columns:", ", ".join(columns))
    column = input("Type column name: ").strip()
    if column not in columns:
        raise ValueError("Not available column")
    return column


def print_rows(cursor: psycopg.Cursor) -> None:
    #rows = cursor.fetchone()
    rows = cursor.fetchall()
    columns = [item.name for item in cursor.description or []] # must return smt like ["id", "name", "email"]
    if not rows:
        print("Unsuccessful fetch")
        return
    print(" | ".join(columns))
    for row in rows:
        print(" | ".join(str(value) for value in row))


##############################


# 6.1.1
def view_all(cursor: psycopg.Cursor) -> None:
    table = choose_table()
    # SELECT * FROM "courses" ORDER BY id
    query = sql.SQL("SELECT * FROM {} ORDER BY id").format(sql.Identifier(table))
    cursor.execute(query)
    print_rows(cursor)
    report_success("The table was read")

# 6.1.2 and 6.1.3
# SELECT * FROM students WHERE name = 'Tteeest' || SELECT * FROM enrollments WHERE course_id = 1 AND grade = 8;
def view_with_filters(cursor: psycopg.Cursor, filter_count: int) -> None:
    table = choose_table()
    conditions = []
    values = []
    for _ in range(filter_count):
        column = choose_column(table)
        value = parse_value(table, column, input(f"Value: {column}: "))
        conditions.append(
            sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
        )
        values.append(value)

    query = sql.SQL("SELECT * FROM {} WHERE {} ORDER BY id").format(
        sql.Identifier(table),
        # it will append AND only if we have >1 conditions
        sql.SQL(" AND ").join(conditions),
    )
    cursor.execute(query, values)
    print_rows(cursor)
    report_success("Success query with filter")

# 6.2.1
def update_one(cursor: psycopg.Cursor) -> None:
    table = choose_table()
    # WHERE id = 2
    row_id = int(input("ID of value: "))
    # columns_text = "name, email"
    columns_text = input("Change values via column using ',': ")
    columns = [item.strip() for item in columns_text.split(",") if item.strip()]
    # TABLES["students"]["editable"] = ["name", "email"]
    allowed = TABLES[table]["editable"]
    # is list empty?
    if not columns or len(columns) != len(set(columns)):
        raise ValueError("Check name of column")
    # can we change columns?
    if any(column not in allowed for column in columns):
        raise ValueError("I can't change value of that column")

    # New values
    values = [parse_value(table, column, input(f"Put new values {column}: ")) for column in columns]
    assignments = [
        sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
        for column in columns
    ]
    query = sql.SQL("UPDATE {} SET {} WHERE id = {}").format(
        sql.Identifier(table),
        sql.SQL(", ").join(assignments),
        sql.Placeholder(),
    )
    cursor.execute(query, [*values, row_id])
    report_success(f"Changed rows: {cursor.rowcount}")

# 6.2.2 
# Ask
#UPDATE enrollments SET grade = 10 WHERE student_id IN (1, 2, 3);
def update_many(cursor: psycopg.Cursor) -> None:
    table = choose_table()
    target_column = choose_column(table, TABLES[table]["editable"])
    new_value = parse_value(table, target_column, input("New common value: "))
    filter_column = choose_column(table)
    texts = [item.strip() for item in input("Value of filter via ',': ").split(",")]
    values = [parse_value(table, filter_column, item) for item in texts if item]
    if not values:
        raise ValueError("List is empty")

    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in values)
    query = sql.SQL("UPDATE {} SET {} = {} WHERE {} IN ({})").format(
        sql.Identifier(table),
        sql.Identifier(target_column),
        sql.Placeholder(),
        sql.Identifier(filter_column),
        placeholders,
    )
    cursor.execute(query, [new_value, *values])
    report_success(f"Changed rows: {cursor.rowcount}")



#6.3.1
#######
def ask_insert_values(table: str) -> tuple[list[str], list]:
    # TABLES["teachers"]["insertable"] = [name, email]
    columns = TABLES[table]["insertable"]
    print("Columns for insert:", ", ".join(columns))
    values = [parse_value(table, column, input(f"{column}: ")) for column in columns]
    return columns, values


# INSERT INTO "teachers" ("name", "email") VALUES (%s, %s) RETURNING id
def insert_one(cursor: psycopg.Cursor) -> None:
    table = choose_table()
    columns, values = ask_insert_values(table)
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in values),
    )
    cursor.execute(query, values)
    new_id = cursor.fetchone()[0]
    report_success(f"Create row with ID: {new_id}")
########


#6.4.1
# INSERT INTO students (name, email) VALUES ('Test', 'test@mail.com') AND INSERT INTO students (name, email) VALUES ('Test2', 'test2@mail.com')
def insert_many(cursor: psycopg.Cursor) -> None:
    table = choose_table()
    columns = TABLES[table]["insertable"]
    count = int(input("Count of rows: "))
    
    ############
    if count < 1:
        raise ValueError("Count not < 1")

    # we add new data of each student
    rows = []
    # range(1, 3) => 1, 2
    for number in range(1, count + 1):
        print(f"Roww {number}")
        rows.append(
            [parse_value(table, column, input(f"{column}: ")) for column in columns]
        )

    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    #cursor.execute(query, values) 
    cursor.executemany(query, rows)
    report_success(f"Inserted new rows {count}")

# 6.3.2
def create_student_with_courses(cursor: psycopg.Cursor, multiple_courses: bool) -> None:
    name = input("Name: ").strip()
    email = input("Email: ").strip()
    cursor.execute(
        "INSERT INTO students (name, email) VALUES (%s, %s) RETURNING id",
        (name, email),
    )

    # get id of new student
    student_id = cursor.fetchone()[0]

    #if multiple_courses:
    #    course_count = int(input("count of courses"))
    #else:
    #    course_count = 1

    # gpt said it's better
    course_count = int(input("How many courses: ")) if multiple_courses else 1
    

    if course_count < 1:
        raise ValueError("I can't create 0 courses")

    for number in range(1, course_count + 1):
        print(f"Course {number}")
        course_id = int(input("ID of course: "))
        cursor.execute(
            "INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s)",
            (student_id, course_id),
        )

    report_success(f"The student with {student_id}, new courses: {course_count}")


def show_menu() -> None:
    print(
        """
1. Show tables
2. Filter by one value
3. Filter by few values
4. Update one row by id
5. Update few rows
6. Insert new row
7. Create one student and add to course
8. Add few rows in one table
9. Create one student and add to courses
0. Exit
"""
    )


def main() -> int:
    config = load_config()
    user = input("Login of PostgreSQL: ").strip()
    password = getpass.getpass("Password of PostgreSQL: ")

    try:
        connection = psycopg.connect(
            host=config["host"],
            port=config["port"],
            dbname=config["dbname"],
            user=user,
            password=password,
            connect_timeout=config["connect_timeout"],
            options=f"-c statement_timeout={config['statement_timeout_ms']}",
        )
    except psycopg.Error as error:
        print("CONNECTION ERROR. Check credentials please", file=sys.stderr)
        raw_log("CONNECTION ERROR " + repr(error) + "\n" + traceback.format_exc())
        return 1

    report_success("connected to DB")

    with connection:
        while True:
            show_menu()
            choice = input("Choose action: ").strip()
            if choice == "0":
                break

            try:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        if choice == "1":
                            view_all(cursor)
                        elif choice == "2":
                            view_with_filters(cursor, 1)
                        elif choice == "3":
                            view_with_filters(cursor, 2)
                        elif choice == "4":
                            update_one(cursor)
                        elif choice == "5":
                            update_many(cursor)
                        elif choice == "6":
                            insert_one(cursor)
                        elif choice == "7":
                            create_student_with_courses(cursor, False)
                        elif choice == "8":
                            insert_many(cursor)
                        elif choice == "9":
                            create_student_with_courses(cursor, True)
                        else:
                            print("Нет такого пункта", file=sys.stderr)
            except ValueError as error:
                print(f"INPUT ERROR: {error}", file=sys.stderr)
                raw_log("INPUT ERROR " + repr(error))
            except psycopg.Error as error:
                report_error(error)

    report_success("Bye, bye")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
