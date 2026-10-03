; ===================================================================
; macro_player.ahk - ФИНАЛЬНАЯ ВЕРСИЯ С DPI FIX
; ===================================================================

#Requires AutoHotkey v2.0
#SingleInstance Force
#Warn All, Off

; ===================================================================
; ФУНКЦИИ
; ===================================================================

TranslateKey(keyStr) {
    keyStr := StrReplace(keyStr, "ctrl_l+", "^")
    keyStr := StrReplace(keyStr, "ctrl_r+", "^")
    keyStr := StrReplace(keyStr, "ctrl+", "^")
    keyStr := StrReplace(keyStr, "alt_l+", "!")
    keyStr := StrReplace(keyStr, "alt_r+", "!")
    keyStr := StrReplace(keyStr, "alt+", "!")
    keyStr := StrReplace(keyStr, "shift_l+", "+")
    keyStr := StrReplace(keyStr, "shift_r+", "+")
    keyStr := StrReplace(keyStr, "shift+", "+")
    keyStr := StrReplace(keyStr, "cmd_l+", "#")
    keyStr := StrReplace(keyStr, "cmd_r+", "#")
    keyStr := StrReplace(keyStr, "cmd+", "#")
    
    keyStr := StrReplace(keyStr, "enter", "{Enter}")
    keyStr := StrReplace(keyStr, "tab", "{Tab}")
    keyStr := StrReplace(keyStr, "space", "{Space}")
    keyStr := StrReplace(keyStr, "backspace", "{Backspace}")
    keyStr := StrReplace(keyStr, "delete", "{Delete}")
    keyStr := StrReplace(keyStr, "esc", "{Esc}")
    keyStr := StrReplace(keyStr, "up", "{Up}")
    keyStr := StrReplace(keyStr, "down", "{Down}")
    keyStr := StrReplace(keyStr, "left", "{Left}")
    keyStr := StrReplace(keyStr, "right", "{Right}")
    keyStr := StrReplace(keyStr, "page_up", "{PgUp}")
    keyStr := StrReplace(keyStr, "page_down", "{PgDn}")
    keyStr := StrReplace(keyStr, "home", "{Home}")
    keyStr := StrReplace(keyStr, "end", "{End}")
    keyStr := StrReplace(keyStr, "insert", "{Insert}")
    keyStr := StrReplace(keyStr, "caps_lock", "{CapsLock}")
    
    if (InStr(keyStr, "vk_")) {
        vkCode := SubStr(keyStr, 4)
        keyStr := "{vk" vkCode "}"
    }
    
    return keyStr
}

JSON_Parse(src) {
    static q := Chr(34)
    
    key := ""
    stack := [tree := []]
    next := tree
    pos := 0
    isKey := false
    
    while ((ch := SubStr(src, ++pos, 1)) != "") {
        if (ch = " " || ch = "`t" || ch = "`r" || ch = "`n")
            continue
            
        if (ch = ",") {
            isKey := true
            continue
        }
        
        if (ch = ":") {
            isKey := false
            continue
        }
        
        if (ch = "}" || ch = "]") {
            stack.Pop()
            next := stack[-1]
            isKey := false
            continue
        }
        
        if (ch = "{") {
            obj := Map()
            
            if (Type(next) = "Array")
                next.Push(obj)
            else if (key != "")
                next[key] := obj
                
            stack.Push(obj)
            next := obj
            isKey := true
            continue
        }
        
        if (ch = "[") {
            obj := []
            
            if (Type(next) = "Array")
                next.Push(obj)
            else if (key != "")
                next[key] := obj
                
            stack.Push(obj)
            next := obj
            isKey := false
            continue
        }
        
        if (ch = q) {
            i := pos
            loop {
                i := InStr(src, q,, i+1)
                if (!i)
                    break
                if (SubStr(src, i-1, 1) != "\")
                    break
            }
            val := SubStr(src, pos+1, i-pos-1)
            pos := i
            
            val := StrReplace(val, "\" q, q)
            val := StrReplace(val, "\\", "\")
        } else {
            i := RegExMatch(src, "[\]\},\s]|$",, pos)
            val := SubStr(src, pos, i - pos)
            pos := i - 1
            
            if (val = "true")
                val := true
            else if (val = "false")
                val := false
            else if (val = "null")
                val := ""
            else if (RegExMatch(val, "^-?\d+(\.\d*)?$"))
                val := Number(val)
        }
        
        if (isKey) {
            key := val
        } else {
            if (Type(next) = "Array")
                next.Push(val)
            else if (key != "")
                next[key] := val
        }
    }
    
    return tree[1]
}

; ===================================================================
; ОСНОВНОЙ КОД
; ===================================================================

; Устанавливаем режим координат
CoordMode("Mouse", "Screen")
CoordMode("Pixel", "Screen")

; Лог файл
logFile := A_ScriptDir "\macro_player_debug.log"
FileAppend("=== Macro Player Started ===`n", logFile)

; Проверяем аргументы
if (A_Args.Length < 1) {
    MsgBox("Usage: macro_player.exe <file>")
    ExitApp
}

sessionFile := A_Args[1]
FileAppend("Session: " sessionFile "`n", logFile)

if (!FileExist(sessionFile)) {
    MsgBox("File not found")
    ExitApp
}

; Читаем файл
try {
    jsonText := FileRead(sessionFile, "UTF-8")
    FileAppend("Read OK`n", logFile)
} catch as err {
    MsgBox("Read error: " err.Message)
    ExitApp
}

; Парсим JSON
try {
    sessionData := JSON_Parse(jsonText)
    FileAppend("Parsed OK`n", logFile)
} catch as err {
    FileAppend("Parse error: " err.Message "`n", logFile)
    MsgBox("Parse error: " err.Message)
    ExitApp
}

; Получаем действия
actions := sessionData.Has("actions") ? sessionData["actions"] : []
FileAppend("Actions: " actions.Length "`n", logFile)

if (actions.Length = 0)
    ExitApp

; Задержка перед началом
Sleep(100)

; Выполняем действия
for index, action in actions {
    FileAppend("Action " index ": ", logFile)
    
    actionType := action.Has("type") ? action["type"] : ""
    FileAppend(actionType " ", logFile)
    
    if (actionType = "click") {
        x := action.Has("x") ? action["x"] : 0
        y := action.Has("y") ? action["y"] : 0
        button := action.Has("button") ? action["button"] : "left"
        
        FileAppend("(" x "," y "," button ") ", logFile)
        
        MouseMove(x, y)
        Sleep(10)
        
        if (button = "left")
            Click(x, y)
        else if (button = "right")
            Click(x, y, "Right")
        else if (button = "middle")
            Click(x, y, "Middle")
        
        FileAppend("OK`n", logFile)
            
    } else if (actionType = "key_press") {
        keyStr := action.Has("key") ? action["key"] : ""
        FileAppend(keyStr " ", logFile)
        
        if (keyStr != "") {
            translated := TranslateKey(keyStr)
            Send(translated)
            FileAppend("OK`n", logFile)
        }
    }
    
    delay := action.Has("delay") ? action["delay"] : 0.1
    if (delay > 0)
        Sleep(delay * 1000)
}

FileAppend("=== Completed ===`n", logFile)
ExitApp
