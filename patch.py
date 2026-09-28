#!/usr/bin/env python3
"""Apply tv.team fixes to the upstream Lampa IPTV plugin.

Usage: patch.py <upstream.js> <out.js>
Every patch must match exactly once; otherwise the build fails and the
previously published iptv.js stays in place.
"""
import re
import sys

EPG_DEFAULT = 'https://epg.team/3.1.xml.gz'

TT_STORE = r"""
  console.log('TT', 'plugin %(label)s loaded');
  // --- tv.team fork: in-memory EPG store ---
  var TT = window.TT_EPG = window.TT_EPG || {
    url: '%(epg)s',
    ids: {},
    cur: {},
    next: {},
    put: function (id, list) {
      if (id === -1 || !list || !list.length) return;
      var ids = Object.keys(this.ids);
      if (ids.length && !this.ids[id]) return;
      var from = Date.now() - 12 * 3600e3, to = Date.now() + 48 * 3600e3;
      var out = [];
      for (var i = 0; i < list.length; i++) {
        var p = list[i];
        if (p.stop < from || p.start > to) continue;
        out.push({ start: p.start, stop: p.stop, title: p.title, category: p.category, desc: (p.desc || '').slice(0, 400), icon: p.icon });
      }
      if (out.length) { this.next[id] = out; this.cur[id] = out; }
    },
    swap: function () { if (Object.keys(this.next).length) this.cur = this.next; this.next = {}; },
    get: function (id) { return this.cur[id]; }
  };
"""

PATCHES = [
    # XMLTV tags without attributes (epg.team writes bare <title>, <desc>, <display-name>)
    ("xmltv display-name",
     "string.match(/<display-name[^>]+>(.*?)</g);",
     "string.match(/<display-name[^>]*>(.*?)</g);"),
    ("xmltv title",
     "m_title = string.match(/<title[^>]+>(.*?)</);",
     "m_title = string.match(/<title[^>]*>(.*?)</);"),
    ("xmltv category",
     "m_category = string.match(/<category[^>]+>(.*?)</);",
     "m_category = string.match(/<category[^>]*>(.*?)</);"),
    ("xmltv desc",
     "m_desc = string.match(/<desc[^>]+>(.*?)</);",
     "m_desc = string.match(/<desc[^>]*>(.*?)</);"),

    # guide parse: keep programme in memory, flush the last channel
    ("guide store programme",
     "if (last_id == data.id) program.push(data.program);else {\n",
     "if (last_id == data.id) program.push(data.program);else {\n                TT.put(last_id, program);\n"),
    ("guide end",
     "Parser.listener.follow('end', function (data) {\n              program = [];",
     "Parser.listener.follow('end', function (data) {\n              TT.put(last_id, program);\n              TT.swap();\n"
     "              console.log('TT', 'guide end', 'channels=' + Object.keys(data.channel).length, 'stored=' + Object.keys(TT.cur).length, 'ids=' + Object.keys(TT.ids).length);\n"
     "              program = [];"),

    # programme lookup: memory first
    ("program lookup",
     "          if (tvg_id) {\n            loadEPG(tvg_id, function () {",
     "          var mem = tvg_id ? TT.get(tvg_id) : null;\n"
     "          console.log('TT', 'program', 'name=' + data.name, 'channel_id=' + data.channel_id, 'tvg=' + JSON.stringify(data.tvg), 'mem=' + (mem ? mem.length : 'none'), 'store=' + Object.keys(TT.cur).length, 'ids=' + Object.keys(TT.ids).length);\n"
     "          if (mem && mem.length) return resolve(mem);\n\n"
     "          if (tvg_id) {\n            loadEPG(tvg_id, function () {"),

    # guide URL: only default when empty
    ("guide url default",
     "var url = Lampa.Storage.get('iptv_guide_url');",
     "var url = Lampa.Storage.get('iptv_guide_url') || TT.url;"),
    ("guide custom default",
     "if (Lampa.Storage.field('iptv_guide_custom') && url) {",
     "if (url) {"),
    # memory is empty after start -> always load the guide
    ("guide on start",
     "if (Lampa.Storage.field('iptv_guide_update_after_start')) this.update();",
     "this.update();"),

    # playlist: remember tvg ids, parse locally (CUB drops tvg-id), ignore CUB-parsed cache
    ("playlist ids",
     "                var channel = {\n                  id: item.tvg && item.tvg.id ? item.tvg.id : null,",
     "                if (item.tvg && item.tvg.id) TT.ids[item.tvg.id] = 1;\n"
     "                var channel = {\n                  id: item.tvg && item.tvg.id ? item.tvg.id : null,"),
    ("playlist local parse",
     re.compile(r"            if \(params && params\.loading == 'lampa' \|\| data\.custom\) \{\n.*?\n            \}\n(?=\s*\}\)\[\"catch\"\])", re.S),
     "            _this5.m3uClient(data.url).then(secuses)[\"catch\"](error);\n"),
    ("playlist cache version",
     "if (playlist && params) {\n              var time = {",
     "if (playlist && playlist.channels) playlist.channels.forEach(function (c) { if (c.id) TT.ids[c.id] = 1; });\n\n"
     "            if (playlist && params && playlist.tt_v === 1) {\n              var time = {"),
    ("playlist cache mark",
     "            var secuses = function secuses(result) {\n              DB.rewriteData",
     "            var secuses = function secuses(result) {\n              result.tt_v = 1;\n              DB.rewriteData"),
    ("playlist log",
     "            var playlist = result[0];\n            var params = result[1];",
     "            var playlist = result[0];\n            var params = result[1];\n"
     "            console.log('TT', 'playlist', id, 'cached=' + !!playlist, 'tt_v=' + (playlist && playlist.tt_v), 'custom=' + data.custom);"),

    # channel without internal id -> use tvg-id (2 places)
    ("channel id fallback",
     "if (channel.id) {",
     "if (!channel.id && channel.tvg && channel.tvg.id) channel.id = channel.tvg.id;\n\n        if (channel.id) {",
     2),
    ("draw log",
     "        this.wait_for = channel.name;\n",
     "        this.wait_for = channel.name;\n"
     "        console.log('TT', 'draw', channel.name, 'id=' + channel.id, 'tvg=' + JSON.stringify(channel.tvg));\n"),
]


def main(src, dst):
    s = open(src, encoding='utf-8').read().replace('\r\n', '\n')
    ver = re.search(r"version: '([\d.]+)'", s)
    label = 'TT ' + (ver.group(1) if ver else '?')

    for p in PATCHES:
        name, old, new = p[0], p[1], p[2]
        want = p[3] if len(p) > 3 else 1
        if isinstance(old, re.Pattern):
            found = len(old.findall(s))
            if found != want:
                sys.exit(f'patch "{name}": expected {want} match, found {found}')
            s = old.sub(lambda m: new, s)
        else:
            found = s.count(old)
            if found != want:
                sys.exit(f'patch "{name}": expected {want} match, found {found}')
            s = s.replace(old, new)

    # visible marker in menu / settings / title
    for old in ["'IPTV', \"</div>", "name: 'IPTV'", "title: 'IPTV',"]:
        if old not in s:
            sys.exit(f'label patch not found: {old}')
        s = s.replace(old, old.replace("'IPTV'", "'IPTV %s'" % label))

    head = "(function () {\n  'use strict';\n"
    if not s.startswith(head):
        sys.exit('unexpected file header')
    s = head + TT_STORE % {'label': label, 'epg': EPG_DEFAULT} + s[len(head):]

    open(dst, 'w', encoding='utf-8').write(s)
    print(f'ok: {label}, {len(s)} bytes')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
