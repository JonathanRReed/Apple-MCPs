on run argv
	set folderId to item 1 of argv
	set folderName to item 2 of argv
	tell application "Notes"
		repeat with acc in accounts
			repeat with fld in folders of acc
				if my safe_text(id of fld) is folderId then
					set name of fld to folderName
					return "{" & quote & "folder" & quote & ":" & my folder_json(fld, acc) & "}"
				end if
			end repeat
		end repeat
	end tell
	return "{" & quote & "found" & quote & ":false}"
end run

on folder_json(fld, acc)
	return "{" & quote & "folder_id" & quote & ":" & my json_string(my safe_text(id of fld)) & "," & quote & "name" & quote & ":" & my json_string(my safe_text(name of fld)) & "," & quote & "account_id" & quote & ":" & my json_string(my safe_text(id of acc)) & "," & quote & "account_name" & quote & ":" & my json_string(my safe_text(name of acc)) & "," & quote & "parent_folder_id" & quote & ":null," & quote & "parent_folder_name" & quote & ":null," & quote & "shared" & quote & ":false}"
end folder_json

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
