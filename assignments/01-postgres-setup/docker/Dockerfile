FROM postgres:18

RUN apt-get update \
    && apt-get install --yes --no-install-recommends locales \
    && sed -i '/^# *ru_RU.UTF-8 UTF-8/s/^# *//' /etc/locale.gen \
    && locale-gen ru_RU.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

COPY postgresql.conf /etc/postgresql/postgresql.conf
COPY init-user.sh /docker-entrypoint-initdb.d/10-init-user.sh

RUN chmod 0555 /docker-entrypoint-initdb.d/10-init-user.sh

CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]

