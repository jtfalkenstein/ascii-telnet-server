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
        os.environ['COLUMNS'] = str(movie.screen_width)
        os.environ['LINES'] = str(movie.screen_height)

    def handle(self):
        visitor = self.prompt_for_name()
        try:
            send_notification(f"Server has been visited by {visitor}!")
        except MisconfiguredNotificationError:
            pass

        self.player = VT100Player(self.movie)
        self.player.draw_frame = self.draw_frame
        self.player.play()

    def prompt_for_name(self) -> str:
        self.rfile.flush() # Empty it from anything that precedes
        self.wfile.write("Who dis? ".encode('ISO-8859-1'))
        visitor_bytes = self.rfile.readline()
        received_string = visitor_bytes.decode('ISO-8859-1')
        split_by_hash = received_string.split('#')
        return split_by_hash[-1].strip()

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
