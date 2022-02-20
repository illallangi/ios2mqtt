from os import environ
from time import sleep
from netmiko import ConnectHandler
import paho.mqtt.client as mqtt  # import the client1
from json import dumps
from re import compile as re_compile


if "SWITCH_ADDRESS" not in environ:
    raise Exception("SWITCH_ADDRESS not defined")
if "SWITCH_USERNAME" not in environ:
    raise Exception("SWITCH_USERNAME not defined")
if "SWITCH_PASSWORD" not in environ:
    raise Exception("SWITCH_PASSWORD not defined")
if "MQTT_ADDRESS" not in environ:
    raise Exception("MQTT_ADDRESS not defined")

SWITCH_ADDRESS = environ["SWITCH_ADDRESS"]
SWITCH_USERNAME = environ["SWITCH_USERNAME"]
SWITCH_PASSWORD = environ["SWITCH_PASSWORD"]
MQTT_ADDRESS = environ["MQTT_ADDRESS"]
MQTT_TOPIC = environ.get("MQTT_TOPIC", SWITCH_ADDRESS)

INTERFACES_COMMAND = "show interfaces"
IP_COMMAND = "show ip int brief"
POE_COMMAND = "show power inline"

router = {
    "host": SWITCH_ADDRESS,
    "username": SWITCH_USERNAME,
    "password": SWITCH_PASSWORD,
    "device_type": "cisco_ios",
    "verbose": True,
    "allow_agent": False,
    "keepalive": 15,
    "conn_timeout": 60,
}

topics = []


def short_intf_name(
    s,
    d={
        "/": "-",
        "fastethernet": "fe",
        "gigabitethernet": "gi",
        "vlan": "vl",
    },
):
    for k in d:
        s = s.replace(k, d[k])
    return f"module-{s}" if s.isdigit() else s


def float_or_string(s):
    try:
        return float(s)
    except:
        return s


def on_connect(
    client,
    userdata,
    flags,
    rc,
):
    client.publish(
        f"ios2mqtt/{MQTT_TOPIC}/status",
        payload="online",
        qos=0,
        retain=True,
    )


on_message_pattern = re_compile(rf"ios2mqtt/{MQTT_TOPIC}/switch/(.*)_poe/command")


def on_message(client, userdata, message):
    print("message received ", str(message.payload.decode("utf-8")))
    print("message topic=", message.topic)
    print("message qos=", message.qos)
    print("message retain flag=", message.retain)
    interface = on_message_pattern.search(message.topic).group(1).replace("-", "/")
    print("Interface: " + interface)

    print(
        userdata.send_config_set(
            [
                f"int {interface}",
                "power inline never"
                if message.payload.decode("utf-8") in ["OFF"]
                else "no power inline never",
            ]
        )
    )

def main():
    with ConnectHandler(
        **router,
    ) as p:
        mqttc = mqtt.Client(userdata=p)

        mqttc.on_connect = on_connect
        mqttc.on_message = on_message
        mqttc.will_set(
            f"ios2mqtt/{MQTT_TOPIC}/status",
            payload="offline",
            qos=0,
            retain=True,
        )

        mqttc.connect(
            MQTT_ADDRESS,
        )

        mqttc.loop_start()

        while True:
            update(mqttc, p)
            sleep(10)


def update(mqttc, p):
    interfaces = {
        short_intf_name(interface["intf"].lower()): {
            key: float_or_string(interface[key])
            for key in interface
            if key not in ["intf"] and interface[key] not in [""]
        }
        for interface in p.send_command(
            INTERFACES_COMMAND,
            use_textfsm=True,
        )
    }

    ip = {
        short_intf_name(interface["intf"].lower()): {
            key: float_or_string(interface[key])
            for key in interface
            if key not in ["intf"] and interface[key] not in [""]
        }
        for interface in p.send_command(
            IP_COMMAND,
            use_textfsm=True,
        )
    }

    poe = {
        short_intf_name(interface["intf"].lower()): {
            key: float_or_string(interface[key])
            for key in interface
            if key not in ["intf"] and interface[key] not in [""]
        }
        for interface in p.send_command(
            POE_COMMAND,
            use_textfsm=True,
        )
    }

    indexes = list(set(list(interfaces.keys()) + list(ip.keys()) + list(poe.keys())))

    combined = {
        interface: {
            **(interfaces.get(interface, {})),
            **(ip.get(interface, {})),
            **(poe.get(interface, {})),
        }
        for interface in indexes
    }

    for interface in [k for k in combined if "power" in combined[k].keys()]:
        mqttc.publish(
            f"ios2mqtt/{MQTT_TOPIC}/sensor/{interface}_power/state",
            payload=combined[interface]["power"],
            qos=0,
            retain=True,
        )
        mqttc.publish(
            f"homeassistant/sensor/{MQTT_TOPIC}/{interface}_power/config",
            payload=dumps(
                {
                    "dev_cla": "power",
                    "unit_of_meas": "W",
                    "stat_cla": "measurement",
                    "name": f"{interface.title()} Power",
                    "stat_t": f"ios2mqtt/{MQTT_TOPIC}/sensor/{interface}_power/state",
                    "avty_t": f"ios2mqtt/{MQTT_TOPIC}/status",
                    "uniq_id": f"ios{MQTT_TOPIC}{interface}power",
                    "dev": {
                        "ids": "600194fb099d",
                        "name": f"{MQTT_TOPIC}",
                        "sw": "esphome v2021.12.3 Jan 12 2022, 12:28:58",
                        "mdl": "esp01_1m",
                        "mf": "espressif",
                    },
                }
            ),
            qos=0,
            retain=True,
        )

    for interface in [k for k in combined if "admin" in combined[k].keys()]:
        mqttc.publish(
            f"ios2mqtt/{MQTT_TOPIC}/switch/{interface}_poe/state",
            payload="ON" if combined[interface]["admin"] in ["auto"] else "OFF",
            qos=0,
            retain=True,
        )

        mqttc.publish(
            f"homeassistant/switch/{MQTT_TOPIC}/{interface}_poe/config",
            payload=dumps(
                {
                    "name": f"{interface.title()} POE",
                    "stat_t": f"ios2mqtt/{MQTT_TOPIC}/switch/{interface}_poe/state",
                    "cmd_t": f"ios2mqtt/{MQTT_TOPIC}/switch/{interface}_poe/command",
                    "avty_t": f"ios2mqtt/{MQTT_TOPIC}/status",
                    "uniq_id": f"ios{MQTT_TOPIC}{interface}poe",
                    "dev": {
                        "ids": "600194fb099d",
                        "name": f"{MQTT_TOPIC}",
                        "sw": "esphome v2021.12.3 Jan 12 2022, 12:28:58",
                        "mdl": "esp01_1m",
                        "mf": "espressif",
                    },
                }
            ),
            qos=0,
            retain=True,
        )

        if f"ios2mqtt/{MQTT_TOPIC}/switch/{interface}_poe/command" not in topics:
            mqttc.subscribe(f"ios2mqtt/{MQTT_TOPIC}/switch/{interface}_poe/command", 2)
            print(
                f"Subscribed to 'ios2mqtt/{MQTT_TOPIC}/switch/{interface}_poe/command'"
            )
            topics.append(f"ios2mqtt/{MQTT_TOPIC}/switch/{interface}_poe/command")

    mqttc.publish(
        f"ios2mqtt/{MQTT_TOPIC}/indexes",
        payload=dumps(indexes),
        qos=0,
        retain=True,
    )

    mqttc.publish(
        f"ios2mqtt/{MQTT_TOPIC}/interfaces",
        payload=dumps(interfaces),
        qos=0,
        retain=True,
    )

    mqttc.publish(
        f"ios2mqtt/{MQTT_TOPIC}/ip",
        payload=dumps(ip),
        qos=0,
        retain=True,
    )

    mqttc.publish(
        f"ios2mqtt/{MQTT_TOPIC}/poe",
        payload=dumps(poe),
        qos=0,
        retain=True,
    )


main()
