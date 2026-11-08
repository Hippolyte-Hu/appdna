"""Pure localization helpers for the retained VoiceCue demo tests.

Importing this module never modifies an application or starts a recording.
"""
import re


def localize_html(html: str) -> str:
    for original,english in {'编辑文稿':'Edit script','暂停':'Pause','放大':'Larger','搜索稿件':'Search scripts'}.items():
        html=html.replace(original,english)
    return html


def localize_js(script: str) -> str:
    script=re.sub(r'(const DEFAULT_SCRIPT\s*=\s*)`[^`]*`',
                  r'\1`Hello and welcome. Today we will walk through a simple demonstration.`',script)
    return script.replace('本地 Whisper 正在监听','Local Whisper is listening').replace('听到：','Heard: ')
