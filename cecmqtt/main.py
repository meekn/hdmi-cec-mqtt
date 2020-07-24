#!/usr/bin/env python
# -*- coding: utf-8 -*-

from logging import basicConfig, DEBUG
import click

from cecmqtt.daemon import CECBeebotteDaemon


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='verbose mode')
def main(verbose=False):
    '''
    Controls HDMI CEC devices via MQTT
    '''

    if verbose:
        basicConfig(level=DEBUG)


@main.command()
@click.argument('channel', type=str)
@click.argument('token', type=str)
def beebotte(channel, token, mapping=None):
    '''
    Controls HDMI CEC devices via Beebotte
    '''

    daemon = CECBeebotteDaemon(channel, token)
    daemon.run(None)
