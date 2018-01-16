from functools import partial
import io

from ..parsing.helpers import text_with_break_type, no_break, groupwhile


ELM_FILE_HEADER = """
module Lyrics exposing (..)

import Time exposing (Time)


type alias Lyric =
    {{ text : String
    , time : Time
    }}


type alias LyricLine =
    List Lyric


type alias LyricPage =
    List LyricLine


type alias LyricBook =
    List LyricPage


lyricBaseFontTTF : String
lyricBaseFontTTF =
    "{font_path}"


lyricBaseFontName : String
lyricBaseFontName =
    "{font_name}"


lyrics : LyricBook
lyrics =
"""


def print_lyrics_tree(event_list, out_file):
    lyric_template = '          Lyric "{text}" <| {time} * Time.second'
    print(
        '    [\n' +
        ',\n'.join([
            '      [\n' +
            ',\n'.join([
                '        [\n' +
                ',\n'.join([
                    lyric_template.format(
                        text=text_with_break_type(token['text']),
                        time=token['time'].total_seconds()
                    )
                    for token in line]) +
                '\n        ]'
                for line in groupwhile(partial(no_break, ['Line']), page)
            ]) +
            ' ]'
            for page in groupwhile(partial(no_break, ['Page']), event_list)
        ])
        + ' ]'
        , file=out_file
    )


def write_elm_output(elm_filename, event_list):
    with io.open(elm_filename, 'w', encoding='utf-8') as elm_file:
        print(ELM_FILE_HEADER.strip().format(
            font_path='static/fonts/leaguegothic/leaguegothic-regular-webfont.ttf',
            font_name='LeagueGothic',
        ), file=elm_file)
        print_lyrics_tree(iter(event_list), elm_file)
