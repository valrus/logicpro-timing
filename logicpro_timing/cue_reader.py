from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from collections import namedtuple

import itertools
import operator
import re
import sys

import attr


@attr.s
class TaggedLine(object):
    line = attr.ib()
    tag = attr.ib()


def strip_int_trailing_period(s):
    return int(s.rstrip('.'))


@attr.s
class Position(object):
    measure = attr.ib(convert=int)
    beat = attr.ib(convert=int)
    division = attr.ib(convert=int)
    tick = attr.ib(convert=strip_int_trailing_period)


@attr.s
class EventLength(object):
    measures = attr.ib(convert=int)
    beats = attr.ib(convert=int)
    divisions = attr.ib(convert=int)
    ticks = attr.ib(convert=strip_int_trailing_period)


@attr.s
class Tempo(object):
    position = attr.ib(validator=attr.validators.instance_of(Position))
    tempo = attr.ib(convert=float)
    time = attr.ib()

    @classmethod
    def from_string(cls, s):
        measure, beat, division, tick, rest = s.split(maxsplit=4)
        tempo, time = rest.split()
        return cls(Position(measure, beat, division, tick), tempo, time)


@attr.s
class TimeSignature(object):
    position = attr.ib(validator=attr.validators.instance_of(Position))
    signature = attr.ib()

    @classmethod
    def from_string(cls, s):
        measure, beat, division, tick, rest = s.split(maxsplit=4)
        _, beats, _, divisions = rest.split()
        return cls(Position(measure, beat, division, tick), (beats, divisions))

    @classmethod
    def validate(cls, data):
        return data.split()[4] == 'Time'


@attr.s
class Event(object):
    position = attr.ib(validator=attr.validators.instance_of(Position))
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


def set_up_parser():
    parser = ArgumentParser(description=__doc__,
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('cue_file')
    return parser


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
    return [Tempo.from_string(row.line) for row in data]


def get_signatures(data):
    return [TimeSignature.from_string(row.line) for row in data
            if TimeSignature.validate(row.line)]


def get_events(data):
    return [Event.from_string(row.line) for row in data]


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


if __name__ == "__main__":
    sys.exit(main())
