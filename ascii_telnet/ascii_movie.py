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

import re

import yaml

ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

class Frame(object):
    def __init__(self, display_time=1):
        """
        One frame is typically 67 columns and 13 rows in effective size on screen.

        Use 'data' to get the lines.

        Args:
            display_time (int): the frame cycles this specific frame should be
                                 displayed (15 cycles per second).
        """
        self.display_time = display_time
        self.data = []  # frame lines

    @property
    def dimensions(self):
        height = len(self.data)
        width = max(
            len(ansi_escape.sub('', line))
            for line in self.data
        )
        return width, height


class TimeBar(object):
    height = 1

    def __init__(self, duration, length, left_decorator=u"<", spacer=u" ", right_decorator=u">", marker=u"o"):
        """
        TimeBar that appears at the bottom of the screen.

        Args:
            duration (int): Frame count that this bar will be tracking
            length (int): Length in characters that the TimeBar will be on the screen
            left_decorator (str): Decorator on the left side
            spacer (str): Spacer in between left and right decorators
            right_decorator (str): Decorator on the right side
            marker (str): Marker for position in Ascii Movie
        """
        self.length = length

        self.duration = duration

        self.spacer = spacer
        self.left_decorator = left_decorator
        self.right_decorator = right_decorator
        self.marker = marker

        self.internal_length = self.length - len(self.left_decorator) - len(self.right_decorator)

        if len(self.left_decorator + self.right_decorator + self.marker) > self.length:
            raise ValueError("This TimeBar is too short for these decorators: {0} {1} {2}".format(self.left_decorator,
                                                                                               self.marker,
                                                                                               self.right_decorator))

    @property
    def _empty_timebar(self):
        time_bar_internals = u"{0:{spacer}>{length}}".format(u"", spacer=self.spacer, length=self.internal_length)

        return u"{tb.left_decorator}{internals}{tb.right_decorator}".format(internals=time_bar_internals, tb=self)

    def get_marker_postion(self, frame_num):
        """
        Return the index for the marker position on the TimeBar's internal length
        Args:
            frame_num: The Frame Number that the movie that the TimeBar marker should reflect

        Returns:
            int: index number for marker

        """

        return int(round(self.internal_length / self.duration * frame_num, 0))

    def get_timebar(self, frame_num):
        """
        Args:
            frame_num: The Frame Number that the movie that the TimeBar marker should reflect

        Returns:
            str: String representation of the TimeBar at the given Frame Number
                Example:  "<    o               >"
        """
        marker_pos = self.get_marker_postion(frame_num)

        if marker_pos >= self.internal_length:
            # Make sure we never overwrite the end decorator.
            marker_pos = self.internal_length - 1

        return self._empty_timebar[:marker_pos + len(self.left_decorator)] + \
               self.marker + \
               self._empty_timebar[marker_pos + len(self.right_decorator) + 1:]


class Movie(object):
    def __init__(self, width=80, height=24):
        """
        A Movie object consists of frames and is empty by default.
        Movies are loaded from text files.
        A movie only can be loaded once. A second try will fail.

        Args:
            width (int): Movie screen width.
            height (int): Movie screen height
        """
        self.frames = []
        self._loaded = False

        f = Frame()
        f.data.append("No movie yet loaded.")
        self.frames.append(f)
        self.screen_width = None
        self.screen_height = None
        self._frame_width = None
        self._frame_height = None
        self.left_margin = None
        self.top_margin = None

        self.set_screen_dimensions(width, height)
        self.set_frame_dimensions(67, 13)

    def set_screen_dimensions(self, width, height):
        self.screen_width = width
        self.screen_height = height

    def set_frame_dimensions(self, width, height):
        self._frame_width = width
        if width > self.screen_width:
            self.screen_width = width

        if height + TimeBar.height:
            self.screen_height = height + TimeBar.height

        self._frame_height = height
        self.left_margin = (self.screen_width - self._frame_width) // 2
        self.top_margin = (self.screen_height - self._frame_height - TimeBar.height) // 2

    def load(self, filepath):
        """
        Loads the ASCII movie from given text file.
        Using an encoded format, described on
        http://www.asciimation.co.nz/asciimation/ascii_faq.html
        In short:
            67x14 chars
            lines separated with \n
            first line is a number telling delay in number of frames
            13 lines effective frame size
            15 frames per second

        Args:
            filepath (str): Path to Ascii Movie Data
        """
        if self._loaded:
            # we don't want to be loaded twice.
            return False

        with open(filepath) as f:
            if filepath.endswith('.txt'):
                self.frames = self._get_text_frames(f)
            elif filepath.endswith('.yaml'):
                self.frames = self._get_yaml_frames(f)

        self._loaded = True
        return True

    def _get_text_frames(self, file_handle):

        lines_per_frame = self._frame_height + TimeBar.height  # incl. meta data (time information)
        current_frame = None

        for line_num, line in enumerate(file_handle):
            time_metadata = None

            if line_num % lines_per_frame == 0:
                time_metadata = int(line.strip())

            if time_metadata is not None:
                current_frame = Frame(display_time=time_metadata)
                self.frames.append(current_frame)
            else:
                line = self._fix_line(line)
                current_frame.data.append(line)

    def _get_yaml_frames(self, file_handle):
        yaml_reader = yaml.parse(file_handle)
        return list(self.generate_frames(yaml_reader))

    def generate_frames(self, yaml_reader):
        dimensions_evaluated = False
        for event in yaml_reader:
            if isinstance(event, yaml.StreamEndEvent):
                break
            if isinstance(event, yaml.ScalarEvent):
                frame_str: str = event.value
                lines = frame_str.splitlines()
                frame = Frame()
                frame.data = lines[:-1]
                if not dimensions_evaluated:
                    width, height = frame.dimensions
                    self.set_frame_dimensions(width, height)
                    dimensions_evaluated = True
                yield frame

    def _fix_line(self, line):
        line = line.rstrip()
        # Second fill line out with blanks so that any previous
        # characters are overwritten
        line = line.ljust(self._frame_width)
        # Third center the frame on the screen
        line = line.rjust(self.left_margin + self._frame_width)
        return line

