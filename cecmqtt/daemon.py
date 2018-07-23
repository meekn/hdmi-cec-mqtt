#!/usr/bin/env python
# -*- coding: utf-8 -*-

from logging import getLogger
import json
import pkg_resources

import cec
import paho.mqtt.client as mqtt
from bidict import bidict


logger = getLogger(__name__)


class DeviceController(object):
    def __init__(self, device):
        self.target = device
        self._action_by_name = {
            'power_on': self.target.power_on,
            'standby': self.target.standby,
        }

    def on_message(self, client, userdata, msg):
        logger.info('Received message for {}'.format(self.target.osd_string))
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
            action = self._action_by_name[action_name]
        except KeyError as e:
            logger.warning('Unsupported action specified ("{}")'.format(action_name))
            return

        action()


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

    def _create_topic_fullname(self, subtopic):
        return '{}/{}'.format(self._bus_topic_name, subtopic)

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

        topic_fullnames_with_logical_address = (
            (self._create_topic_fullname(logical_address_name), logical_address)
            for logical_address_name, logical_address in self.LOGICAL_ADDRESS_BY_NAME.items()
        )

        topic_fullnames_with_device_controller = (
            (topic_fullname, DeviceController(cec.Device(logical_address)))
            for topic_fullname, logical_address in topic_fullnames_with_logical_address
        )

        client = mqtt.Client()
        client.username_pw_set(self._username_and_password)
        client.on_connect = self._on_connect
        for topic_fullname, device_controller in topic_fullnames_with_device_controller:
            client.message_callback_add(topic_fullname, device_controller.on_message)

        if self._tls_cert_filename:
            client.tls_set(self._tls_cert_filename)

        try:
            client.connect(self._broker, self._port)
        except RuntimeError as e:
            logger.error(e)
            return

        client.loop_forever()


class CECBeebotteDaemon(CECMQTTDaemon):
    MQTT_BROKER = 'mqtt.beebotte.com'
    MQTT_PORT = 8883
    MQTT_TLS_CERT_FILEPATH = 'data/mqtt.beebotte.com.pem'

    def __init__(self, channel, token):
        mqtt_username_and_password = 'token:{}'.format(token)

        super().__init__(
            self.MQTT_BROKER,
            self.MQTT_PORT,
            mqtt_username_and_password,
            channel,
            tls_cert_filename=pkg_resources.resource_filename('cecmqtt', self.MQTT_TLS_CERT_FILEPATH),
        )
