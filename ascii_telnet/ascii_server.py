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
import time

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

    @classmethod
    def set_up_handler_global_state(cls, movie: Movie):
        cls.movie = movie

    def setup(self):
        send_notification("Server is standing up")
        return super().setup()

    def handle(self):
        visitor = self.prompt_for_name()
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
        self.wfile.write(
            (
                "You'll probably want to make your window wider.\r\n"
                "I'll give you a few to do that now.\r\n"
                "The following should be a single line\r\n"
                f"{self.movie.screen_width * '-'}\r\n"
                f"Also, Windows telnet is the WORST client. \r\n"
                f"You'll get a better experience with pretty much any other option."
            ).encode('ISO-8859-1')
        )
        time.sleep(10)
        self.wfile.write("\r\nHere we go!\r\n".encode('ISO-8859-1'))
        time.sleep(2)

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
