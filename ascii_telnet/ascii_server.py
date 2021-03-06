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
from itertools import chain

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

ESC = chr(27)
CLEAR_SCREEN = ESC + '[2J'
CLEAR_LINE = ESC + '[2K'
LINE_UP = ESC + 'D'
MOVE_TO_TOP_LEFT = ESC + "[1;1H"


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
            try:
                self.verify_is_human()
            except NotAHumanError:
                print(f"Nonhuman visited")
                return
            self.prepare_for_screen_size()
            if self.dialogue_options:
                visitor = self.run_visitor_dialogue()
                if 'adventurer' in visitor.lower():
                    visitor = self.run_adventure()

            self.player = VT100Player(self.movie)
            self.player.draw_frame = self.draw_frame
            self.player.play()
            self.wfile.write(b'\r\n')
            if self.dialogue_options:
                self.prompt_for_parting_message(visitor)
        except BrokenPipeError:
            pass

    def run_visitor_dialogue(self):
        results = self.dialogue_options.run('visitor', self.prompt, self.output)
        visitor = results['input']
        notification = f"Server has been visited by {visitor} at {self.client_address[0]}!"
        self.notify(notification)
        if results['resolved']:
            self.prompt('Press enter to continue...')
        return visitor

    def run_adventure(self):
        while True:
            results = self.dialogue_options.run('adventure', self.prompt, self.output)
            adventurer_name = results['input']
            readable_results = Dialogue.make_dialogue_readable(results)
            result_text = json.dumps(readable_results, indent='\t')
            notification = f'An adventurer has come! His name is {adventurer_name}.\nHis path: {result_text}'
            self.notify(notification)
            horizontal_bar = '-' * self.movie.screen_width
            response = self.prompt(
                f"\n{horizontal_bar}\nPress enter to continue or enter 'retry' to answer differently. You might find "
                f"you end up with a VERY different adventure..."
            )
            if 'retry' in response:
                continue
            return adventurer_name

    def prepare_for_screen_size(self):
        self.output("A box is about to be shown to help you prepare your terminal window size.")
        time.sleep(5)
        screen_box = self.movie.create_viewing_area_box()
        for second in reversed(range(1, 16)):
            self.output(f"{CLEAR_SCREEN}{MOVE_TO_TOP_LEFT}\r")
            self.output(screen_box)
            self.output(f"Continuing in {second} seconds...", False)
            time.sleep(1)

    def output(self, output_text, return_at_end=True):
        endswith_space = output_text.endswith(' ')
        lines = output_text.splitlines()
        wrapped_lines = chain.from_iterable(
            textwrap.wrap(line, self.movie.screen_width, replace_whitespace=False)
            if line
            else ['']
            for line in lines
        )
        wrapped = '\r\n'.join(wrapped_lines)
        if endswith_space:
            wrapped += ' '
        if return_at_end and not wrapped.endswith('\r\n'):
            wrapped += '\r\n'

        line_count = wrapped.count('\r\n')
        if line_count > self.movie.screen_height:
            self._output_long_text(wrapped)
        else:
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
            with_tabs_replaced = notification_text.replace('\t', '....')
            send_notification(with_tabs_replaced)
        except MisconfiguredNotificationError:
            print(notification_text)

    def _output_long_text(self, long_text):
        lines = long_text.split('\r\n')
        window_size = self.movie.screen_height - 4
        window = lines[:window_size]
        start_index = len(window) - 1
        end_index = len(lines) - 1
        current_index = start_index

        def scroll_down():
            nonlocal current_index
            window.pop(0)
            current_index += 1
            window.append(lines[current_index])

        while True:
            to_print = '\r\n'.join(window)
            encoded = to_print.encode('ISO-8859-1')
            # Clear the line, return cursor to first column and move up one line
            self.wfile.write(f'{CLEAR_SCREEN}{LINE_UP}'.encode())
            self.wfile.write(encoded)
            if current_index < end_index:
                response = self.prompt(
                    f"\n{'-' * self.movie.screen_width}\n\n"
                    f"Press <Enter> to scroll, or enter 'bottom' to scroll to the bottom..."
                )
                if 'bottom' in response:
                    current_index = end_index
                    window = lines[end_index - window_size:]
                else:
                    scroll_down()
            else:
                break
