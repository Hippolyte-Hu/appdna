"""The recording build must not retain the upstream untranslated prompting labels."""
import runpy
from pathlib import Path

HELPER = Path(__file__).resolve().parents[2] / 'tasks/overnight/prepare_voicecue_english.py'


def test_prompting_labels_and_sample_are_english():
    module = runpy.run_path(str(HELPER))
    js = "const DEFAULT_SCRIPT = `大家好，欢迎回到频道。`; setListeningUi(true, '本地 Whisper 正在监听'); setHeardPreview(`听到：${clean.slice(-60)}`);"
    result = module['localize_js'](js)
    assert '大家好' not in result
    assert 'Local Whisper is listening' in result
    assert 'Heard: ${clean.slice(-60)}' in result


def test_prompt_controls_are_real_translated_controls():
    module = runpy.run_path(str(HELPER))
    result = module['localize_html']('<button id="editButton">编辑文稿</button><small>暂停</small><small>放大</small>')
    assert result == '<button id="editButton">Edit script</button><small>Pause</small><small>Larger</small>'
    assert module["localize_html"]("搜索稿件") == "Search scripts"
