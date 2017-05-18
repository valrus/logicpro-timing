from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

import io
import itertools
import json
import operator
import re
import sys
from datetime import timedelta
from decimal import Decimal
from textwrap import dedent

import attr

# This seems to be constant in Logic Pro
TICKS_PER_BEAT = 960

ELM_BREAK_TYPE_MAPPING = {
    '•': 'Syllable',
    '¬': 'Line',
    '¶': 'Page',
}


def set_up_parser():
    parser = ArgumentParser(description=__doc__,
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('cue_file')
    parser.add_argument('--json')
    parser.add_argument('--elm', default='lyrics.elm')
    return parser


@attr.s
class TaggedLine(object):
    line = attr.ib()
    tag = attr.ib()


def strip_int_trailing_period(s):
    try:
        return int(s.rstrip('.')) - 1
    except AttributeError:
        return int(s) - 1


def int_to_zero_index(s):
    return int(s) - 1


def seconds_per_beat(tempo):
    return Decimal(60) / Decimal(tempo)


@attr.s
class Position(object):
    measure = attr.ib(convert=int_to_zero_index)
    beat = attr.ib(convert=int_to_zero_index)
    division = attr.ib(convert=int_to_zero_index)
    tick = attr.ib(convert=strip_int_trailing_period)

    def to_timedelta(self, tempo, time_signature):
        return timedelta(
            microseconds=int(
                seconds_per_beat(tempo)
                * 1000000
                * (
                    (self.measure * time_signature.beats)
                    + (self.beat)
                    + (self.division * Decimal(1) / Decimal(time_signature.division))
                    + (self.tick * Decimal(1) / Decimal(TICKS_PER_BEAT))
                )
            )
        )


@attr.s
class Event(object):
    position = attr.ib(validator=attr.validators.instance_of(Position))


@attr.s
class EventLength(object):
    measures = attr.ib(convert=int)
    beats = attr.ib(convert=int)
    divisions = attr.ib(convert=int)
    ticks = attr.ib(convert=strip_int_trailing_period)


def to_timedelta(time_str):
    _, hours, minutes, seconds = time_str.split(':')
    seconds, dot, decimal_part = seconds.partition('.')
    return timedelta(
        hours=int(hours),
        minutes=int(minutes),
        seconds=int(seconds),
        microseconds=int(Decimal(dot + decimal_part) * 1000000)
    )


@attr.s
class TempoEvent(Event):
    tempo = attr.ib(convert=Decimal)
    time = attr.ib(convert=to_timedelta)

    @classmethod
    def from_string(cls, s):
        measure, beat, division, tick, rest = s.split(maxsplit=4)
        tempo, time = rest.split()
        return cls(Position(measure, beat, division, tick), tempo, time)


@attr.s
class TimeSignature(object):
    beats = attr.ib(convert=int)
    division = attr.ib(convert=int)


@attr.s
class TimeSignatureEvent(Event):
    time_signature = attr.ib(validator=attr.validators.instance_of(TimeSignature))

    @classmethod
    def from_string(cls, s):
        measure, beat, division, tick, rest = s.split(maxsplit=4)
        _, beats, _, divisions = rest.split()
        return cls(Position(measure, beat, division, tick),
                   TimeSignature(beats, divisions))

    @classmethod
    def validate(cls, data):
        return data.split()[4] == 'Time'


@attr.s
class NoteEvent(Event):
    title = attr.ib()
    track = attr.ib(convert=int)
    length = attr.ib(validator=attr.validators.instance_of(EventLength))

    @classmethod
    def from_string(cls, s):
        measure, beat, division, tick, rest = s.split(maxsplit=4)
        pos = Position(measure, beat, division, tick)
        title, track, rest = rest.split(maxsplit=2)
        measures, beats, divisions, ticks = rest.split(maxsplit=4)
        length = EventLength(measures, beats, divisions, ticks)
        return cls(pos, title, track, length)


def sections(stream):
    """
    Tag each line of the stream with its [section] (or None)
    """
    section_pattern = re.compile(r'\[(.*)\]')
    section = None
    for line in stream:
        matcher = section_pattern.match(line)
        if matcher:
            section = matcher.group(1)
            continue
        line = line.strip()
        if line:
            yield TaggedLine(line, section)


def splitter(stream):
    """
    Group each stream into sections
    """
    return itertools.groupby(sections(stream), operator.attrgetter('tag'))


def parsed_sections(stream):
    for section, lines in splitter(stream):
        yield section, lines


def section_order(args):
    section, _ = args
    return {
        'tempo': 1,
        'signatures': 2,
        'events': 3
    }[section]


def get_tempos(data):
    return [TempoEvent.from_string(row.line) for row in data]


def get_signatures(data):
    return [TimeSignatureEvent.from_string(row.line) for row in data
            if TimeSignatureEvent.validate(row.line)]


def get_events(data):
    return [NoteEvent.from_string(row.line) for row in data]


class EventStream(object):
    def __init__(self, tempos, signatures, events, default_tempo=120):
        self._stream = sorted(
            itertools.chain(tempos, signatures, events),
            key=operator.attrgetter('position')
        )
        self._curr_time = timedelta()
        self._curr_position = Position(1, 1, 1, 1)
        self._curr_tempo = Decimal(120)
        self._curr_signature = TimeSignature(4, 4)
        self._last_tempo_change = timedelta()

    def _compute_time(self, event):
        event_pos = event.position
        return (
            self._curr_time
            + event_pos.to_timedelta(self._curr_tempo, self._curr_signature)
            - self._curr_position.to_timedelta(self._curr_tempo, self._curr_signature)
        )

    def event_times(self):
        for item in self._stream:
            new_time = self._compute_time(item)
            if hasattr(item, 'tempo'):
                self._curr_tempo = item.tempo
                self._last_tempo_change = item.time
            elif hasattr(item, 'time_signature'):
                self._curr_signature = item.time_signature
            elif hasattr(item, 'length'):
                yield (new_time, item)
            self._curr_time = new_time
            self._curr_position = item.position


def text_with_break_type(text):
    if text and text[-1] in ELM_BREAK_TYPE_MAPPING:
        return (text[:-1], ELM_BREAK_TYPE_MAPPING[text[-1]])
    else:
        return (text, 'Word')


def print_lyrics_tree(event_list):
    for event in event_list:
        pass
        # store lyrics in page/line/lyric tree?
        # or flat with markers?


def write_elm_output(elm_filename, event_list):
    with io.open(elm_filename, 'w', encoding='utf-8') as elm_file:
        print(dedent("""
            module Lyrics exposing (..)

            import Array exposing (Array)
            import Time exposing (Time)


            type alias Lyric =
                { text : String
                , break : LyricBreak
                , time : Time
                }


            lyrics : Array Lyric
            lyrics =
                Array.fromList <|
        """).strip(), file=elm_file)
        print('        [ ', end='', file=elm_file)
        print('        , '.join(
            ['Lyric "{}" {} {}\n'.format(*text_with_break_type(evt['text']),
                                         evt['time'].total_seconds())
             for evt in event_list]
        ), end='', file=elm_file)
        print('        ]', file=elm_file)


def main():
    args = set_up_parser().parse_args()
    with open(args.cue_file) as stream:
        for section, data in parsed_sections(stream):
            if section == 'tempo':
                tempos = get_tempos(data)
            elif section == 'signatures':
                signatures = get_signatures(data)
            elif section == 'events':
                events = get_events(data)
            else:
                raise RuntimeError('Unknown section {}'.format(section))
    event_stream = EventStream(tempos, signatures, events)
    output_list = [{'text': event.title, 'time': time}
                   for time, event in event_stream.event_times()]
    if args.json:
        with io.open(args.json, 'w', encoding='utf-8') as json_file:
            json.dump(output_list, json_file, indent=4)
    if args.elm:
        write_elm_output(args.elm, output_list)


if __name__ == "__main__":
    sys.exit(main())
