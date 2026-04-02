on run argv
	set folderId to item 1 of argv
	tell application "Notes"
		repeat with acc in accounts
			repeat with fld in folders of acc
				if my safe_text(id of fld) is folderId then
					delete fld
					return "{" & quote & "deleted" & quote & ":true," & quote & "folder_id" & quote & ":" & my json_string(folderId) & "}"
				end if
			end repeat
		end repeat
	end tell
	return "{" & quote & "deleted" & quote & ":false," & quote & "folder_id" & quote & ":" & my json_string(folderId) & "}"
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

