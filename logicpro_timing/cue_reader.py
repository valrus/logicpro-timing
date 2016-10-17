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
    bar = attr.ib(convert=int)
    beat = attr.ib(convert=int)
    division = attr.ib(convert=int)
    tick = attr.ib(convert=strip_int_trailing_period)


@attr.s
class Tempo(object):
    position = attr.ib(validator=attr.validators.instance_of(Position))
    tempo = attr.ib(convert=float)
    time = attr.ib()

    @classmethod
    def from_string(cls, s):
        bar, beat, division, tick, rest = s.split(maxsplit=4)
        tempo, time = rest.split()
        return cls(Position(bar, beat, division, tick), tempo, time)


@attr.s
class Signature(object):
    position = attr.ib(validator=attr.validators.instance_of(Position))

    @classmethod
    def from_string(cls, s):
        bar, beat, division, tick, rest = s.split(maxsplit=4)


def set_up_parser():
    parser = ArgumentParser(description=__doc__,
                            formatter_class=ArgumentDefaultsHelpFormatter)
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
    return [Tempo(row) for row in data]


def get_signatures(date):
    return [Signature(row) for row in data]


def main():
    args = set_up_parser().parse_args()
    with open(args.cueFile) as stream:
        for section, data in sorted(parsed_sections(stream), key=section_order):
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
