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
import os
import sys
from pathlib import Path
from signal import signal, SIGINT, SIGTERM
from time import sleep
from urllib.request import urlopen

import click
import yaml

from ascii_telnet.ascii_movie import get_loaded_movie
from ascii_telnet.ascii_player import VT100Player
from ascii_telnet.ascii_server import TelnetRequestHandler, ThreadedTCPServer
from ascii_telnet.connection_notifier import send_notification
from ascii_telnet.movie_maker import make_movie
from ascii_telnet.prompt_resolver import Dialogue

DNS_UPDATE_URL = os.getenv('DNS_UPDATE_URL')

current_directory = Path(__file__).parent
default_movie = current_directory / 'movies' / 'movie.pkl'


def termination_handler(*args):
    try:
        send_notification("Server has been terminated!")
    except Exception:
        pass
    exit(0)


def runTcpServer(interface, port, filename, dialogue: Dialogue):
    """
    Start a TCP server that a client can connect to that streams the output of
     Ascii Player

    Args:
        interface (str):  bind to this interface
        port (int): bind to this port
        filename (str): file name of the ASCII movie. Can be a txt file, yaml file, or pickled movie file.
        dialogue (Dialogue): The Dialogue object to run
    """
    signal(SIGINT, termination_handler)
    signal(SIGTERM, termination_handler)
    if DNS_UPDATE_URL:
        print("updating dynamic DNS")
        response = urlopen(DNS_UPDATE_URL)
        print(f"DNS update response: {response.read().decode('utf-8')}")
    print("Loading movie...")
    movie = get_loaded_movie(filename)
    TelnetRequestHandler.set_up_handler_global_state(movie, dialogue)
    print("Launching server!")
    server = ThreadedTCPServer((interface, port), TelnetRequestHandler)
    server.serve_forever()


def runStdOut(filepath, dialogue: Dialogue = None):
    """
    Stream the output of the Ascii Player to STDOUT
    Args:
        filepath (str): file path of the ASCII movie
        dialogue_file (str): The file name for special dialogue options based upon visitor name
    """
    def prompt_func(prompt_text: str):
        return input(f'{prompt_text} ')

    def draw_frame_to_stdout(screen_buffer):
        sys.stdout.write(screen_buffer.read().decode('iso-8859-15'))

    if dialogue:
        dialogue.run(prompt_func, print)

    movie = get_loaded_movie(filepath)
    player = VT100Player(movie)
    player.draw_frame = draw_frame_to_stdout
    print(movie.create_viewing_area_box())
    sleep(5)
    player.play()


@click.group()
def cli():
    """Command line interface to run the various functions of the this tool."""
    pass


@cli.command(short_help="Plays the video, either to stdout or as a telnet server")
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
    type=click.Path(exists=True),
    help=(
        "File path of yaml file where keys are visitor name search strings and values are special messages to display "
        "to that specific visitor."
    )
)
def run(
    stdout,
    file,
    interface,
    port,
    dialogue_file
):
    """Plays the specified movie file, either via stdout (if the --stdout) flag is used, or as a Telnet server
    (the default)

    There are a few environment variables that are used by this process, for various purposes:

    \b
    To make gmail notifications work on server standup, termination, and client connection:
        * NOTIFICATION_USERNAME: The GMAIL username (without the @gmail.com)
        * NOTIFICATION_PASSWORD: The GMAIL password
        * DESTINATION_EMAIL_ADDRESS: The email address to receive the notifications
        * APP_NAME: The name of the app to include in the notifications

        If any of the above environment variables are not set, gmail notification will not happen.

    \b
    To update DNS entry (for example, when using FreeDNS or similar service):
        DNS_UPDATE_URL: The url to send a GET request to in order to update the DNS A Record

        If this is not set, DNS records will not be updated
    """
    if dialogue_file:
        with open(dialogue_file) as f:
            result = yaml.unsafe_load(f)
            dialogue = result['dialogue']
    try:
        if stdout:
            runStdOut(file, dialogue)
        else:
            print("Running TCP server on {0}:{1}".format(interface, port))
            print("Playing movie {0}".format(file))
            runTcpServer(interface, port, file, dialogue)

    except KeyboardInterrupt:
        print("Ascii Player Quit.")


@cli.command(short_help="Creates a pickled movie to play from a video file.")
@click.option(
    '-i',
    '--video-file-in',
    required=True,
    type=click.Path(exists=True),
    help="A valid video file, such as mp4, that can be rendered using ffmpeg to produce movie."
)
@click.option(
    '-o',
    '--pickle-file-out',
    required=True,
    help="The output filename to save the pickled movie to. Should end with .pkl"
)
@click.option(
    '--node-path',
    type=click.Path(exists=True),
    help="Path to NodeJS executable. If not specified, will rely on 'node' being in your PATH"
)
@click.option(
    '-s',
    '--subtitles',
    type=click.Path(exists=True),
    help="Subtitles file path. This should be a text file where each line is a 'slide'."
)
@click.option(
    '--subtitle-seconds',
    type=click.INT,
    default=5,
    help=(
        "Default number of seconds per slide in subtitles. Can be overridden with a line starting with '#|'. where the "
        "number is the number of seconds it should display for."
    )
)
def make(
    video_file_in,
    pickle_file_out,
    node_path,
    subtitles,
    subtitle_seconds
):
    """Creates an ascii-movie from a video file and then saves it as a pickle for fast loading later.

    Note: This method requires the ascii-video nodejs package installed using the attached package.json with at least
    node version 10. Why? Because this is simply the best video-to-ascii conversion tool I could find that produced
    colorful, text-based output into a single file. This functionality COULD be produced in native Python, but nothing
    similar seems to exist at this point.
    """
    make_movie(video_file_in, pickle_file_out, node_path, subtitles, subtitle_seconds)


@cli.command(short_help="Combines multiple movies together into a single move, output to a pickle file.")
@click.option(
    '-m',
    '--movie',
    multiple=True,
    type=click.Path(exists=True),
    required=True,
    help="Movie files to combine. Can be .txt, .yaml, or .pkl. This option can be used multiple times."
)
@click.option(
    '-o',
    '--pickle_file_out',
    type=click.Path(),
    required=True,
    help="Output filepath for the combined and pickled movie file."
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
