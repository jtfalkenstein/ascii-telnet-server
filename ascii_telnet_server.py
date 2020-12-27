# coding=utf-8
# !/usr/bin/env python

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Copyright (c) 2008, Martin W. Kirst All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are
#  met:
#
#  Redistributions of source code must retain the above copyright notice,
#  this list of conditions and the following disclaimer.
#  Redistributions in binary form must reproduce the above copyright notice,
#  this list of conditions and the following disclaimer in the documentation
#  and/or other materials provided with the distribution.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
#  IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
#  TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
#  PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
#  TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
#  PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
#  LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
#  NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
  ASCII art movie Telnet player.
  Version         : 0.1

  Can stream an ~20 minutes ASCII movie via Telnet emulation
  as stand alone server or via xinetd daemon.
  Tested with Python 2.6+, Python 3.5+

  Original art work : Simon Jansen ( http://www.asciimation.co.nz/ )
  Telnetification
  & Player coding   : Martin W. Kirst ( https://github.com/nitram509/ascii-telnet-server )
  Python3 Update: Ryan Jarvis

"""
import os
import sys
from pathlib import Path

import click
import yaml

from ascii_telnet.ascii_movie import get_loaded_movie
from ascii_telnet.ascii_player import VT100Player
from ascii_telnet.ascii_server import TelnetRequestHandler, ThreadedTCPServer
from ascii_telnet.movie_maker import make_movie
from ascii_telnet.connection_notifier import send_notification
from signal import signal, SIGINT, SIGTERM
from urllib.request import urlopen

from os import environ
DNS_UPDATE_URL = os.getenv('DNS_UPDATE_URL')

current_directory = Path(__file__).parent
default_movie = current_directory / 'movies' / 'movie.pkl'


def termination_handler(*args):
    send_notification("Server has been terminated!")


def runTcpServer(interface, port, filename, dialogue_file=None):
    """
    Start a TCP server that a client can connect to that streams the output of
     Ascii Player

    Args:
        interface (str):  bind to this interface
        port (int): bind to this port
        filename (str): file name of the ASCII movie
    """
    signal(SIGINT, termination_handler)
    signal(SIGTERM, termination_handler)
    if DNS_UPDATE_URL:
        print("updating dynamic DNS")
        response = urlopen(DNS_UPDATE_URL)
        print(f"DNS update response: {response.read()}")
    print("Loading movie...")
    movie = get_loaded_movie(filename)
    if dialogue_file:
        with open(dialogue_file) as f:
            dialogue_options = yaml.load(f)
    else:
        dialogue_options = None
    TelnetRequestHandler.set_up_handler_global_state(movie, dialogue_options)
    print("Launching server!")
    server = ThreadedTCPServer((interface, port), TelnetRequestHandler)
    server.serve_forever()


def runStdOut(filepath):
    """
    Stream the output of the Ascii Player to STDOUT
    Args:
        filepath (str): file path of the ASCII movie
    """

    def draw_frame_to_stdout(screen_buffer):
        sys.stdout.write(screen_buffer.read().decode('iso-8859-15'))

    movie = get_loaded_movie(filepath)
    player = VT100Player(movie)
    player.draw_frame = draw_frame_to_stdout
    player.play()


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    '--stdout',
    is_flag=True,
    help=(
        "Run with STDIN and STDOUT, for example in XINETD " +
        "instead of stand alone TCP server. " +
        "Use with python option '-u' for unbuffered " +
        "STDIN STDOUT communication"
    )
)
@click.option(
    '-f',
    '--file',
    type=click.Path(exists=True),
    help="File containing the ASCII movie. It can be a .txt, .yaml, or .pkl file",
    default=str(default_movie)
)
@click.option(
    '-i',
    '--interface',
    default='0.0.0.0',
    help="Bind to this interface (default '0.0.0.0', all interfaces)"
)
@click.option(
    '-p',
    '--port',
    default=23,
    help="Bind to this port (default 23, Telnet)",
)
@click.option(
    '-d',
    '--dialogue-file',
    type=click.Path(exists=True)
)
def run(
    stdout,
    file,
    interface,
    port,
    dialogue_file
):
    try:
        if stdout:
            runStdOut(file)
        else:
            print("Running TCP server on {0}:{1}".format(interface, port))
            print("Playing movie {0}".format(file))
            runTcpServer(interface, port, file, dialogue_file)

    except KeyboardInterrupt:
        print("Ascii Player Quit.")


@cli.command()
@click.option(
    '-i',
    '--video-file-in',
    required=True,
    type=click.Path(exists=True)
)
@click.option(
    '-o',
    '--pickle-file-out',
    required=True
)
@click.option(
    '--node-path',
    type=click.Path(exists=True)
)
@click.option(
    '-s',
    '--subtitles',
    type=click.Path(exists=True)
)
@click.option(
    '--subtitle-seconds',
    type=click.INT,
    default=5
)
def make(
    video_file_in,
    pickle_file_out,
    node_path,
    subtitles,
    subtitle_seconds
):
    make_movie(video_file_in, pickle_file_out, node_path, subtitles, subtitle_seconds)

@cli.command()
@click.option(
    '-m',
    '--movie',
    multiple=True,
    type=click.Path(exists=True),
    required=True
)
@click.option(
    '-o',
    '--pickle_file_out',
    type=click.Path(),
    required=True
)
def combine(movie, pickle_file_out):
    movie_iterator = (
        get_loaded_movie(movie_path)
        for movie_path in movie
    )
    first_movie = next(movie_iterator)
    for subsequent_movie in movie_iterator:
        first_movie += subsequent_movie

    first_movie.compress()
    first_movie.to_pickle(pickle_file_out)


if __name__ == "__main__":
    cli()
