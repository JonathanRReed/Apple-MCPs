on run argv
	set jsonItems to {}
	tell application "Notes"
		repeat with acc in accounts
			set accName to my safe_text(name of acc)
			set accId to my safe_text(id of acc)
			set upgradedValue to false
			try
				set upgradedValue to upgraded of acc
			end try
			set defaultFolderId to ""
			try
				set defaultFolderId to my safe_text(id of default folder of acc)
			end try
			set end of jsonItems to "{" & ¬
				quote & "account_id" & quote & ":" & my json_string(accId) & "," & ¬
				quote & "name" & quote & ":" & my json_string(accName) & "," & ¬
				quote & "upgraded" & quote & ":" & my json_boolean(upgradedValue) & "," & ¬
				quote & "default_folder_id" & quote & ":" & my nullable_json_string(defaultFolderId) & "}"
		end repeat
	end tell
	return "{" & quote & "items" & quote & ":[" & my join_list(jsonItems, ",") & "]}"
end run

on safe_text(valueText)
	try
		return valueText as text
	on error
		return ""
	end try
end safe_text

on nullable_json_string(valueText)
	if valueText is "" then
		return "null"
	end if
	return my json_string(valueText)
end nullable_json_string

on json_boolean(boolValue)
	if boolValue then
		return "true"
	end if
	return "false"
end json_boolean

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

on join_list(itemList, delimiterText)
	if (count of itemList) is 0 then
		return ""
	end if
	set originalDelimiters to AppleScript's text item delimiters
	set AppleScript's text item delimiters to delimiterText
	set joinedText to itemList as text
	set AppleScript's text item delimiters to originalDelimiters
	return joinedText
end join_list
