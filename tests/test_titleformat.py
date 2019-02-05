#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:ts=2:sw=2:et:ai

from euphonogenizer import titleformat
from euphonogenizer.common import unistr

from functools import reduce
from itertools import product

import sys
import pytest

cs_01 = {
      "@" : "01. This.flac",
      "ALBUM" : "See What You Started by Continuing (Deluxe Edition)",
      "ARTIST" : "Collective Soul",
      "COMMENT" : "Van-38004-02 Vanguard Records",
      "DATE" : "2015",
      "DISCNUMBER" : "1",
      "GENRE" : "Rock",
      "REPLAYGAIN_ALBUM_GAIN" : "-11.65 dB",
      "REPLAYGAIN_ALBUM_PEAK" : "1.000000",
      "REPLAYGAIN_TRACK_GAIN" : "-12.10 dB",
      "REPLAYGAIN_TRACK_PEAK" : "1.000000",
      "TITLE" : "This",
      "TOTALDISCS" : "2",
      "TOTALTRACKS" : "11",
      "TRACKNUMBER" : "01"
}

fake_track = {
    "FAKEDASH" : "-",
}

window_title_integration_fmt = (
    "[%artist% - ]%title%["
      + " '['["
         + "#$num(%tracknumber%, 0)"
         + "$if(%totaltracks%,[ of $num(%totaltracks%, 0)])"
      + "]"
    + "] on %album%[ '('%date%')']["
      + "$ifgreater(%totaldiscs%,1, "
        + "$if("
              + "$strcmp(%discnumber%,A)"
              + "$strcmp(%discnumber%,B)"
              + "$strcmp(%discnumber%,C)"
              + "$strcmp(%discnumber%,D),"
          + "'{'Side %discnumber%'}',"
          + "'{'Disc %discnumber% of %totaldiscs%"
            + "$if2( - %set subtitle%,)'}'"
        + ")"
      + ",)"
    + "]"
    + "$if($or(%tracknumber%,%totaltracks%),']')"
)

window_title_integration_expected = (
    'Collective Soul - This'
    + ' [#1 of 11 on See What You Started by Continuing'
    + ' (Deluxe Edition) (2015) {Disc 1 of 2}]'
)

f = titleformat.TitleFormatter()
fdbg = titleformat.TitleFormatter(debug=True)

def _tcid(prefix, testcase):
  suffix = '' if len(testcase) <= 4 or not testcase[4] else ':' + testcase[4]
  return "%s%s<'%s' = '%s'>" % (prefix, suffix, testcase[0], testcase[1])

def _testcasegroup(idprefix, *testcases):
  return [pytest.param(*x[:4], id=_tcid(idprefix, x))
          for x in testcases]

def _generatecases(idsuffix, fn, answers, *inputs):
  return [('$%s(%s)' % (fn, ','.join(x)), *answers(x), idsuffix)
          for x in product(*inputs)]

def resolve_var(v, track, missing='?', stripped=False):
  if '%' in v or stripped:
    if not stripped:
      v = v.strip('%')
    return track[v] if v in track else missing
  return v

def resolve_int_var(v, track, stripped=False):
  try:
    if stripped:
      return int(v)
    else:
      return int(v.rstrip(' abc').lstrip(' '))
  except ValueError:
    pass

  r = resolve_var(v, track, missing=0, stripped=stripped)

  try:
    return int(r)
  except ValueError:
    return 0

test_eval_cases = [
    # Basic parsing tests -- test various interesting parser states
    *_testcasegroup('parser:basic',
      ('', '', False, {}),
      (' ', ' ', False, {}),
      (',', ',', False, {}),
      ('(', '', False, {}),
      (')', '', False, {}),
      ('asdf1234', 'asdf1234', False, {}),
      ("''", "'", False, {}),
      ("''''", "''", False, {}),
      ('%%', '%', False, {}),
      ('%%%%', '%%', False, {}),
      ('[]', '', False, {}),
      ('[[]]', '', False, {}),
      ("['']", '', False, {}),
      ('[%]', '', False, {}),
      ('[%%]', '', False, {}),
      ("'['", '[', False, {}),
      ("']'", ']', False, {}),
      ("'[]'", '[]', False, {}),
      ("'['']'", '[]', False, {}),
      ('%[%', '?', False, {}),
      ('[%[%]]', '', False, {}),
      ('%]%', '?', False, {}),
    ),
    *_testcasegroup('parser:functions',
      ('$', '', False, {}),
      ("'$", '$', False, {}),
      ("'$'", '$', False, {}),
      ('$$', '$', False, {}),
      ('*$$*', '*$*', False, {}),
      ('*$$$*', '*$', False, {}),
      ('$()', '[UNKNOWN FUNCTION]', False, {}),
      ('*$*', '*', False, {}),
      ('*$(*', '*', False, {}),
      ('$([])', '[UNKNOWN FUNCTION]', False, {}),
      ('*$[a', '*', False, {}),
      ('*$[]a', '*', False, {}),
      ('*$[()]a', '*', False, {}),
      ('*()$add(1,2)', '*', False, {}),
      ('*$ad$if($add(),a,d)d(2)', '*', False, {}),
      ('*$if($ad$if($add(),a,d),yes,no)d(2)', '*nod', False, {}),
      ('*$if((),yes,no)*', '*no*', False, {}),
      ("*$if('()',yes,no)*", '*no*', False, {}),
      ('*$if((((what,ever))),yes(,)oof,no($)gmb)*', '*no*', False, {}),
      ('*$if((%artist%),yes(,)oof,no($)gmb)*', '*no*', False, cs_01),
      ('*$if(%artist%(%a,b%),yes(,)oof,no($)gmb)*', '*yes*', False, cs_01),
      ('*$if(%missing%(%a,b%),yes(,)oof,no($)gmb)*', '*no*', False, cs_01),
      ('*$if(,fail,add)(1,2)*', '*add', False, {}),
      ('$$&$$$$$$$add(1,2)$$$$$$&$$', '$&$$$3$$$&$', False, {}),
    ),
    # Variable resolution tests
    *_testcasegroup('variable',
      ('%artist% - ', 'Collective Soul - ', True, cs_01),
      ('[%artist% - ]', 'Collective Soul - ', True, cs_01),
      ('*[%missing% - ]*', '**', False, cs_01),
      ("'%artist%'", '%artist%', False, cs_01),
    ),
    # Bizarre variable resolution, yes this actually works in foobar
    *_testcasegroup('variable:arithmetic_magic',
      ('$add(1%track%,10)', '111', True, cs_01),
      ('$sub(1%track%,10)', '91', True, cs_01),
      ('$mul(1%track%,10)', '1010', True, cs_01),
      ('$div(1%track%,10)', '10', True, cs_01),
    ),
    # Sanity tests, basic non-generated cases that validate generated ones
    *_testcasegroup('sanity:arithmetic',
      ("$add('1234')", '1234', False, {}),
      ("$add(,,  '    1234    '  ,,)", '1234', False, {}),
      ('$add($div($mul($sub(100,1),2),10),2)', '21', False, {}),
    ),
    # Nested arithmetic: $add() and $sub() -- other arithmetic tests generated
    *_testcasegroup('arithmetic:nested',
      ('$add(1,$add(1,$add(1,$add(1))))', '4', False, {}),
      ('$add(1,$add(2,$add(3,$add(4))))', '10', False, {}),
      ('$add(-1,$add(-2,$add(-3,$add(-4))))', '-10', False, {}),
      # Foobar will negate a value returned to it by a function, but only if
      # it's positive. If it's negative, it will be treated as text (--).
      ("$add(-$add('1','2'),' 10')", '7', False, {}),
      # Foobar can't negate functions that return negative values.
      ('$add(-1,-$add(-2,-$add(-3)))', '-1', False, {}),
      # Same here, but it actually sums the first two.
      ('$add(-2,-6,-$add(-2,-$add(-3)))', '-8', False, {}),
      ('$add(-3,-$add(-2,-$add(-3)),-4)', '-7', False, {}),
      ('$add($add($add(1,$add(5))),$add(2,$add(3,4)))', '15', False, {}),
      ('$sub(1,$sub(1,$sub(1)))', '1', False, {}),
      ('$sub(1,$sub(1,$sub(1,$sub(1))))', '0', False, {}),
      ('$sub(1,$sub(2,$sub(3,$sub(4))))', '-2', False, {}),
      ('$sub(-1,$sub(-2,$sub(-3,$sub(-4))))', '2', False, {}),
      ("$sub(-$sub('2','1'),'10')",'-11', False, {}),
      # Foobar still can't negate functions that return negative values.
      ('$sub(-1,-$sub(-2,-$sub(-3)))', '-1', False, {}),
      # Same here, but it actually subtracts for the first two.
      ('$sub(-2,-6,-$sub(-2,-$sub(-3)))', '4', False, {}),
      ('$sub(-3,-$sub(-2,-$sub(-3)),-4)', '1', False, {}),
      ('$sub($sub($sub(1,$sub(5))),$sub(2,$sub(3,4)))', '-7', False, {}),
    ),
    # NOTE: This function is weird. Any valid call is True, according to Foobar.
    *_testcasegroup('arithmetic:muldiv',
      ('$muldiv()!a$muldiv()', '!a', False, {}),
      ('$muldiv(123)', '', False, {}),
      ('$muldiv(-456)', '', False, {}),
      ('$muldiv(-)', '', False, {}),
      ('$muldiv(0)', '', False, {}),
      ('$muldiv(-0)', '', False, {}),
      ('$muldiv(1000, 10)', '', False, {}),
      ('$muldiv(,)', '', False, {}),
      ('$muldiv(-,)', '', False, {}),
      ('$muldiv(,-)', '', False, {}),
      ('$muldiv(-,-)', '', False, {}),
      ('$muldiv(-1,-)', '', False, {}),
      ('$muldiv(0, 123)', '', False, {}),
      ('$muldiv(1, 0)', '', False, {}),
      ('$muldiv(0, 0)', '', False, {}),
      ('$muldiv(-10, 3)', '', False, {}),
      ('$muldiv(10, -3)', '', False, {}),
      ('$muldiv(-10, -3)', '', False, {}),
      ('$muldiv(128,2,2)', '128', True, {}),
      ('$muldiv(,,)', '-1', True, {}),
      ('$muldiv(-,-,-)', '-1', True, {}),
      ('$muldiv(5,3,1)', '15', True, {}),
      ('$muldiv(-5,3,1)', '-15', True, {}),
      ('$muldiv(5,-3,1)', '-15', True, {}),
      ('$muldiv(-5,-3,1)', '15', True, {}),
      # Test rounding down behavior
      ('$muldiv(5,3,2)', '7', True, {}),
      ('$muldiv(-5,3,2)', '-7', True, {}),
      ('$muldiv(5,-3,2)', '-7', True, {}),
      ('$muldiv(-5,-3,2)', '7', True, {}),
      ('$muldiv(5,2,3)', '3', True, {}),
      ('$muldiv(-5,2,3)', '-3', True, {}),
      ('$muldiv(5,-2,3)', '-3', True, {}),
      ('$muldiv(-5,-2,3)', '3', True, {}),
      ('$muldiv(5,7,8)', '4', True, {}),
      ('$muldiv(-5,7,8)', '-4', True, {}),
      ('$muldiv(5,-7,8)', '-4', True, {}),
      ('$muldiv(-5,-7,8)', '4', True, {}),
      ('$muldiv(5,3,-1)', '-15', True, {}),
      ('$muldiv(-5,3,-1)', '15', True, {}),
      ('$muldiv(5,-3,-1)', '15', True, {}),
      ('$muldiv(-5,-3,-1)', '-15', True, {}),
      ('$muldiv(5,3,-2)', '-7', True, {}),
      ('$muldiv(-5,3,-2)', '7', True, {}),
      ('$muldiv(5,-3,-2)', '7', True, {}),
      ('$muldiv(-5,-3,-2)', '-7', True, {}),
      ('$muldiv(5,2,-3)', '-3', True, {}),
      ('$muldiv(-5,2,-3)', '3', True, {}),
      ('$muldiv(5,-2,-3)', '3', True, {}),
      ('$muldiv(-5,-2,-3)', '-3', True, {}),
      ('$muldiv(5,7,-8)', '-4', True, {}),
      ('$muldiv(-5,7,-8)', '4', True, {}),
      ('$muldiv(5,-7,-8)', '4', True, {}),
      ('$muldiv(-5,-7,-8)', '-4', True, {}),
      ('$muldiv(128,0,3)', '0', True, {}),
      # WTF. This is actual Foobar behavior. It's obviously a bug but... HOW?
      ('$muldiv(128,5,0)', '-1', True, {}),
      ('$muldiv(6969,0,-0)', '-1', True, {}),
      ('$muldiv(,,,)', '', False, {}),
      ('$muldiv(1,1,1,1)', '', False, {}),
      ('$muldiv(%artist%,%artist%,%artist%)', '-1', True, cs_01),
      ('$muldiv(%date%,%totaldiscs%,%totaltracks%)', '366', True, cs_01),
      ('$muldiv(%no%,%nope%,%still no%)', '-1', True, cs_01),
    ),
    # Arithmetic: $greater()
    *_testcasegroup('arithmetic:greater',
      ('$greater()', '', False, {}),
      ('$greater(0)', '', False, {}),
      ('$greater(-)', '', False, {}),
      ('$greater(,)', '', False, {}),
      ('$greater(0,)', '', False, {}),
      ('$greater(,0)', '', False, {}),
      ('$greater(,-0)', '', False, {}),
      ('$greater(1,)', '', True, {}),
      ('$greater(,1)', '', False, {}),
      ('$greater(2,1)', '', True, {}),
      ('$greater(2,t)', '', True, {}),
      ('$greater(,,)', '', False, {}),
      ('$greater(2,,)', '', False, {}),
      ('$greater(2,1,)', '', False, {}),
      ('$greater(2,1,0)', '', False, {}),
      ('$greater(,-1)', '', True, {}),
      ('$greater(-1,-2)', '', True, {}),
      ('$greater(%totaltracks%,-1)', '', True, cs_01),
      ('$greater(-1,%totaltracks%)', '', False, cs_01),
      ('$greater(%totaltracks%,%totaltracks%)', '', False, cs_01),
      ('$greater($add(%totaltracks%,1),%totaltracks%)', '', True, cs_01),
      ('$greater(%totaltracks%,$add(%totaltracks%,1))', '', False, cs_01),
      ('$greater($add(1,%track%),$add(%track%,1))', '', False, cs_01),
    ),
    # Arithmetic: $max() and $min -- the rest are autogenerated
    pytest.param('$max()', '', False, {}, id='max_arity0'),
    pytest.param('$min()', '', False, {}, id='min_arity0'),
    *_testcasegroup('control_flow',
      # $if()
      ('*$if()*', '*[INVALID $IF SYNTAX]*', False, {}),
      ('*$if($add())*', '*[INVALID $IF SYNTAX]*', False, {}),
      ('*$if(%artist%)*', '*[INVALID $IF SYNTAX]*', False, cs_01),
      ('*$if(%missing%)*', '*[INVALID $IF SYNTAX]*', False, cs_01),
      ('*$if(,)*', '**', False, {}),
      ('*$if($add(),)*', '**', False, {}),
      ('*$if($add(),,)*', '**', False, {}),
      ('*$if($add(),yes)*', '**', False, {}),
      ('*$if($add(),yes,)*', '**', False, {}),
      ('*$if($add(),yes,no)*', '*no*', False, {}),
      ('*$if(%artist%,)*', '**', False, cs_01),
      ('*$if(%artist%,,)*', '**', False, cs_01),
      ('*$if(%artist%,yes)*', '*yes*', False, cs_01),
      ('*$if(%artist%,yes,)*', '*yes*', False, cs_01),
      ('*$if(%artist%,yes,no)*', '*yes*', False, cs_01),
      ('*$if($add(),%artist%)*', '**', False, cs_01),
      ('*$if(%tracknumber%,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if(%missing%,%artist%)*', '**', False, cs_01),
      ('*$if($add(),%artist%,)*', '**', False, cs_01),
      ('*$if($add(),,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if(%tracknumber%,%artist%,)*', '*Collective Soul*', True, cs_01),
      ('*$if(%tracknumber%,,%artist%)*', '**', False, cs_01),
      ('*$if(%artist%,%artist%,%track%)*', '*Collective Soul*', True, cs_01),
      ('*$if(%missing%,%artist%,%track%)*', '*01*', True, cs_01),
      ('*$if(,,)*', '**', False, {}),
      ('*$if(,yes,no)*', '*no*', False, {}),
      ('*$if($if($add()),yes,no)*', '*no*', False, {}),
      ('*$if($if(%artist%),yes,no)*', '*no*', False, cs_01),
      ('*$if(a,b,c,d)*', '*[INVALID $IF SYNTAX]*', False, {}),
      # $if2()
      ('*$if2()*', '*[INVALID $IF2 SYNTAX]*', False, {}),
      ('*$if2(a)*', '*[INVALID $IF2 SYNTAX]*', False, {}),
      ('*$if2(%artist%)*', '*[INVALID $IF2 SYNTAX]*', False, cs_01),
      ('*$if2(%missing%)*', '*[INVALID $IF2 SYNTAX]*', False, cs_01),
      ('*$if2(,)*', '**', False, {}),
      ('*$if2(,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if2(text,no)*', '*no*', False, {}),
      ('*$if2(%artist%,no)*', '*Collective Soul*', True, cs_01),
      ('*$if2(%missing%,no)*', '*no*', False, cs_01),
      ('*$if2(text,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if2(%track%,%artist%)*', '*01*', True, cs_01),
      ('*$if2(%missing%,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if2($if2(%artist%,no),nope)*', '*Collective Soul*', True, cs_01),
      ('*$if2(a,b,c)*', '*[INVALID $IF2 SYNTAX]*', False, {}),
      # $if3()
      ('*$if3()*', '**', False, {}),
      ('*$if3(a)*', '**', False, {}),
      ('*$if3(%artist%)*', '**', False, cs_01),
      ('*$if3(%missing%)*', '**', False, cs_01),
      ('*$if3(,)*', '**', False, {}),
      ('*$if3(a,no)*', '*no*', False, {}),
      ('*$if3(%artist%,no)*', '*Collective Soul*', True, cs_01),
      ('*$if3(%artist%,%missing%)*', '*Collective Soul*', True, cs_01),
      ('*$if3(%artist%,%track%)*', '*Collective Soul*', True, cs_01),
      ('*$if3(no,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if3(no,%missing%)*', '*?*', False, cs_01),
      ('*$if3(%missing%,no)*', '*no*', False, cs_01),
      ('*$if3(%missing1%,%missing2%)*', '*?*', False, cs_01),
      ('*$if3(,,)*', '**', False, {}),
      ('*$if3(,,no)*', '*no*', False, {}),
      ('*$if3(%artist%,no,still no)*', '*Collective Soul*', True, cs_01),
      ('*$if3(no,%artist%,still no)*', '*Collective Soul*', True, cs_01),
      ('*$if3(no,still no,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if3(%missing%,no,still no)*', '*still no*', False, cs_01),
      ('*$if3(no,%missing%,still no)*', '*still no*', False, cs_01),
      ('*$if3(no,still no,%missing%)*', '*?*', False, cs_01),
      ('*$if3(wow,no,%artist%,%missing%)*', '*Collective Soul*', True, cs_01),
      ('*$if3(wow,no,%missing%,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$if3(a,b,%missing%,d,e)*', '*e*', False, cs_01),
      # $ifequal()
      ('*$ifequal()*', '*[INVALID $IFEQUAL SYNTAX]*', False, {}),
      ('*$ifequal(a)*', '*[INVALID $IFEQUAL SYNTAX]*', False, {}),
      ('*$ifequal(,)*', '*[INVALID $IFEQUAL SYNTAX]*', False, {}),
      ('*$ifequal(,,)*', '*[INVALID $IFEQUAL SYNTAX]*', False, {}),
      ('*$ifequal(,,,)*', '**', False, {}),
      ('*$ifequal(,,,,)*', '*[INVALID $IFEQUAL SYNTAX]*', False, {}),
      ('*$ifequal(,,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(0,,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(,0,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(0,0,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(-0,0,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(0,-0,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(zero,one,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(0,1,yes,no)*', '*no*', False, {}),
      ('*$ifequal(1,1,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(1,0,yes,no)*', '*no*', False, {}),
      ('*$ifequal(-1,1,yes,no)*', '*no*', False, {}),
      ('*$ifequal(1,-1,yes,no)*', '*no*', False, {}),
      ('*$ifequal(-1,-1,yes,no)*', '*yes*', False, {}),
      ('*$ifequal(2,2,%track%,no)*', '*01*', True, cs_01),
      ('*$ifequal(2,2,%track%,%missing%)*', '*01*', True, cs_01),
      ('*$ifequal(2,2,no,%track%)*', '*no*', False, cs_01),
      ('*$ifequal(2,2,%missing%,%track%)*', '*?*', False, cs_01),
      ('*$ifequal(123 a,-123 a,no,%track%)*', '*01*', True, cs_01),
      ('*$ifequal(123 a,-123 a,no,%missing%)*', '*?*', False, cs_01),
      ('*$ifequal(%artist%,0,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(%track%,0,yes,no)*', '*no*', False, cs_01),
      ('*$ifequal(%missing%,0,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(0,%artist%,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(0,%track%,yes,no)*', '*no*', False, cs_01),
      ('*$ifequal(0,%missing%,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(%artist%,%artist%,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(%track%,%track%,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(%missing%,%missing%,yes,no)*', '*yes*', False, cs_01),
      ('*$ifequal(%artist%,0,%track%,no)*', '*01*', True, cs_01),
      ('*$ifequal(%track%,0,yes,%artist%)*', '*Collective Soul*', True, cs_01),
      ('*$ifequal(%missing%,0,%track%,no)*', '*01*', True, cs_01),
      ('*$ifequal(0,%artist%,%missing%,%track%)*', '*?*', False, cs_01),
      ('*$ifequal(0,%track%,%artist%,%missing%)*', '*?*', False, cs_01),
      ('*$ifequal(0,%missing%,yes,%missing%)*', '*yes*', False, cs_01),
      ('*$ifequal(%artist%,-1%artist%,yes,%missing%)*', '*?*', False, cs_01),
      ('*$ifequal(%track%,-1%track%,yes,%track%)*', '*01*', True, cs_01),
      ('*$ifequal(%missing%,-1%missing%,yes,%track%)*', '*01*', True, cs_01),
      # $ifgreater()
      ('*$ifgreater()*', '*[INVALID $IFGREATER SYNTAX]*', False, {}),
      ('*$ifgreater(a)*', '*[INVALID $IFGREATER SYNTAX]*', False, {}),
      ('*$ifgreater(,)*', '*[INVALID $IFGREATER SYNTAX]*', False, {}),
      ('*$ifgreater(,,)*', '*[INVALID $IFGREATER SYNTAX]*', False, {}),
      ('*$ifgreater(,,,)*', '**', False, {}),
      ('*$ifgreater(,,,,)*', '*[INVALID $IFGREATER SYNTAX]*', False, {}),
      ('*$ifgreater(,,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(0,,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(,0,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(0,0,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(-0,0,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(0,-0,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(zero,one,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(0,1,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(1,1,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(1,0,yes,no)*', '*yes*', False, {}),
      ('*$ifgreater(-1,1,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(1,-1,yes,no)*', '*yes*', False, {}),
      ('*$ifgreater(-1,-1,yes,no)*', '*no*', False, {}),
      ('*$ifgreater(2,2,%track%,no)*', '*no*', False, cs_01),
      ('*$ifgreater(2,2,%track%,%missing%)*', '*?*', False, cs_01),
      ('*$ifgreater(2,2,no,%track%)*', '*01*', True, cs_01),
      ('*$ifgreater(2,2,%missing%,%track%)*', '*01*', True, cs_01),
      ('*$ifgreater(123 a,-123 a,%track%,no)*', '*01*', True, cs_01),
      ('*$ifgreater(123 a,-123 a,%missing%,no)*', '*?*', False, cs_01),
      ('*$ifgreater(%artist%,0,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(%track%,0,yes,no)*', '*yes*', False, cs_01),
      ('*$ifgreater(%missing%,0,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(0,%artist%,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(0,%track%,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(0,%missing%,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(%artist%,%artist%,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(%track%,%track%,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(%missing%,%missing%,yes,no)*', '*no*', False, cs_01),
      ('*$ifgreater(%artist%,0,%track%,no)*', '*no*', False, cs_01),
      ('*$ifgreater(%track%,0,%artist%,no)*', '*Collective Soul*', True, cs_01),
      ('*$ifgreater(%missing%,0,no,%track%)*', '*01*', True, cs_01),
      ('*$ifgreater(0,%artist%,%missing%,%track%)*', '*01*', True, cs_01),
      ('*$ifgreater(0,%track%,%artist%,%missing%)*', '*?*', False, cs_01),
      ('*$ifgreater(0,%missing%,yes,%missing%)*', '*?*', False, cs_01),
      ('*$ifgreater(%artist%,-1%artist%,%missing%,no)*', '*?*', False, cs_01),
      ('*$ifgreater(%track%,-1%track%,%track%,no)*', '*01*', True, cs_01),
      ('*$ifgreater(%missing%,-1%missing%,%track%,no)*', '*01*', True, cs_01),
      # $iflonger()
      ('*$iflonger()*', '*[INVALID $IFLONGER SYNTAX]*', False, {}),
      ('*$iflonger(a)*', '*[INVALID $IFLONGER SYNTAX]*', False, {}),
      ('*$iflonger(,)*', '*[INVALID $IFLONGER SYNTAX]*', False, {}),
      ('*$iflonger(,,)*', '*[INVALID $IFLONGER SYNTAX]*', False, {}),
      ('*$iflonger(,,,)*', '**', False, {}),
      ('*$iflonger(,,,,)*', '*[INVALID $IFLONGER SYNTAX]*', False, {}),
      *_generatecases('generated', 'iflonger',
        lambda x: (
          resolve_var(x[2], cs_01)
            if len(resolve_var(x[0], cs_01)) > resolve_int_var(x[1], cs_01)
            else resolve_var(x[3], cs_01),
          len(resolve_var(x[0], cs_01)) > resolve_int_var(x[1], cs_01)
            and 'A' in x[2]  # Bit of a hack here to avoid %MISSING% = True
            or len(resolve_var(x[0], cs_01)) <= resolve_int_var(x[1], cs_01)
            and 'A' in x[3],
          cs_01),
        ('', '0', '00', '-0', '1', '-1', '2', 'zero', 'one', '123 a', '-123 a',
          ' ', ' ' * 2, ' ' * 3, '%TRACKNUMBER%', '%ARTIST%', '%MISSING%'),
        ('', '0', '-0', '1', '-1', '2', 'zero', 'one', ' 123 a', ' -123 a',
          '%TRACKNUMBER%', '%ARTIST%', '%MISSING%'),
        ('yes', '%TRACKNUMBER%', '%ARTIST%', '%MISSING%'),
        ('no', '%TRACKNUMBER%', '%ARTIST%', '%MISSING%'),
      ),
      # $select()
      ('*$select()*', '**', False, {}),
      ('*$select(a)*' ,'**', False, {}),
      *_generatecases('generated:arity2', 'select',
        lambda x: (
          resolve_var(x[1], cs_01)
            if resolve_int_var(x[0], cs_01) == 1 else '',
          resolve_int_var(x[0], cs_01) == 1 and 'A' in x[1],
          cs_01),
        ('', 'a', '0', '1', '2', '3', '-1', '-2',
          '%ARTIST%', '%TRACKNUMBER%', '%missing%'),
        ('', 'a', '123', '%ARTIST%', '%TRACKNUMBER%', '%missing%'),
      ),
      *_generatecases('generated:arity3', 'select',
        lambda x: (
          *(lambda i=resolve_int_var(x[0], cs_01):
              (
                (resolve_var(x[1], cs_01), resolve_var(x[2], cs_01))[i - 1]
                  if i > 0 and i <= 2 else '',
                i > 0 and i <= 2 and 'A' in x[i],
              )
            )(),
          cs_01),
        ('', 'a', '0', '1', '2', '3', '-1', '-2', '-3',
          '%ARTIST%', '%TRACKNUMBER%', '%TOTALDISCS%', '%missing%'),
        ('', 'a', '123', '%ARTIST%', '%TRACKNUMBER%', '%missing%'),
        ('', 'b', '-456', '%ARTIST%', '%TRACKNUMBER%', '%missing%'),
      ),
      *_generatecases('generated:arity4', 'select',
        lambda x: (
          *(lambda i=resolve_int_var(x[0], cs_01):
              (
                (
                  resolve_var(x[1], cs_01),
                  resolve_var(x[2], cs_01),
                  resolve_var(x[3], cs_01),
                )[i - 1]
                  if i > 0 and i <= 3 else '',
                i > 0 and i <= 3 and 'A' in x[i],
              )
            )(),
          cs_01),
        ('', 'a', '0', '1', '2', '3', '-1', '-4',
          '%ARTIST%', '%TOTALDISCS%', '%missing%'),
        ('', 'a', '%ARTIST%', '%missing%'),
        ('', 'b', '%TRACKNUMBER%', '%missing%'),
        ('', 'c', '%DATE%', '%missing%'),
      ),
    ),
    *_testcasegroup('strings',
      # $abbr()
      ('$abbr()', '', False, {}),
      ('$abbr(,)', '', False, {}),
      ('$abbr(,,)', '', False, {}),
      ('$abbr(,,,)', '', False, {}),
      ("$abbr('')", "'", False, {}),
      ("$abbr(' ')", '', False, {}),
      ("$abbr(''a)", "'", False, {}),
      ("$abbr('a'b)", 'a', False, {}),
      ('$abbr(/a)', 'a', False, {}),  # Why does fb2k do this??
      ('$abbr(\\a)', 'a', False, {}),
      ("$abbr(','a)", 'a', False, {}),
      ('$abbr(¿a)', '¿', False, {}),
      ("$abbr('['a)", '[a', False, {}),
      ("$abbr(']'a)", ']a', False, {}),
      ("$abbr(a'[')", 'a', False, {}),
      ("$abbr(a']')", 'a', False, {}),
      ("$abbr('[]'a'[')", '[]a[', False, {}),
      ("$abbr('a(b)c')", 'abc', False, {}),
      ("$abbr('a/b/c')", 'abc', False, {}),
      ("$abbr('a\\b\\c')", 'abc', False, {}),
      ("$abbr('a,b,c')", 'abc', False, {}),
      ("$abbr('a.b.c')", 'a', False, {}),
      ('$abbr(-1234 5678)', '-5678', False, {}),
      ("$abbr('[a(b[c]d)e]')", '[abe', False, {}),
      ("$abbr('[ab/cd/ef[gh]')", '[abce', False, {}),
      ("$abbr('/a \\b [c ]d (e )f (g(h )i)j [k(l/m]n ]o/p)q]r -123')",
        'ab[c]defghij[klm]opq-', False, {}),
      ("$abbr('[a(b[c'%artist%')')", '[abS', True, cs_01),
      ('$abbr(%missing%a)', '?', False, {}),
      ('$abbr(%artist%)', 'CS', True, cs_01),
      ("$abbr('%artist%')", '%', False, cs_01),
      ('$abbr([%artist%])', 'CS', True, cs_01),
      ("$abbr(%date%)", '2015', True, cs_01),
      ("$abbr('ああ')", 'あ', False, {}),
      # Unfortunately fb2k doesn't understand other Unicode spaces
      ("$abbr('。あ　亜。')", '。', False, {}),
      ('$abbr(!abc)', '!', False, {}),
      ('$abbr(Memoirs of 2005)', 'Mo2005', False, {}),
      ('$abbr(Memoirs of 2005a)', 'Mo2', False, {}),
      # Examples from documentation
      ("$abbr('This is a Long Title (12-inch version) [needs tags]')",
        'TiaLT1v[needst', False, {}),
      # NOTE: There are more encoding tests for $ansi() and $ascii() later.
      # $ansi()
      ('$ansi()', '', False, {}),
      ('$ansi( a )', ' a ', False, {}),
      ('$ansi(%artist%)', 'Collective Soul', True, cs_01),
      ('$ansi(2814 - 新しい日の誕生)', '2814 - ???????', False, {}),
      ('$ansi(a,b)', '', False, {}),
      # $ascii
      ('$ascii()', '', False, {}),
      ('$ascii( a )', ' a ', False, {}),
      ('$ascii(%artist%)', 'Collective Soul', True, cs_01),
      ('$ascii(2814 - 新しい日の誕生)', '2814 - ???????', False, {}),
      ('$ascii(a,b)', '', False, {}),
      # $caps
      ('$caps()', '', False, {}),
      ('$caps(a)', 'A', False, {}),
      ('$caps(á)', 'Á', False, {}),
      ('$caps(a c a b)', 'A C A B', False, {}),
      ("$caps('ŭaŭ, la ĥoraĉo eĥadas en ĉi tiu preĝejo')",
        'Ŭaŭ, La Ĥoraĉo Eĥadas En Ĉi Tiu Preĝejo', False, {}),
      ("$caps('ŬAŬ, LA ĤORAĈO EĤADAS EN ĈI TIU PREĜEJO')",
        'Ŭaŭ, La Ĥoraĉo Eĥadas En Ĉi Tiu Preĝejo', False, {}),
      ('$caps(У Сашки в карма́шке ши́шки да ша́шки)',
        'У Сашки В Карма́шке Ши́шки Да Ша́шки', False, {}),
      ('$caps(У САШКИ В КАРМА́ШКЕ ШИ́ШКИ ДА ША́ШКИ)',
        'У Сашки В Карма́шке Ши́шки Да Ша́шки', False, {}),
      ('$caps(Μιὰ πάπια μὰ ποιά πάπια;)',
        'Μιὰ Πάπια Μὰ Ποιά Πάπια;', False, {}),
      ('$caps(ΜΙᾺ ΠΆΠΙΑ ΜᾺ ΠΟΙΆ ΠΆΠΙΑ;)',
        'Μιὰ Πάπια Μὰ Ποιά Πάπια;', False, {}),
      ('$caps(%artist%)', 'Collective Soul', True, cs_01),
      ('$caps(%artist%, b)', '', False, cs_01),
      # $caps2
      ('$caps2()', '', False, {}),
      ('$caps2(a)', 'A', False, {}),
      ('$caps2(á)', 'Á', False, {}),
      ('$caps2(a c a b)', 'A C A B', False, {}),
      ("$caps2('ŭaŭ, la ĥoraĉo eĥadas en ĉi tiu preĝejo')",
        'Ŭaŭ, La Ĥoraĉo Eĥadas En Ĉi Tiu Preĝejo', False, {}),
      ("$caps2('ŬAŬ, LA ĤORAĈO EĤADAS EN ĈI TIU PREĜEJO')",
        'ŬAŬ, LA ĤORAĈO EĤADAS EN ĈI TIU PREĜEJO', False, {}),
      ('$caps2(У Сашки в карма́шке ши́шки да ша́шки)',
        'У Сашки В Карма́шке Ши́шки Да Ша́шки', False, {}),
      ('$caps2(У САШКИ В КАРМА́ШКЕ ШИ́ШКИ ДА ША́ШКИ)',
        'У САШКИ В КАРМА́ШКЕ ШИ́ШКИ ДА ША́ШКИ', False, {}),
      ('$caps2(Μιὰ πάπια μὰ ποιά πάπια;)',
        'Μιὰ Πάπια Μὰ Ποιά Πάπια;', False, {}),
      ('$caps2(ΜΙᾺ ΠΆΠΙΑ ΜᾺ ΠΟΙΆ ΠΆΠΙΑ;)',
        'ΜΙᾺ ΠΆΠΙΑ ΜᾺ ΠΟΙΆ ΠΆΠΙΑ;', False, {}),
      ('$caps2(%artist%)', 'Collective Soul', True, cs_01),
      ('$caps2(%artist%, b)', '', False, cs_01),
      # $char
      ('$char()', '', False, {}),
      ('$char(0)', '', False, {}),
      ('$char(-1)', '', False, {}),
      ('$char(208)$char(111)$char(103)$char(101)', 'Ðoge', False, {}),
      ('$char(20811)', '克', False, {}),
      ('$char(1048575)', '󿿿', False, {}),
      ('$char(1048576)', '?', False, {}),
      ('$char(asdf)', '', False, {}),
      ('$char(%totaltracks%)', '', False, cs_01),
      ('$char(a,b)', '', False, {}),
      # $crc32
      ('$crc32()', '', False, {}),
      ('$crc32( )', '3916222277', False, {}),
      ('$crc32(abc)', '891568578', False, {}),
      ('$crc32(%totaltracks%)', '3596227959', True, cs_01),
      ("$crc32('')", '1997036262', False, {}),
      ('$crc32(a b c)', '3358461392', False, {}),
      ('$crc32(1,%totaltracks%)', '', False, cs_01),
      ("$crc32(G#1cW)$crc32('J]GAD')$crc32(in0W=)$crc32('eAe%Y')"
          "$crc32(6Nc6p)$crc32('9]rkV')$crc32('7Rm[j')", '0234568', False, {}),
      # TODO: $crlf, $cut
      # $directory
      ('$directory()', '', False, {}),
      ('$directory( )', '', False, {}),
      ('$directory(\\ \\)', ' ', False, {}),
      ('$directory(\\\\server\\dir\\file.fil)', 'dir', False, {}),
      ('$directory(/local/home/user/file.tar.xz)', 'user', False, {}),
      ('$directory(a|b|c)', 'b', False, cs_01),
      ('$directory(c:\\a|b|c|d, 3)', 'a', False, {}),
      ('$directory(/a/b/)', 'b', False, {}),
      ('$directory(/a/b/, 2)', 'a', False, {}),
      ('$directory(/a/b/, 3)', '', False, {}),
      ('$directory(/a/b/, 4)', '', False, {}),
      ('$directory(||||)', '', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\file.txt)',
          'Text Files', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\%totaltracks%.txt)',
          'Text Files', True, cs_01),
      ('$directory(C:\\My Documents\\Text Files\\%missing%.txt)',
          'Text Files', False, cs_01),
      ('$directory(C:\\My Documents\\%totaltracks%\\file.txt)',
          '11', True, cs_01),
      ('$directory(C:\\My Documents\\%totaltracks%\\file.txt, 2)',
          'My Documents', True, cs_01),
      ('$directory(C:\\My Documents\\Text Files\\file.txt, 0)', '', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\file.txt, 1)',
          'Text Files', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\file.txt, 2)',
          'My Documents', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\file.txt, 3)', '', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\file.txt, 4)', 'C', False, {}),
      ('$directory(C:\\My Documents\\Text Files\\file.txt, -1)', '', False, {}),
      ('$directory(a,b,c)', '', False, {}),
    ),
    # Real-world use-cases; integration tests
    pytest.param(
        window_title_integration_fmt, window_title_integration_expected, True,
        cs_01, id='window_title_integration'),
]


def __div_logic(x, y):
  if y == 0: return x
  if x == 0: return 0
  if x * y < 0:
    return x * -1 // y * -1
  return x // y

def div_logic(x, y):
  r = __div_logic(x, y)
  return r

def __mod_logic(x, y):
  if y == 0: return x
  return x % y

def mod_logic(x, y):
  r = __mod_logic(x, y)
  return r


arithmetic_resolutions = {
    'add': {'arity0': ('0', False), 'answer': lambda x, y: x + y},
    'sub': {'arity0': ('', False) , 'answer': lambda x, y: x - y},
    'mul': {'arity0': ('1', False), 'answer': lambda x, y: x * y},
    'div': {'arity0': ('', False) , 'answer': div_logic},
    'mod': {'arity0': ('', False) , 'answer': mod_logic},
}

boolean_resolutions = {
    'and': {'arity0': ('', True),   'answer': lambda x, y: x and y},
    'or':  {'arity0': ('', False),  'answer': lambda x, y: x or y},
    'not': {'arity0': ('', False),  'answer': lambda x: not x},
    'xor': {'arity0': ('', False),  'answer': lambda x, y: x ^ y},
}

for key in arithmetic_resolutions:
  arithmetic_resolutions[key]['group'] = 'arithmetic'

for key in boolean_resolutions:
  boolean_resolutions[key]['group'] = 'boolean'

expected_resolutions = arithmetic_resolutions.copy()
expected_resolutions.update(boolean_resolutions)


# Generate arithmetic and boolean tests
def generate_tests():
  generated_cases = []
  stripchars = "% -!abc',"
  for fn in expected_resolutions.keys():
    group = expected_resolutions[fn]['group']

    # Arity 0 tests
    fmt = '$%s()' % fn
    expected = expected_resolutions[fn]['arity0'][0]
    expected_truth = expected_resolutions[fn]['arity0'][1]
    generated_cases.append(pytest.param(
        fmt, expected, expected_truth, {},
        id="%s:arity0<%s = '%s'>" % (group, fmt, expected)))

    fmt = '$%s()!a$%s()' % (fn, fn)
    expected = '%s!a%s' % (expected, expected)
    generated_cases.append(pytest.param(
        fmt, expected, expected_truth, {},
        id="%s:arity0<$%s() = '%s'>" % (group, fn, expected)))

    answer = expected_resolutions[fn]['answer']

    # Arity 1 tests
    for testarg in (
        '123', '-456', '-', '0', '-0', '007', '-007', '?',
        '%TOTALDISCS%', '%TRACKNUMBER%', '%ARTIST%', '%MISSING%',
    ):
      fmt = '$%s(%s)' % (fn, testarg)

      if group == 'arithmetic':
        expected = unistr(resolve_int_var(testarg, cs_01))
        try:
          expected = unistr(int(expected))
        except ValueError:
          expected = '0'
      elif group == 'boolean':
        expected = ''

      testarg_stripped = testarg.strip('%')
      expected_truth = testarg_stripped in cs_01

      try:
        # If there's an arity 1 answer, use it.
        expected_truth = answer(expected_truth)
      except TypeError:
        pass

      generated_cases.append(pytest.param(
          fmt, expected, expected_truth, cs_01,
          id="%s:arity1<%s = '%s'>" % (group, fmt, expected)))

      if testarg[0] == '%' and group == 'arithmetic':
        # Attempts to negate a variable resolution actually work somehow!
        fmt = '$%s(-%s)' % (fn, testarg)
        expected = unistr(int(expected) * -1)
        generated_cases.append(pytest.param(
            fmt, expected, testarg_stripped in cs_01, cs_01,
            id="%s:arity1<%s = '%s'>" % (group, fmt, expected)))

    # Arity 2 tests
    for t1, t2 in (
        (12, 34), (70, 20), (1000, 10), (10, 3), (-10, 3), (10, -3), (-10, -3),
        (123, 0), (0, 123), (0, 0), (0, 10), (10, 0), (100, 0), (0, 100),
        (1, 1), (1, 10), (10, 1), (1, 100), (100, 1), (-1, 1), (1, -1),
        (-1, -1), (-1, 100), (1, -100), (-100, -1), (-1, 0), (0, -1), (0, '-0'),
        ('-0', 0), ('-0', '-0'), (1, '-0'), ('-0', 1), ('', ''), ('-', ''),
        ('', '-'), ('-', '-'), (-1,'-'), ('?', '?'), ('-?', '?'),
        ('%TOTALDISCS%', 1),
        (3, '%TOTALDISCS%'),
        ('%TOTALDISCS%', '?'),
        ('?', '%TOTALDISCS%'),
        ('%TOTALDISCS%', '%TOTALDISCS%'),
        ('%MISSING%', '%TOTALDISCS%'),
        ('%TOTALDISCS%', '%MISSING%'),
        ('%MISSING%', '%MISSING%'),
    ):
      # First check the literal parser and how it handles numbers
      if fn != 'not': # Skip this check for not
        if type(t1) is int or type(t1) is not int and '%' not in t1:
          s1 = unistr(t1)
          literal_s1 = "'" + s1 + "'"
          a1 = t1 if type(t1) is int else resolve_int_var(t1, cs_01)
          a2 = t2 if type(t2) is int else resolve_int_var(t2, cs_01)
          fmt = '$%s(%s,%s)' % (fn, literal_s1, t2)
          expected = '' if group == 'boolean' else unistr(answer(a1, a2))
          expected_truth = False if fn == 'and' else '%' in unistr(t2)
          generated_cases.append(pytest.param(
            fmt, expected, expected_truth, cs_01,
            id="%s:arity2literal<'%s' = '%s'>" % (group, fmt, expected)))
          if len(s1) > 1:
            literal_s1 = "'" + s1[0] + "'" + s1[1:]
            fmt = '$%s(%s,%s)' % (fn, literal_s1, t2)
            generated_cases.append(pytest.param(
              fmt, expected, False, cs_01,
              id="%s:arity2literal<'%s' = '%s'>" % (group, fmt, expected)))

      for g1, g2, g3, g4 in (  # Also generate some garbage text to test with
          ('', '', '', ''),  # The default, no garbage
          ('', '--', '', '--'),
          ('', '!a', '', "','"),
          ('', "','", '', '!a'),
          ('  ', '  ', ' ', ' '),
          ('  ', " ',' ", " ',' ", " ',' "),
      ):
        if fn == 'not' and (
            g2 != ''
            or type(t1) is int and (-1 > t1 or t1 > 1)
            or type(t2) is int and (-1 > t2 or t2 > 1)
        ):
          # We really don't need to test $not that much for arity 2.
          continue
        t1g = '%s%s%s' % (g1, t1, g2)
        t2g = '%s%s%s' % (g3, t2, g4)
        fmt = '$%s(%s,%s)' % (fn, t1g, t2g)
        t1s = t1g.lstrip('% ').rstrip(stripchars)
        t2s = t2g.lstrip('% ').rstrip(stripchars)
        val1 = resolve_int_var(t1s, cs_01, stripped=True)
        val2 = resolve_int_var(t2s, cs_01, stripped=True)

        if group == 'arithmetic':
          expected = unistr(answer(val1, val2))
          expected_truth = (
              t1s.strip(stripchars) in cs_01
              or t2s.strip(stripchars) in cs_01)
        elif group == 'boolean':
          expected = ''
          try:
            expected_truth = answer(t1 == '%TOTALDISCS%', t2 == '%TOTALDISCS%')
          except TypeError:
            # Assume False, this is probably $not.
            expected_truth = False

        generated_cases.append(pytest.param(
            fmt, expected, expected_truth, cs_01,
            id="%s:arity2<%s = '%s'>" % (group, fmt, expected)))

    if fn == 'not':
      # We really don't need to test $not beyond arity 2.
      continue

    # Arity 3+ tests
    for t in (
        (0, 0, 0),
        (1, 2, 3),
        (0, 2, 3),
        (1, 0, 3),
        (1, 2, 0),
        (128, 2, 2),
        (128, 0, 3),
        (128, 5, 0),
        (128, -2, 2),
        (128, -0, 3),
        (128, -5, 0),
        (128, -2, -2),
        (128, -0, -3),
        (128, -5, -0),
        (-128, -2, -2),
        (-128, -0, -3),
        (-128, -5, -0),
        (6969, 0, -0),
        ('', '', ''),
        ('-', '-', '-'),
        ('%MISSING%', '%MISSING%', '%MISSING%'),
        ('%TOTALDISCS%', '%TOTALDISCS%', '%TOTALDISCS%'),
        ('%MISSING%', '%TOTALDISCS%', '%TOTALDISCS%'),
        ('%TOTALDISCS%', '%MISSING%', '%TOTALDISCS%'),
        ('%TOTALDISCS%', '%TOTALDISCS%', '%MISSING%'),
        (0, 0, '%TOTALDISCS%'),
        (1, 1, '%TOTALDISCS%'),
        (0, 0, '%MISSING%'),
        (1, 1, '%MISSING%'),
        (1, 2, 3, 4),
        (-4, -3, -2, -1),
        ('  -1!a', '-1- ', ' -2 -9-  ', '-3a bc  '),
        ('  -1!a', '-1- ', ' -2 -9-  ', '-3a bc  ', '10-')
    ):
      fmt = '$%s(%s)' % (fn, ','.join(map(unistr, t)))
      ts = [x for x in
            map(lambda x:
                x.lstrip('% ').replace('2 -9-', '2').rstrip(stripchars),
              map(unistr, t))]
      vals = [resolve_int_var(x, cs_01, stripped=True) for x in ts]

      if group == 'boolean':
        expected = ''
      else:
        expected = answer(vals[0], vals[1])
        for x in vals[2:]:
          expected = answer(expected, x)
        expected = unistr(expected)

      if group == 'boolean':
        try:
          expected_truth = reduce(answer, map(lambda x: x == '%TOTALDISCS%', t))
        except TypeError:
          # Assume False, this is probably $not.
          expected_truth = False
      else:
        expected_truth = reduce(
            lambda x, y: x or y, map(lambda z: z in cs_01, ts))
      generated_cases.append(pytest.param(
        fmt, expected, expected_truth, cs_01,
        id="%s:arity%s<'%s' = '%s'>" % (group, len(t), fmt, expected)))
  return generated_cases


test_eval_cases += generate_tests()


# Add min/max tests
for fn in ('min', 'max'):
  for case in (
      (['0'], '0', False),
      (['123'], '123', False),
      (['-'], '0', False),
      (['',''], '0', False),
      (['2','1'], '1', '2', False),
      (['-2','1'], '-2', '1', False),
      (['1','2'], '1', '2', False),
      (['-1','2'], '-1', '2', False),
      (['','',''], '0', False),
      (['-1','-2','-3'], '-3', '-1', False),
      (['','-2','-3'], '-3', '0', False),
      (['-2','-1','3', '2', ''], '-2', '3', False),
      (['%missing%'], '0', False),
      (['%totaltracks%'], cs_01['TOTALTRACKS'], True),
      (['%missing%', '%missing%'], '0', False),
      (['%totaltracks%', '%missing%'],
        '0', cs_01['TOTALTRACKS'], True),
      (['%missing%', '%totaltracks%'],
        '0', cs_01['TOTALTRACKS'], True),
      (['%missing%', '%missing%', '%missing%'], '0', False),
      (['%totaltracks%', '%missing%', '%missing%'],
        '0', cs_01['TOTALTRACKS'], True),
      (['%missing%', '%totaltracks%', '%missing%'],
        '0', cs_01['TOTALTRACKS'], True),
      (['%missing%', '%missing%', '%totaltracks%'],
        '0', cs_01['TOTALTRACKS'], True),
  ):
    caselen = len(case)
    fmt = '$%s(%s)' % (fn, ','.join(case[0]))
    min_expected = case[1]
    max_expected = case[-2]
    expected = min_expected if fn == 'min' else max_expected
    expected_truth = case[-1]
    arity = len(case[0])

    test_eval_cases.append(pytest.param(
      fmt, expected, expected_truth, cs_01,
      id="arithmetic:arity%s('%s' = '%s')" % (arity, fmt, expected)))
    # Now check for variable negation
    if len([e1 for e1 in filter((
        lambda x: len([e2 for e2 in filter((
          lambda y: '%' in y), x)]) > 0), case[0])]) > 0:
      negated = ['-' + x for x in case[0]]
      expected = unistr(-int(max_expected if fn == 'min' else min_expected))
      fmt = '$%s(%s)' % (fn, ','.join(negated))
      test_eval_cases.append(pytest.param(
        fmt, expected, expected_truth, cs_01,
        id="arithmetic:arity%s('%s' = '%s')" % (arity, fmt, expected)))


# Encoding tests for Unicode; $ansi() and $ascii(), etc. Format is:
# UNICODE_INPUT, ANSI_OUTPUT, ASCII_OUTPUT
encoding_tests = {
    # Latin-1 Supplement
    '00A0-00AF': (' ¡¢£¤¥¦§¨©ª«¬­®¯', ' ¡¢£¤¥¦§¨©ª«¬­®¯', ' !c?$Y|??Ca<?-R?'),
    '00B0-00BF': ('°±²³´µ¶·¸¹º»¼½¾¿', '°±²³´µ¶·¸¹º»¼½¾¿', '??23???.,1o>????'),
    '00C0-00CF': ('ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏ', 'ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏ', 'AAAAAAACEEEEIIII'),
    '00D0-00DF': ('ÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß', 'ÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß', 'DNOOOOO?OUUUUY??'),
    '00E0-00EF': ('àáâãäåæçèéêëìíîï', 'àáâãäåæçèéêëìíîï', 'aaaaaaaceeeeiiii'),
    '00F0-00FF': ('ðñòóôõö÷øùúûüýþÿ', 'ðñòóôõö÷øùúûüýþÿ', '?nooooo?ouuuuy?y'),
    # Latin Extended-A
    '0100-010F': ('ĀāĂăĄąĆćĈĉĊċČčĎď', 'AaAaAaCcCcCcCcDd', 'AaAaAaCcCcCcCcDd'),
    '0110-011F': ('ĐđĒēĔĕĖėĘęĚěĜĝĞğ', 'ÐdEeEeEeEeEeGgGg', 'DdEeEeEeEeEeGgGg'),
    '0120-012F': ('ĠġĢģĤĥĦħĨĩĪīĬĭĮį', 'GgGgHhHhIiIiIiIi', 'GgGgHhHhIiIiIiIi'),
    '0130-013F': ('İıĲĳĴĵĶķĸĹĺĻļĽľĿ', 'Ii??JjKk?LlLlLl?', 'Ii??JjKk?LlLlLl?'),
    '0140-014F': ('ŀŁłŃńŅņŇňŉŊŋŌōŎŏ', '?LlNnNnNn???OoOo', '?LlNnNnNn???OoOo'),
    '0150-015F': ('ŐőŒœŔŕŖŗŘřŚśŜŝŞş', 'OoŒœRrRrRrSsSsSs', 'OoOoRrRrRrSsSsSs'),
    '0160-016F': ('ŠšŢţŤťŦŧŨũŪūŬŭŮů', 'ŠšTtTtTtUuUuUuUu', 'SsTtTtTtUuUuUuUu'),
    '0170-017F': ('ŰűŲųŴŵŶŷŸŹźŻżŽžſ', 'UuUuWwYyŸZzZzŽž?', 'UuUuWwYyYZzZzZz?'),
    # Latin Extended-B
    '0180-018F': ('ƀƁƂƃƄƅƆƇƈƉƊƋƌƍƎƏ', 'b????????Ð??????', 'b????????D??????'),
    '0190-019F': ('ƐƑƒƓƔƕƖƗƘƙƚƛƜƝƞƟ', '?ƒƒ????I??l????O', '?Ff????I??l????O'),
    '01A0-01AF': ('ƠơƢƣƤƥƦƧƨƩƪƫƬƭƮƯ', 'Oo?????????t??TU', 'Oo?????????t??TU'),
    '01B0-01BF': ('ưƱƲƳƴƵƶƷƸƹƺƻƼƽƾƿ', 'u?????z?????????', 'u?????z?????????'),
    '01C0-01CF': ('ǀǁǂǃǄǅǆǇǈǉǊǋǌǍǎǏ', '|??!?????????AaI', '?????????????AaI'),
    '01D0-01DF': ('ǐǑǒǓǔǕǖǗǘǙǚǛǜǝǞǟ', 'iOoUuUuUuUuUu?Aa', 'iOoUuUuUuUuUu?Aa'),
    '01E0-01EF': ('ǠǡǢǣǤǥǦǧǨǩǪǫǬǭǮǯ', '????GgGgKkOoOo??', '????GgGgKkOoOo??'),
    '01F0-01FF': ('ǰǱǲǳǴǵǶǷǸǹǺǻǼǽǾǿ', 'j???????????????', 'j???????????????'),
    '0200-020F': ('ȀȁȂȃȄȅȆȇȈȉȊȋȌȍȎȏ', '????????????????', '????????????????'),
    '0210-021F': ('ȐȑȒȓȔȕȖȗȘșȚțȜȝȞȟ', '????????????????', '????????????????'),
    '0220-022F': ('ȠȡȢȣȤȥȦȧȨȩȪȫȬȭȮȯ', '????????????????', '????????????????'),
    '0230-023F': ('ȰȱȲȳȴȵȶȷȸȹȺȻȼȽȾȿ', '????????????????', '????????????????'),
    '0240-024F': ('ɀɁɂɃɄɅɆɇɈɉɊɋɌɍɎɏ', '????????????????', '????????????????'),
    # General Punctuation
    '2000-200F': ('           ​‌‍‎‏',
                  '       ?????????',
                  '       ?????????'),
    '2010-201F': ('‐‑‒–—―‖‗‘’‚‛“”„‟',
                  '--?–—??=‘’‚?“”„?',
                  '--?--???\'\',?"""?'),
    '2020-202F': ('†‡•‣․‥…‧  ‪‫‬‭‮ ',
                  '†‡•?·?…?????????',
                  '??.???.?????????'),
    '2030-203F': ('‰‱′″‴‵‶‷‸‹›※‼‽‾‿',
                  '‰?\'??`???‹›?????',
                  '??\'??`???<>?????'),
    '2040-204F': ('⁀⁁⁂⁃⁄⁅⁆⁇⁈⁉⁊⁋⁌⁍⁎⁏',
                  '????/???????????',
                  '????????????????'),
    '2050-205F': ('⁐⁑⁒⁓⁔⁕⁖⁗⁘⁙⁚⁛⁜⁝⁞ ',
                  '????????????????',
                  '????????????????'),
    '2060-206F': ('⁠⁡⁢⁣⁤⁦⁧⁨⁩⁪⁫⁬⁭⁮⁯',
                  '???????????????',
                  '???????????????'),
}


class TestTitleFormatter:
  @pytest.mark.parametrize('compiled', [
    pytest.param(False, id='interpreted'),
    pytest.param(True, id='compiled'),
  ])
  @pytest.mark.parametrize('fmt,expected,expected_truth,track', test_eval_cases)
  def test_eval(self, fmt, expected, expected_truth, compiled, track):
    if compiled:
      print("[TEST] Compiling titleformat...")
      fn = fdbg.eval(None, fmt, compiling=True)
      print("[TEST] Calling resulting function...")
      result = fn(track)
    else:
      result = fdbg.eval(track, fmt)

    assert result.string_value == expected
    assert result.truth_value is expected_truth

    if compiled:
      fn = f.eval(None, fmt, compiling=True)
      quiet_result = fn(track)
    else:
      quiet_result = f.eval(track, fmt)

    assert quiet_result.string_value == expected
    assert quiet_result.truth_value is expected_truth

  @pytest.mark.parametrize('block', encoding_tests.keys())
  def test_eval_ansi_encoding(self, block):
    unicode_input, expected_ansi, _ = encoding_tests[block]

    result_ansi = fdbg.eval(None, "$ansi('%s')" % unicode_input)

    assert result_ansi.string_value == expected_ansi
    assert not result_ansi.truth_value

  @pytest.mark.parametrize('block', encoding_tests.keys())
  def test_eval_ascii_encoding(self, block):
    unicode_input, _, expected_ascii = encoding_tests[block]

    result_ascii = fdbg.eval(None, "$ascii('%s')" % unicode_input)

    assert result_ascii.string_value == expected_ascii
    assert not result_ascii.truth_value

