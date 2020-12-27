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
from __future__ import division, print_function

import errno
import os
import socket
import textwrap
import time
from typing import Optional, Dict

from ascii_telnet.ascii_movie import Movie
from ascii_telnet.ascii_player import VT100Player
from ascii_telnet.connection_notifier import send_notification, MisconfiguredNotificationError

try:
    # noinspection PyCompatibility
    from socketserver import StreamRequestHandler, ThreadingMixIn, TCPServer
except ImportError:  # Py2
    # noinspection PyCompatibility,PyUnresolvedReferences
    from SocketServer import StreamRequestHandler, ThreadingMixIn, TCPServer


class ThreadedTCPServer(ThreadingMixIn, TCPServer):
    daemon_threads = True


class TelnetRequestHandler(StreamRequestHandler):
    """
    Request handler used for multi threaded TCP server
    @see: SocketServer.StreamRequestHandler
    """

    movie = None
    dialogue_options = None

    @classmethod
    def set_up_handler_global_state(cls, movie: Movie, dialogue_options: Optional[Dict[str, str]]):
        cls.movie = movie
        cls.dialogue_options = dialogue_options

    def setup(self):
        send_notification("Server is standing up")
        return super().setup()

    def handle(self):
        visitor = self.prompt_for_name()
        self.run_dialogue(visitor)
        self.prepare_for_screen_size()
        try:
            send_notification(f"Server has been visited by {visitor} at {self.client_address[0]}!")
        except MisconfiguredNotificationError:
            pass

        self.player = VT100Player(self.movie)
        self.player.draw_frame = self.draw_frame
        self.player.play()

    def prompt_for_name(self) -> str:
        self.rfile.flush()  # Empty it from anything that precedes
        self.wfile.write("Who dis? ".encode('ISO-8859-1'))
        visitor_bytes = self.rfile.readline(50)
        received_string = visitor_bytes.decode('ISO-8859-1')
        split_by_hash = received_string.split('#')
        return split_by_hash[-1].strip()

    def prepare_for_screen_size(self):
        self.output(
            f"{self.movie.screen_width * '-'}\n"
            "For the best viewing experience, you'll probably want to make your window wider\n"
            "I'll give you a few moments to do that now.\n"
            "The following should be a single line\n"
            f"{self.movie.screen_width * '-'}\n"
            f"Also, Windows telnet is the WORST client.\n"
            f"You'll get a better experience with pretty much any other option."
        )
        time.sleep(10)
        self.output("Here we go!")
        time.sleep(2)

    def output(self, output_text):
        if not output_text.endswith('\n'):
            output_text = f'{output_text}\n'
        with_carriage_returns = output_text.replace('\n', '\r\n')
        encoded = with_carriage_returns.encode('ISO-8859-1')
        self.wfile.write(encoded)

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

    def run_dialogue(self, visitor):
        for option in self.dialogue_options:
            if option.lower() in visitor.lower():
                self.output(f"SUPER SECRET MESSAGE JUST FOR {option.upper()}:")
                message = self.dialogue_options[option]
                wrapped = textwrap.wrap(message, self.movie.screen_width)
                with_line_breaks = '\n'.join(wrapped)
                self.output(with_line_breaks)
                self.output("...".center(self.movie.screen_width))
                time.sleep(15)
                break
