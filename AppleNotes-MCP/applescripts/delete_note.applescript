on run argv
	set targetNoteId to item 1 of argv
	tell application "Notes"
		try
			delete note id targetNoteId
			return "{" & quote & "deleted" & quote & ":true," & quote & "note_id" & quote & ":" & my json_string(targetNoteId) & "}"
		on error
			return "{" & quote & "deleted" & quote & ":false," & quote & "note_id" & quote & ":" & my json_string(targetNoteId) & "}"
		end try
	end tell
end run

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
