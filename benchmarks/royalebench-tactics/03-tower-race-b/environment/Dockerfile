FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash curl git ca-certificates sudo procps \
    && rm -rf /var/lib/apt/lists/*

# referee: owns the engine, the match and the action log. player: the agent.
# Agent harnesses install as root under /root/.local and then run as player, so /root is made
# traversable (0711: no listing) for the player to execute the installed CLI.
RUN useradd --system --home-dir /opt/referee --shell /usr/sbin/nologin referee \
    && useradd --create-home --shell /bin/bash player

RUN python3 -m venv /opt/referee/venv \
    && /opt/referee/venv/bin/pip install --no-cache-dir royalegym==0.1.28 royalesim==0.1.48 numpy==2.5.4 gymnasium==1.4.0 pettingzoo==1.27.0 msgspec==0.22.0 cloudpickle==3.1.2 typing-extensions==4.16.0 farama-notifications==0.0.6

COPY referee/ /opt/referee/app/cr_arena/
COPY task.json /opt/referee/task.json
COPY cr /usr/local/bin/cr
COPY royale-start-server /usr/local/sbin/royale-start-server
COPY sudoers /etc/sudoers.d/royale

RUN chmod 0755 /usr/local/bin/cr /usr/local/sbin/royale-start-server \
    && chmod 0440 /etc/sudoers.d/royale \
    && mkdir -p /var/lib/royale /var/lib/royale-run /app /logs/agent /logs/verifier \
    && chown -R referee:referee /opt/referee /var/lib/royale /var/lib/royale-run \
    && chmod 0700 /opt/referee /var/lib/royale \
    && chmod 0755 /var/lib/royale-run \
    && chown player:player /app \
    && chmod 0777 /logs /logs/agent /logs/verifier \
    && chmod 0711 /root \
    && cd /opt/referee/app && /opt/referee/venv/bin/python -c "import cr_arena.royale_task"

ENV PYTHONHASHSEED=0 LANG=C.UTF-8 LC_ALL=C.UTF-8
WORKDIR /app
