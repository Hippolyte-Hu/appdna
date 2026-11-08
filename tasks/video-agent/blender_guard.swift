// PID-scoped Blender probe/input. Refuse locked sessions and foreground changes.
import Foundation
import AppKit
import CoreGraphics
import ApplicationServices

func output(_ value: [String:Any]) {
    let data = try! JSONSerialization.data(withJSONObject:value, options:[.sortedKeys])
    print(String(data:data,encoding:.utf8)!)
}
func fail(_ message:String) -> Never { output(["error":message]);exit(2) }
let args=CommandLine.arguments
let command=args.count>1 ? args[1] : "probe"
let pid=pid_t(args.count>2 ? Int32(args[2]) ?? 0 : 0)
let session=CGSessionCopyCurrentDictionary() as? [String:Any] ?? [:]
let locked=(session["CGSSessionScreenIsLocked"] as? Bool ?? false) || (session[kCGSessionOnConsoleKey as String] as? Bool != true)
if command == "lock" { output(["locked":locked]);exit(0) }
if locked { fail("Mac is locked. Unlock it before running Blender actions.") }
guard let app=NSRunningApplication(processIdentifier:pid),app.bundleIdentifier=="org.blenderfoundation.blender" else { fail("Target PID is not Blender") }
if command == "activate" {
    app.activate(options:[]);Thread.sleep(forTimeInterval:0.7)
}
guard NSWorkspace.shared.frontmostApplication?.processIdentifier==pid else { fail("Blender target is not foreground; no input sent") }
guard AXIsProcessTrusted() else { fail("Accessibility permission is missing") }
guard CGPreflightScreenCaptureAccess() else { fail("Screen Recording permission is missing") }
let windows=CGWindowListCopyWindowInfo([.optionOnScreenOnly,.excludeDesktopElements],kCGNullWindowID) as? [[String:Any]] ?? []
let matches=windows.filter { ($0[kCGWindowOwnerPID as String] as? Int)==Int(pid) && ($0[kCGWindowLayer as String] as? Int)==0 }
func area(_ window:[String:Any]) -> Double {
    let rect=window[kCGWindowBounds as String] as? [String:Double] ?? [:]
    let width:Double=rect["Width"] ?? 0
    let height:Double=rect["Height"] ?? 0
    return width*height
}
let sorted:[[String:Any]]=matches.sorted { area($0)>area($1) }
let selected=matches.first { ($0[kCGWindowName as String] as? String)=="Blender File View" } ?? sorted.first
guard let w=selected,let bounds=w[kCGWindowBounds as String] as? [String:Double],(bounds["Width"] ?? 0)>400 else { fail("No visible Blender main window for target PID") }
if command=="probe" || command=="activate" { output(["locked":false,"pid":Int(pid),"bounds":bounds]);exit(0) }
let source=CGEventSource(stateID:.hidSystemState)
if command=="click" || command=="double_click" || command=="right_click" {
    guard args.count==5,let x=Double(args[3]),let y=Double(args[4]),x>=0,x<=1000,y>=0,y<=1000 else { fail("Invalid normalized coordinates") }
    let point=CGPoint(x:(bounds["X"] ?? 0)+x*(bounds["Width"] ?? 0)/1000,y:(bounds["Y"] ?? 0)+y*(bounds["Height"] ?? 0)/1000)
    CGEvent(mouseEventSource:source,mouseType:.mouseMoved,mouseCursorPosition:point,mouseButton:.left)!.post(tap:.cghidEventTap)
    Thread.sleep(forTimeInterval:0.15)
    for count in 1...(command=="double_click" ? 2 : 1) {
        let types:[CGEventType]=command=="right_click" ? [.rightMouseDown,.rightMouseUp] : [.leftMouseDown,.leftMouseUp]
        for kind in types {
            let event=CGEvent(mouseEventSource:source,mouseType:kind,mouseCursorPosition:point,mouseButton:command=="right_click" ? .right : .left)!
            event.setIntegerValueField(.mouseEventClickState,value:Int64(count));event.post(tap:.cghidEventTap)
            Thread.sleep(forTimeInterval:0.06)
        }
    }
} else if command=="key" {
    let codes:[String:CGKeyCode] = ["return":36,"escape":53,"tab":48,"space":49,"up":126,"down":125,"left":123,"right":124,"f3":99,"ctrl+a":0,"ctrl+shift+s":1,"shift+tab":48]
    guard args.count==4,let code=codes[args[3]] else { fail("Shortcut not allowed") }
    var flags=CGEventFlags()
    var modifiers:[CGKeyCode]=[]
    if args[3].contains("ctrl+"){flags.insert(.maskControl);modifiers.append(59)}
    if args[3].contains("shift+"){flags.insert(.maskShift);modifiers.append(56)}
    for modifier in modifiers {
        let e=CGEvent(keyboardEventSource:source,virtualKey:modifier,keyDown:true)!;e.flags=flags;e.post(tap:.cghidEventTap)
        Thread.sleep(forTimeInterval:0.06)
    }
    for down in [true,false] {
        let e=CGEvent(keyboardEventSource:source,virtualKey:code,keyDown:down)!;e.flags=flags;e.post(tap:.cghidEventTap)
        Thread.sleep(forTimeInterval:0.06)
    }
    for modifier in modifiers.reversed() {
        let e=CGEvent(keyboardEventSource:source,virtualKey:modifier,keyDown:false)!;e.flags=[];e.post(tap:.cghidEventTap)
        Thread.sleep(forTimeInterval:0.06)
    }
} else if command=="type" {
    guard args.count==4,args[3].count<=512 else { fail("Invalid input") }
    if args[3].count>10 {
        // Blender's separate file-browser window can ignore Unicode key events.
        // Paste only validator-approved text; preserve clipboard data without logging it.
        let board=NSPasteboard.general
        let previous=(board.pasteboardItems ?? []).map { item in
            Dictionary(uniqueKeysWithValues:item.types.compactMap { type in item.data(forType:type).map { (type,$0) } })
        }
        board.clearContents();board.setString(args[3],forType:.string)
        defer {
            board.clearContents()
            let items=previous.map { values -> NSPasteboardItem in let item=NSPasteboardItem();for (type,data) in values {item.setData(data,forType:type)};return item }
            board.writeObjects(items)
        }
        for (key,down,flags):(CGKeyCode,Bool,CGEventFlags) in [(59,true,.maskControl),(9,true,.maskControl),(9,false,.maskControl),(59,false,[])] {
            let e=CGEvent(keyboardEventSource:source,virtualKey:key,keyDown:down)!;e.flags=flags;e.post(tap:.cghidEventTap)
            Thread.sleep(forTimeInterval:0.08)
        }
        Thread.sleep(forTimeInterval:0.3)
    } else {
        for unit in args[3].utf16 {
            let chars=[unit]
            for down in [true,false] {
                let e=CGEvent(keyboardEventSource:source,virtualKey:0,keyDown:down)!;e.flags=[]
                e.keyboardSetUnicodeString(stringLength:1,unicodeString:chars);e.post(tap:.cghidEventTap)
                Thread.sleep(forTimeInterval:0.005)
            }
        }
    }
} else { fail("Unknown command") }
output(["posted":true,"pid":Int(pid)])
