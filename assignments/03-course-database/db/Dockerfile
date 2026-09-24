FROM postgres:18

RUN apt-get update \
    && apt-get install --yes --no-install-recommends locales \
    && sed -i '/^# *ru_RU.UTF-8 UTF-8/s/^# *//' /etc/locale.gen \
    && locale-gen ru_RU.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

COPY postgresql.conf /etc/postgresql/postgresql.conf
COPY 01-schema.sql /docker-entrypoint-initdb.d/01-schema.sql
COPY 02-demo-data.sql /docker-entrypoint-initdb.d/02-demo-data.sql
COPY 03-create-app-user.sh /docker-entrypoint-initdb.d/03-create-app-user.sh

RUN chmod 0555 /docker-entrypoint-initdb.d/03-create-app-user.sh

CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]

