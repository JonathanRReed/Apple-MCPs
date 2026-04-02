on run argv
	set folderName to item 1 of argv
	set accountName to item 2 of argv
	set parentFolderId to item 3 of argv
	tell application "Notes"
		set targetAccount to account accountName
		if parentFolderId is not "" then
			set targetFolder to folder id parentFolderId
			set newFolder to make new folder at targetFolder with properties {name:folderName}
		else
			set newFolder to make new folder at targetAccount with properties {name:folderName}
		end if
		return "{" & quote & "folder" & quote & ":" & my folder_json(newFolder, targetAccount) & "}"
	end tell
end run

on folder_json(fld, acc)
	set folderId to my safe_text(id of fld)
	set folderName to my safe_text(name of fld)
	set accountId to my safe_text(id of acc)
	set accountName to my safe_text(name of acc)
	return "{" & quote & "folder_id" & quote & ":" & my json_string(folderId) & "," & quote & "name" & quote & ":" & my json_string(folderName) & "," & quote & "account_id" & quote & ":" & my json_string(accountId) & "," & quote & "account_name" & quote & ":" & my json_string(accountName) & "," & quote & "parent_folder_id" & quote & ":null," & quote & "parent_folder_name" & quote & ":null," & quote & "shared" & quote & ":false}"
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
