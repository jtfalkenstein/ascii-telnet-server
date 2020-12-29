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


class NotAHumanError(Exception): pass


class TelnetRequestHandler(StreamRequestHandler):
    """
    Request handler used for multi threaded TCP server
    @see: SocketServer.StreamRequestHandler
    """

    movie = None
    dialogue_options = None
    repo_url = None

    @classmethod
    def set_up_handler_global_state(
        cls,
        movie: Movie,
        dialogue_options: Optional[Dict[str, str]],
        repo_url: Optional[str]
    ):
        cls.movie = movie
        cls.dialogue_options = dialogue_options or {}
        cls.repo_url = repo_url

    def handle(self):
        visitor = self.prompt_for_name()
        try:
            self.verify_is_human()
        except NotAHumanError:
            print(f"Nonhuman visited: {visitor}")
            return

        try:
            send_notification(f"Server has been visited by {visitor} at {self.client_address[0]}!")
        except MisconfiguredNotificationError:
            pass
        self.run_dialogue(visitor)
        self.prepare_for_screen_size()
        self.player = VT100Player(self.movie)
        self.player.draw_frame = self.draw_frame
        self.player.play()
        self.prompt_for_parting_message(visitor)
        if self.repo_url:
            self.output(
                "\nInterested in how I did this? See my source code at: \n"
                f"{self.repo_url}"
            )

    def prompt_for_name(self) -> str:
        return self.prompt("Who dis? (Real name is best)")

    def prepare_for_screen_size(self):
        self.output(
            f"{self.movie.screen_width * '-'}\n"
            "For the best viewing experience, you'll probably want to make your window wider\n"
            "I'll give you a few moments to do that now.\n"
            "The following should be a single line\n"
            f"{self.movie.screen_width * '-'}\n"
            f"Also, Windows telnet is the WORST client. If you're on Windows, try using PuTTY or WSL."
        )
        time.sleep(20)
        self.output("Here we go!")
        time.sleep(2)

    def output(self, output_text, return_at_end=True):
        if return_at_end and not output_text.endswith('\n'):
            output_text = f'{output_text}\n'
        # Silly Windows
        with_carriage_returns = output_text.replace('\n', '\r\n')
        encoded = with_carriage_returns.encode('ISO-8859-1')
        self.wfile.write(encoded)

    def prompt(self, prompt_text, max_bytes_in=50, pad_with_trailing_space=True) -> str:
        if pad_with_trailing_space:
            prompt_text += ' '
        self.rfile.flush()
        self.output(prompt_text, False)
        raw_bytes_in = self.rfile.readline(max_bytes_in)
        input_string = self.get_text_from_raw_bytes(raw_bytes_in)
        return input_string.strip()

    def get_text_from_raw_bytes(self, bytes_in: bytes) -> str:
        byterator = iter(bytes_in)
        # Telnet is tricky and there are special command codes that can precede the input
        last_byte = None
        real_text_bytes = []
        for byte_integer in byterator:
            if SE <= byte_integer <= IAC:  # Normal telnet negotiation stuff
                continue
            if last_byte == WILL:
                continue
            real_text_bytes.append(byte_integer)

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

    def verify_is_human(self):
        response = self.prompt("Are you a human?", 20)
        for answer in ['yes', 'yea', 'si', 'yep']:
            if answer in response.lower():
                self.output("Whew. Ok. I thought you were a robot. Close one!")
                return
        self.output("Robots are not welcome! Get off my lawn!")
        raise NotAHumanError()

    def prompt_for_parting_message(self, visitor_name: str):
        self.output("\nLooks like you made it all the way to the end.")
        parting_message = self.prompt("Go ahead and leave the Ghost of Falkenstein a parting message.\n>>", 300)
        notification = f"Parting message received from {visitor_name}: {parting_message}"
        try:
            send_notification(notification)
        except MisconfiguredNotificationError:
            print(notification)
