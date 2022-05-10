FROM docker.io/library/python:3.11.0b1

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    XDG_CONFIG_HOME=/config \
    NET_TEXTFSM=/usr/src/app/templates

WORKDIR /usr/src/app

COPY ./requirements.txt /usr/src/app/requirements.txt
RUN python -m pip install -r requirements.txt

ADD . /usr/src/app

CMD python ./main.py