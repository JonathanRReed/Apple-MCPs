on run argv
	set accountFilter to ""
	set folderFilter to ""
	if (count of argv) > 0 then set accountFilter to item 1 of argv
	if (count of argv) > 1 then set folderFilter to item 2 of argv
	set jsonItems to {}
	tell application "Notes"
		repeat with acc in accounts
			set accName to my safe_text(name of acc)
			set accId to my safe_text(id of acc)
			if accountFilter is not "" and accName is not accountFilter then
				-- skip
			else
				repeat with fld in folders of acc
					set fldId to my safe_text(id of fld)
					set fldName to my safe_text(name of fld)
					if folderFilter is not "" and fldId is not folderFilter then
						-- skip
					else
						repeat with n in notes of fld
							set end of jsonItems to my note_json(accId, accName, fldId, fldName, n)
						end repeat
					end if
				end repeat
			end if
		end repeat
	end tell
	return "{" & quote & "items" & quote & ":[" & my join_list(jsonItems, ",") & "]}"
end run

on note_json(accountId, accountName, folderId, folderName, n)
	set noteId to my safe_text(id of n)
	set titleText to ""
	set plainText to ""
	set createdEpoch to 0
	set modifiedEpoch to 0
		set sharedValue to false
		set attachmentCount to 0
		try
			set titleText to my safe_text(name of n)
		end try
	try
		set plainText to my safe_text(plaintext of n)
	end try
	try
		set createdEpoch to my date_to_epoch(creation date of n)
	end try
	try
		set modifiedEpoch to my date_to_epoch(modification date of n)
	end try
		try
			set sharedValue to shared of n
		end try
	try
		set attachmentCount to count of attachments of n
	end try
	set noteJson to "{" & ¬
		quote & "note_id" & quote & ":" & my json_string(noteId) & "," & ¬
		quote & "title" & quote & ":" & my json_string(titleText) & "," & ¬
		quote & "account_id" & quote & ":" & my json_string(accountId) & "," & ¬
		quote & "account_name" & quote & ":" & my json_string(accountName) & "," & ¬
		quote & "folder_id" & quote & ":" & my json_string(folderId) & "," & ¬
		quote & "folder_name" & quote & ":" & my json_string(folderName) & "," & ¬
		quote & "created_epoch" & quote & ":" & createdEpoch & "," & ¬
		quote & "modified_epoch" & quote & ":" & modifiedEpoch & "," & ¬
			quote & "shared" & quote & ":" & my json_boolean(sharedValue) & "," & ¬
		quote & "attachment_count" & quote & ":" & attachmentCount & "," & ¬
		quote & "plaintext" & quote & ":" & my json_string(plainText) & "}"
	return noteJson
end note_json

on date_to_epoch(dateValue)
	set epochDate to current date
	set year of epochDate to 1970
	set month of epochDate to January
	set day of epochDate to 1
	set time of epochDate to 0
	return (dateValue - epochDate) as integer
end date_to_epoch

on safe_text(valueText)
	try
		return valueText as text
	on error
		return ""
	end try
end safe_text

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
