"""Record actual VoiceCue UI in an isolated library with prerecorded test speech.
No real microphone, private library, or synthetic application response is used.
"""
import json
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "deliverables"
OUT.mkdir(exist_ok=True)
SCRIPT = """Here is VoiceCue, a teleprompter designed to follow your speech instead of making you chase a fixed scrolling speed. This is the real VoiceCue interface, running locally in a clean demonstration workspace. First, give the episode a title and paste the script you want to read. You can expand the editor to focus on longer text. Next, select the recognition language. VoiceCue offers Mandarin Chinese, English, French, and Cantonese. Set a countdown if you need a moment to get into position. Before recording, check that the local Whisper engine and script protection are ready. Speech recognition runs on this Mac. Saving an episode adds it to the local Script Library. You can find it again by title, reopen it, and reuse it as a new episode without replacing the original. Start prompting to enter the reading view. The controls let you pause, adjust the reading presentation, and return to editing. The purpose of voice following is to keep your current line in view as your pace changes. Whisper processes speech in chunks, so this is not a claim of instant, word-perfect tracking. This demonstration shows the actual interface and local workflow. A procurement team would still need to test recognition accuracy, accessibility, supported hardware, and its own recording conditions. That distinction matters: a demonstration explains a product, but it does not independently prove every claim. Next, AppDNA will analyze this recording as evidence, connect what it sees to the application knowledge map, and keep untested requirements visible in the evaluation."""
(OUT / "voicecue-demo-narration.txt").write_text(SCRIPT)
wave = OUT / "voicecue-demo-test-speech.wav"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(OUT / "voicecue-demo-narration.mp3"), "-ar", "48000", "-ac", "1", str(wave)], check=True)
events = []
errors = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", f"--use-file-for-fake-audio-capture={wave}"])
    # The taller capture keeps the setup card and prompting dock readable in-frame.
    context = browser.new_context(viewport={"width": 1600, "height": 1000}, record_video_dir=str(OUT / "raw"), record_video_size={"width": 1600, "height": 1000}, permissions=["microphone"], reduced_motion="reduce", locale="en-US")
    page = context.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("response", lambda response: events.append({"event": "local_transcription", "status": response.status, "at": round(time.monotonic() - start, 2)}) if "/transcribe" in response.url else None)
    start = time.monotonic()
    page.add_init_script(r"""
      window.__englishViolations = [];
      setInterval(() => {
        if (!document.body) return;
        const seen = [];
        const visible = el => el && el.checkVisibility({opacityProperty:true,visibilityProperty:true}) && (()=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth})();
        const walker = document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
        let n;
        while(n=walker.nextNode()) if(visible(n.parentElement)&&!n.parentElement.closest('select,script,style')&&/[\u3400-\u9fff]/.test(n.textContent)) seen.push(n.textContent.trim());
        for(const el of document.querySelectorAll('textarea,input[type="text"],input[type="search"]')) if(visible(el)&&/[\u3400-\u9fff]/.test(el.value)) seen.push(el.value);
        for(const text of seen) if(!window.__englishViolations.includes(text)) window.__englishViolations.push(text);
      },100);
    """)
    def at(second, label, fn):
        remaining = second - (time.monotonic() - start)
        if remaining > 0: page.wait_for_timeout(remaining * 1000)
        fn()
        events.append({"at": round(time.monotonic() - start, 2), "event": label})
    page.goto("http://127.0.0.1:43976")
    page.locator("#scriptInput").wait_for()
    at(9, "episode title", lambda: page.locator("#episodeTitle").fill("VoiceCue procurement demo — local workspace"))
    at(13, "paste script", lambda: page.locator("#scriptInput").fill(SCRIPT))
    at(21, "expand editor", lambda: page.locator("#expandScriptButton").click())
    page.screenshot(path=str(OUT / "raw/voicecue-editor.png"))
    at(26, "close expanded editor", lambda: page.keyboard.press("Escape"))
    at(29, "select English recognition", lambda: page.locator("#languageSelect").select_option("en-US"))
    at(37, "countdown", lambda: page.locator("#countdownSelect").select_option("3"))
    at(43, "readiness", lambda: page.locator("#saveScriptButton").scroll_into_view_if_needed())
    at(47, "save sample episode", lambda: page.locator("#saveScriptButton").click())
    at(53, "open library", lambda: page.locator("#libraryButton").click())
    at(57, "search sample episode", lambda: page.locator("#librarySearch").fill("procurement"))
    at(62, "close library", lambda: page.locator("#closeLibraryButton").click())
    at(66, "start with prerecorded ElevenLabs speech through real local Whisper", lambda: page.locator("#startButton").click())
    def dock_click(selector):
        page.mouse.move(1100, 600)
        page.wait_for_timeout(200)
        page.locator(selector).click()
    at(82, "increase reading size", lambda: dock_click("#largerButton"))
    at(90, "pause", lambda: dock_click("#listenButton"))
    page.screenshot(path=str(OUT / "raw/voicecue-prompting.png"))
    at(94, "return to editing", lambda: dock_click("#editButton"))
    at(106, "end", lambda: None)
    final_text = page.locator("body").inner_text()
    language_violations = page.evaluate("window.__englishViolations")
    video = page.video
    context.close()
    raw = OUT / "voicecue-demo-screen.webm"
    video.save_as(str(raw))
    browser.close()
manifest = {"capture": "Actual English-localized VoiceCue browser demo build on local server 43976; not the upstream native window", "data": "Isolated demo library; no user scripts", "speech_input": "Prerecorded ElevenLabs narration supplied as test microphone audio; real local Whisper requests, not live human speech", "events": events, "page_errors": errors, "visible_language_violations": language_violations, "final_text": final_text}
(OUT / "voicecue-demo-capture.json").write_text(json.dumps(manifest, indent=2))
assert not errors, errors
assert not language_violations, language_violations
assert any(event["event"] == "local_transcription" and event["status"] == 200 for event in events), "Local Whisper must actually process the prerecorded speech"
print(json.dumps({"raw_video": str(raw), "events": len(events), "transcription_requests": sum(event["event"] == "local_transcription" for event in events), "page_errors": errors}))
