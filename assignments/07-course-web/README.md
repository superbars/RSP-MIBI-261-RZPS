# Задание 7 Веб-приложение учебных курсов

## Запуск

```bash
./run.sh
```

Web:

```text
http://localhost:8080
```

Default credentials

```text
course_user : course-demo-password
```

## Структура

- `app/app.py` — маршруты, сессии и безопасные SQL-запросы;
- `app/templates/` — HTML-страницы;
- `app/static/style.css` — стили интерфейса;
- `app/config.toml` — несекретные параметры PostgreSQL;
- `app/Dockerfile` — образ `rsp-courses-web:1.0.0` и автозапуск;
- `db/01-schema.sql` — четыре связанные таблицы;
- `db/02-demo-data.sql` — демонстрационные данные;
- `db/03-create-app-user.sh` — роль с минимальными правами;
- `compose.yaml` — PostgreSQL и веб-приложение;
- `.env.example` — рабочие демонстрационные переменные;

## Commands for app

Logs:

```bash
docker compose logs --follow web
```

Recreate:

```bash
docker compose build --no-cache web
docker compose up --detach --force-recreate web
```

Stop:

```bash
docker compose down
```

Remove with psql volume

```bash
docker compose down --volumes
```

## Test requests

Add
table: teachers
name: Demo Teacher
email: demo.teacher@example.com

update
table: teachers
ID: ID из предыдущей вставки
column: name
new value: Updated Teacher

update-many
table: enrollments
target column: grade
new value: 10
filter column: student_id
filter values: 1, 2
