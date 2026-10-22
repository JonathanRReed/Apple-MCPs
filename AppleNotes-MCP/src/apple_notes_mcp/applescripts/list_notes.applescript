use framework "Foundation"
use scripting additions

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
						set jsonItems to jsonItems & my folder_notes_json(accId, accName, fldId, fldName, fld)
					end if
				end repeat
			end if
		end repeat
	end tell
	return "{" & quote & "items" & quote & ":[" & my join_list(jsonItems, ",") & "]}"
end run

on folder_notes_json(accountId, accountName, folderId, folderName, fld)
	-- Read each property for every note of the folder in one Apple Event.
	-- Reading per note costs one event per property per note, which timed out
	-- on large stores. The id list is read again at the end; if the folder
	-- changed in between, the columns may not line up, so retry.
	repeat 3 times
		try
			tell application "Notes"
				set noteIds to id of every note of fld
				if (count of noteIds) is 0 then return {}
				set noteTitles to name of every note of fld
				set notePlainTexts to plaintext of every note of fld
				set noteCreatedDates to creation date of every note of fld
				set noteModifiedDates to modification date of every note of fld
				set noteSharedValues to shared of every note of fld
				set noteAttachmentIds to id of every attachment of every note of fld
				set noteIdsAfter to id of every note of fld
			end tell
			set noteCount to count of noteIds
			set columnsMatch to (count of noteTitles) is noteCount and (count of notePlainTexts) is noteCount and (count of noteCreatedDates) is noteCount and (count of noteModifiedDates) is noteCount and (count of noteSharedValues) is noteCount and (count of noteAttachmentIds) is noteCount
			considering case
				set idsStable to noteIdsAfter = noteIds
			end considering
			if columnsMatch and idsStable then
				set folderItems to {}
				repeat with i from 1 to noteCount
					set end of folderItems to my note_json_from_values(accountId, accountName, folderId, folderName, item i of noteIds, item i of noteTitles, item i of notePlainTexts, item i of noteCreatedDates, item i of noteModifiedDates, item i of noteSharedValues, item i of noteAttachmentIds)
				end repeat
				return folderItems
			end if
		end try
	end repeat
	-- Fall back to reading note by note.
	set folderItems to {}
	tell application "Notes"
		repeat with n in notes of fld
			set end of folderItems to my note_json(accountId, accountName, folderId, folderName, n)
		end repeat
	end tell
	return folderItems
end folder_notes_json

on note_json_from_values(accountId, accountName, folderId, folderName, rawNoteId, rawTitleText, rawPlainText, rawCreatedDate, rawModifiedDate, rawSharedValue, rawAttachmentIds)
	set noteId to my safe_text(rawNoteId)
	set titleText to ""
	set plainText to ""
	set createdEpoch to 0
	set modifiedEpoch to 0
	set sharedValue to false
	set attachmentCount to 0
	try
		set titleText to my safe_text(rawTitleText)
	end try
	try
		set plainText to my safe_text(rawPlainText)
	end try
	try
		set createdEpoch to my date_to_epoch(rawCreatedDate)
	end try
	try
		set modifiedEpoch to my date_to_epoch(rawModifiedDate)
	end try
	try
		set sharedValue to rawSharedValue
	end try
	try
		set attachmentCount to count of rawAttachmentIds
	end try
	return my note_record_json(accountId, accountName, folderId, folderName, noteId, titleText, plainText, createdEpoch, modifiedEpoch, sharedValue, attachmentCount)
end note_json_from_values

on note_json(accountId, accountName, folderId, folderName, n)
	tell application "Notes" to set rawNoteId to id of n
	set noteId to my safe_text(rawNoteId)
	set titleText to ""
	set plainText to ""
	set createdEpoch to 0
	set modifiedEpoch to 0
		set sharedValue to false
		set attachmentCount to 0
		try
			tell application "Notes" to set rawTitleText to name of n
			set titleText to my safe_text(rawTitleText)
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
	try
		tell application "Notes" to set attachmentCount to count of attachments of n
	end try
	return my note_record_json(accountId, accountName, folderId, folderName, noteId, titleText, plainText, createdEpoch, modifiedEpoch, sharedValue, attachmentCount)
end note_json

on note_record_json(accountId, accountName, folderId, folderName, noteId, titleText, plainText, createdEpoch, modifiedEpoch, sharedValue, attachmentCount)
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
		quote & "attachment_count" & quote & ":" & attachmentCount & "," & ¬
		quote & "plaintext" & quote & ":" & my json_string(plainText) & "}"
end note_record_json

on date_to_epoch(dateValue)
	-- NSDate's epoch is an absolute UTC instant, independent of local timezone.
	set cocoaDate to current application's NSDate's dateWithTimeInterval:0 sinceDate:dateValue
	-- AppleScript numeric text is locale-sensitive and its integer range is too small.
	return ((current application's NSNumber's numberWithDouble:(cocoaDate's timeIntervalSince1970()))'s stringValue()) as text
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
