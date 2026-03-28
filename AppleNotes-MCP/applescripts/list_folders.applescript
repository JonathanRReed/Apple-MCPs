on run argv
	set accountFilter to ""
	if (count of argv) is greater than 0 then
		set accountFilter to item 1 of argv
	end if
	set jsonItems to {}
	tell application "Notes"
		repeat with acc in accounts
			set accName to my safe_text(name of acc)
			if accountFilter is not "" and accName is not accountFilter then
				-- skip
			else
				set accId to my safe_text(id of acc)
				repeat with fld in folders of acc
					set folderRecord to my folder_json(accId, accName, fld)
					if folderRecord is not "" then
						set end of jsonItems to folderRecord
					end if
				end repeat
			end if
		end repeat
	end tell
	return "{" & quote & "items" & quote & ":[" & my join_list(jsonItems, ",") & "]}"
end run

on folder_json(accountId, accountName, fld)
	set folderId to ""
	set folderName to ""
	set sharedValue to false
	set parentFolderId to ""
	set parentFolderName to ""
	try
		set folderId to my safe_text(id of fld)
	end try
	try
		set folderName to my safe_text(name of fld)
	end try
	try
		set sharedValue to shared of fld
	end try
	try
		if class of container of fld is folder then
			set parentFolderId to my safe_text(id of container of fld)
			set parentFolderName to my safe_text(name of container of fld)
		end if
	end try
	return "{" & ¬
		quote & "folder_id" & quote & ":" & my json_string(folderId) & "," & ¬
		quote & "name" & quote & ":" & my json_string(folderName) & "," & ¬
		quote & "account_id" & quote & ":" & my json_string(accountId) & "," & ¬
		quote & "account_name" & quote & ":" & my json_string(accountName) & "," & ¬
		quote & "parent_folder_id" & quote & ":" & my nullable_json_string(parentFolderId) & "," & ¬
		quote & "parent_folder_name" & quote & ":" & my nullable_json_string(parentFolderName) & "," & ¬
		quote & "shared" & quote & ":" & my json_boolean(sharedValue) & "}"
end folder_json

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
