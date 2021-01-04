# coding=utf-8
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
import errno
import json
import socket
import textwrap
import time

import yaml

from ascii_telnet.ascii_movie import Movie
from ascii_telnet.ascii_player import VT100Player
from ascii_telnet.connection_notifier import send_notification, MisconfiguredNotificationError
from ascii_telnet.prompt_resolver import Dialogue

try:
    # noinspection PyCompatibility
    from socketserver import StreamRequestHandler, ThreadingMixIn, TCPServer
except ImportError:  # Py2
    # noinspection PyCompatibility,PyUnresolvedReferences
    from SocketServer import StreamRequestHandler, ThreadingMixIn, TCPServer


class ThreadedTCPServer(ThreadingMixIn, TCPServer):
    daemon_threads = True


# Telnet special command codes
IAC = 255  # "Interpret As Command"
DONT = 254
DO = 253
WONT = 252
WILL = 251
SE = 240  # Subnegotiation End
NOP = 241  # No Operation
DM = 242  # Data Mark
BRK = 243  # Break
IP = 244  # Interrupt process
AO = 245  # Abort output
AYT = 246  # Are You There
EC = 247  # Erase Character
EL = 248  # Erase Line
GA = 249  # Go Ahead
SB = 250  # Subnegotiation Begin
NAWS = 31


class NotAHumanError(Exception): pass


class TelnetRequestHandler(StreamRequestHandler):
    """
    Request handler used for multi threaded TCP server
    @see: SocketServer.StreamRequestHandler
    """

    movie = None
    dialogue_options = None

    @classmethod
    def set_up_handler_global_state(
        cls,
        movie: Movie,
        dialogue_options: Dialogue,
    ):
        cls.movie = movie
        cls.dialogue_options = dialogue_options

    def handle(self):
        try:
            self.verify_is_human()
        except NotAHumanError:
            print(f"Nonhuman visited")
            return
        if self.dialogue_options:
            visitor = self.run_visitor_dialogue()

        self.prepare_for_screen_size()
        self.player = VT100Player(self.movie)
        self.player.draw_frame = self.draw_frame
        self.output("Here we go!")
        time.sleep(2)
        self.player.play()
        self.wfile.write(b'\r\n')
        if self.dialogue_options:
            self.prompt_for_parting_message(visitor)

    def run_visitor_dialogue(self):
        while True:
            results = self.dialogue_options.run('visitor', self.prompt, self.output)
            visitor = results['input']
            result_text = json.dumps(results, indent='    ')
            notification = f"Server has been visited by {visitor} at {self.client_address[0]}!: {result_text}"
            self.notify(notification)
            if results['resolved']:
                response = self.prompt("Press enter to continue or enter 'retry' to answer differently...")
                if 'retry' in response:
                    continue
            return visitor

    def prompt_for_name(self) -> str:
        return self.prompt("Who dis? (Real name is best)")

    def prepare_for_screen_size(self):
        self.output("\nUse the following to make sure your terminal size is correct.")
        time.sleep(2)
        screen_box = self.movie.create_viewing_area_box()
        self.output(screen_box)
        time.sleep(15)

    def output(self, output_text, return_at_end=True):
        endswith_space = output_text.endswith(' ')
        with_carriage_returns = output_text.replace('\n', '\r\n')
        wrapped = '\r\n'.join(textwrap.wrap(with_carriage_returns, self.movie.screen_width, replace_whitespace=False))
        if endswith_space:
            wrapped += ' '
        if return_at_end and not wrapped.endswith('\r\n'):
            wrapped += '\r\n'
        encoded = wrapped.encode('ISO-8859-1')
        self.wfile.write(encoded)

    def prompt(self, prompt_text, max_bytes_in=300, pad_with_trailing_space=True) -> str:
        if pad_with_trailing_space:
            prompt_text += ' '
        self.rfile.flush()
        self.output(prompt_text, False)
        raw_bytes_in = self.rfile.readline(max_bytes_in)
        input_string = self.get_text_from_raw_bytes(raw_bytes_in)
        return input_string.strip()

    def get_text_from_raw_bytes(self, bytes_in: bytes) -> str:
        # Telnet is tricky and there are special command codes that can precede the input
        last_byte = None
        real_text_bytes = []
        for byte_integer in bytes_in:
            if last_byte == SB and byte_integer == SE:
                pass
            elif last_byte == SB:
                continue  # We'll skip everything between SB and SE
            elif last_byte in (IAC, WILL, WONT, DO, DONT):
                pass
            elif 240 <= byte_integer <= 255:
                pass
            else:
                real_text_bytes.append(byte_integer)
            last_byte = byte_integer

        remainder_of_bytes = bytes(real_text_bytes)
        decoded = remainder_of_bytes.decode('ISO-8859-1')
        return decoded

    def draw_frame(self, screen_buffer):
        """
        Gets the current screen buffer and writes it to the socket.
        """
        try:
            self.wfile.write(screen_buffer.read())
        except socket.error as e:
            if e.errno == errno.EPIPE:
                print("Client Disconnected.")
                self.player.stop()

    def verify_is_human(self):
        response = self.prompt("Are you a human?", 20)
        for answer in ['yes', 'yea', 'si', 'yep']:
            if answer in response.lower():
                self.output("Whew. Ok. I thought you were a robot. Close one!")
                return
        self.output("Robots are not welcome! Get off my lawn!")
        raise NotAHumanError()

    def prompt_for_parting_message(self, visitor_name: str):
        result = self.dialogue_options.run('parting_message', self.prompt, self.output)
        parting_message = result['input']
        notification = f"Parting message received from {visitor_name}: {parting_message}"
        self.notify(notification)

    def notify(self, notification_text: str):
        try:
            send_notification(notification_text)
        except MisconfiguredNotificationError:
            print(notification_text)
