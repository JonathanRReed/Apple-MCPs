use framework "Foundation"
use scripting additions

on run argv
	set targetNoteId to item 1 of argv
	set foundJson to ""
	tell application "Notes"
		repeat with acc in accounts
			set accName to my safe_text(name of acc)
			set accId to my safe_text(id of acc)
			repeat with fld in folders of acc
				set fldId to my safe_text(id of fld)
				set fldName to my safe_text(name of fld)
				repeat with n in notes of fld
					if my safe_text(id of n) is targetNoteId then
						set foundJson to "{" & quote & "found" & quote & ":true," & quote & "note" & quote & ":" & my note_json(accId, accName, fldId, fldName, n, true) & "}"
						exit repeat
					end if
				end repeat
				if foundJson is not "" then exit repeat
			end repeat
			if foundJson is not "" then exit repeat
		end repeat
	end tell
	if foundJson is "" then
		return "{" & quote & "found" & quote & ":false}"
	end if
	return foundJson
end run

on note_json(accountId, accountName, folderId, folderName, n, includeBody)
	tell application "Notes" to set rawNoteId to id of n
	set noteId to my safe_text(rawNoteId)
	set titleText to ""
	set bodyHtml to ""
	set plainText to ""
	set createdEpoch to 0
	set modifiedEpoch to 0
		set sharedValue to false
		try
			tell application "Notes" to set rawTitleText to name of n
			set titleText to my safe_text(rawTitleText)
		end try
	try
		tell application "Notes" to set rawBodyHtml to body of n
		set bodyHtml to my safe_text(rawBodyHtml)
	end try
	try
		tell application "Notes" to set rawPlainText to plaintext of n
		set plainText to my safe_text(rawPlainText)
	end try
	try
		tell application "Notes" to set rawCreatedDate to creation date of n
		set createdEpoch to my date_to_epoch(rawCreatedDate)
	end try
	try
		tell application "Notes" to set rawModifiedDate to modification date of n
		set modifiedEpoch to my date_to_epoch(rawModifiedDate)
	end try
		try
			tell application "Notes" to set sharedValue to shared of n
		end try
	return "{" & ¬
		quote & "note_id" & quote & ":" & my json_string(noteId) & "," & ¬
		quote & "title" & quote & ":" & my json_string(titleText) & "," & ¬
		quote & "account_id" & quote & ":" & my json_string(accountId) & "," & ¬
		quote & "account_name" & quote & ":" & my json_string(accountName) & "," & ¬
		quote & "folder_id" & quote & ":" & my json_string(folderId) & "," & ¬
		quote & "folder_name" & quote & ":" & my json_string(folderName) & "," & ¬
		quote & "created_epoch" & quote & ":" & createdEpoch & "," & ¬
		quote & "modified_epoch" & quote & ":" & modifiedEpoch & "," & ¬
			quote & "shared" & quote & ":" & my json_boolean(sharedValue) & "," & ¬
		quote & "attachment_count" & quote & ":0," & ¬
		quote & "plaintext" & quote & ":" & my json_string(plainText) & "," & ¬
		quote & "body_html" & quote & ":" & my json_string(bodyHtml) & "," & ¬
		quote & "attachments" & quote & ":[]}"
end note_json

on date_to_epoch(dateValue)
	-- NSDate's epoch is an absolute UTC instant, independent of local timezone.
	set cocoaDate to current application's NSDate's dateWithTimeInterval:0 sinceDate:dateValue
	return cocoaDate's timeIntervalSince1970() as integer
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
