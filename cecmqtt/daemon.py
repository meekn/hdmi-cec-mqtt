#!/usr/bin/env python
# -*- coding: utf-8 -*-

from logging import getLogger
import json
import pkg_resources

import cec
import paho.mqtt.client as mqtt
from bidict import bidict


logger = getLogger(__name__)


class CECMQTTDaemon(object):
    LOGICAL_ADDRESS_BY_NAME = bidict({
        'AUDIOSYSTEM': cec.CECDEVICE_AUDIOSYSTEM,
        'BROADCAST': cec.CECDEVICE_BROADCAST,
        'FREEUSE': cec.CECDEVICE_FREEUSE,
        'PLAYBACKDEVICE1': cec.CECDEVICE_PLAYBACKDEVICE1,
        'PLAYBACKDEVICE2': cec.CECDEVICE_PLAYBACKDEVICE2,
        'PLAYBACKDEVICE3': cec.CECDEVICE_PLAYBACKDEVICE3,
        'RECORDINGDEVICE1': cec.CECDEVICE_RECORDINGDEVICE1,
        'RECORDINGDEVICE2': cec.CECDEVICE_RECORDINGDEVICE2,
        'RECORDINGDEVICE3': cec.CECDEVICE_RECORDINGDEVICE3,
        'TUNER1': cec.CECDEVICE_TUNER1,
        'TUNER2': cec.CECDEVICE_TUNER2,
        'TUNER3': cec.CECDEVICE_TUNER3,
        'TUNER4': cec.CECDEVICE_TUNER4,
        'TV': cec.CECDEVICE_TV,
    })

    def __init__(self, broker, port, username_and_password, bus_topic_name, tls_cert_filename=None):
        self._broker = broker
        self._port = port
        self._username_and_password = username_and_password
        self._bus_topic_name = bus_topic_name
        self._tls_cert_filename = tls_cert_filename

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            raise RuntimeError('Cannot connect to MQTT Broker (rc: {})'.format(rc))

        logger.info('Connected to MQTT broker')
        subscription_target_topic = '{}/+'.format(self._bus_topic_name)
        logger.info('Subscribe topic "{}"'.format(subscription_target_topic))
        client.subscribe(subscription_target_topic)

    def _create_device_topic_name(self, subtopic):
        return '{}/{}'.format(self._bus_topic_name, subtopic)

    def _create_message_handler(self, logical_address):
        device = cec.Device(logical_address)
        action_by_name = {
            'power_on': device.power_on,
            'standby': device.standby,
        }

        def on_message(client, userdata, msg):
            logger.info('Received message for {}'.format(device.osd_string))
            payload_string = msg.payload.decode('utf-8')
            logger.info(payload_string)
            parsed_payload = json.loads(payload_string)

            data = parsed_payload.get('data', [])

            try:
                action_name = data['action']
            except TypeError as e:
                logger.warning(e)
                return

            try:
                action = action_by_name[action_name]
            except KeyError as e:
                logger.warning('Unsupported action specified ("{}")'.format(action_name))
                return

            action()

        return on_message


    def run(self, mapping_definition=None):
        logger.info('Initializing CEC...')
        cec.init()
        logger.info('Done')

        for logical_address, device in cec.list_devices().items():
            logger.info('{}\t{}\t{}'.format(
                logical_address,
                self.LOGICAL_ADDRESS_BY_NAME.inv[logical_address],
                device.osd_string)
            )

        client = mqtt.Client()
        client.username_pw_set(self._username_and_password)
        client.on_connect = self._on_connect

        for logical_address_name, logical_address in self.LOGICAL_ADDRESS_BY_NAME.items():
            device_topic_name = self._create_device_topic_name(logical_address_name)
            message_handler = self._create_message_handler(logical_address)
            client.message_callback_add(device_topic_name, message_handler)

        if self._tls_cert_filename:
            client.tls_set(self._tls_cert_filename)

        logger.info('Connecting to MQTT server...')
        try:
            client.connect(self._broker, self._port)
        except RuntimeError as e:
            logger.error(e)
            return
        logger.info('Done')

        client.loop_forever()


class CECBeebotteDaemon(CECMQTTDaemon):
    BROKER = 'mqtt.beebotte.com'
    PORT = 8883
    TLS_CERT_FILEPATH = 'data/mqtt.beebotte.com.pem'

    def __init__(self, channel, token):
        mqtt_username_and_password = 'token:{}'.format(token)

        super().__init__(
            self.BROKER,
            self.PORT,
            mqtt_username_and_password,
            channel,
            tls_cert_filename=pkg_resources.resource_filename('cecmqtt', self.TLS_CERT_FILEPATH),
        )
