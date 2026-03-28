on run argv
	set targetNoteId to item 1 of argv
		set jsonItems to {}
	tell application "Notes"
		repeat with acc in accounts
			set accName to my safe_text(name of acc)
			set accId to my safe_text(id of acc)
			repeat with fld in folders of acc
				set fldId to my safe_text(id of fld)
				set fldName to my safe_text(name of fld)
				repeat with n in notes of fld
					if my safe_text(id of n) is targetNoteId then
						repeat with a in attachments of n
								set end of jsonItems to "{" & quote & "name" & quote & ":" & my json_string(my safe_text(name of a)) & "}"
							end repeat
							return "{" & quote & "items" & quote & ":[" & my join_list(jsonItems, ",") & "]}"
					end if
				end repeat
			end repeat
		end repeat
	end tell
	return "{" & quote & "items" & quote & ":[]}"
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
