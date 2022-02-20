ios2mqtt
============

Exposes Cisco IOS POE-enabled ports to MQTT, and thus to Home Assistant.

Usage
-------

    docker run -it --rm \
      -e SWITCH_ADDRESS=192.0.2.1 \
      -e SWITCH_USERNAME=root \
      -e SWITCH_PASSWORD=Hunter2 \
      -e MQTT_ADDRESS=192.0.2.3 \
      ghcr.io/illallangi/ios2mqtt:latest
