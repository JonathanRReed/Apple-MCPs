on run argv
	set targetNoteId to item 1 of argv
	set folderId to item 2 of argv
	tell application "Notes"
		set noteRef to my find_note(targetNoteId)
		if noteRef is missing value then return "{" & quote & "moved" & quote & ":false," & quote & "note_id" & quote & ":" & my json_string(targetNoteId) & "}"
		set targetFolder to my find_folder(folderId)
		if targetFolder is missing value then error "Can't get folder '" & folderId & "'."
		move noteRef to targetFolder
		return "{" & quote & "moved" & quote & ":true," & quote & "note_id" & quote & ":" & my json_string(targetNoteId) & "}"
	end tell
end run

on find_note(targetNoteId)
	tell application "Notes"
		repeat with acc in accounts
			repeat with fld in folders of acc
				repeat with n in notes of fld
					if my safe_text(id of n) is targetNoteId then return n
				end repeat
			end repeat
		end repeat
	end tell
	return missing value
end find_note

on find_folder(targetFolderId)
	tell application "Notes"
		repeat with acc in accounts
			repeat with fld in folders of acc
				if my safe_text(id of fld) is targetFolderId then return fld
			end repeat
		end repeat
	end tell
	return missing value
end find_folder

on safe_text(valueText)
	try
		return valueText as text
	on error
		return ""
	end try
end safe_text

on json_string(valueText)
	set backslash to ASCII character 92
	set escapedText to my replace_text(valueText as text, backslash, backslash & backslash)
	set escapedText to my replace_text(escapedText, quote, backslash & quote)
	set escapedText to my replace_text(escapedText, return, backslash & "n")
	set escapedText to my replace_text(escapedText, linefeed, backslash & "n")
	return quote & escapedText & quote
end json_string

on replace_text(sourceText, findText, replaceText)
	set originalDelimiters to AppleScript's text item delimiters
	set AppleScript's text item delimiters to findText
	set sourceItems to text items of sourceText
	set AppleScript's text item delimiters to replaceText
	set resultText to sourceItems as text
	set AppleScript's text item delimiters to originalDelimiters
	return resultText
end replace_text
