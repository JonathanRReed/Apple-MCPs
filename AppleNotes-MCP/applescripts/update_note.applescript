on run argv
	set targetNoteId to item 1 of argv
	set titleText to item 2 of argv
	set bodyHtml to item 3 of argv
	set folderId to item 4 of argv
	set tagsCsv to item 5 of argv
	tell application "Notes"
		try
			set noteRef to note id targetNoteId
		on error
			return "{" & quote & "found" & quote & ":false}"
		end try
		set noteInfo to my note_info(noteRef)
		set accountId to item 2 of noteInfo
		set accountName to item 3 of noteInfo
		set resolvedFolderId to item 4 of noteInfo
		set folderName to item 5 of noteInfo
		if bodyHtml is not "" or tagsCsv is not "" then
			if bodyHtml is not "" then
				set noteBody to bodyHtml
			else
				set noteBody to my safe_text(body of noteRef)
			end if
			set body of noteRef to my compose_note_body(noteBody, tagsCsv)
		end if
		if folderId is not "" then
			set targetFolderInfo to my find_folder_info(folderId)
			if targetFolderInfo is missing value then error "Can't get folder '" & folderId & "'."
			set targetFolder to item 1 of targetFolderInfo
			set accountId to item 2 of targetFolderInfo
			set accountName to item 3 of targetFolderInfo
			set resolvedFolderId to folderId
			set folderName to item 4 of targetFolderInfo
			move noteRef to targetFolder
		end if
		if titleText is not "" then set name of noteRef to titleText
		return "{" & quote & "note" & quote & ":" & my note_json(accountId, accountName, resolvedFolderId, folderName, noteRef) & "}"
	end tell
end run

on find_folder_info(targetFolderId)
	tell application "Notes"
		try
			set fld to folder id targetFolderId
		on error
			return missing value
		end try
		set accountId to ""
		set accountName to ""
		try
			set parentAccount to container of fld
			set accountId to my safe_text(id of parentAccount)
			set accountName to my safe_text(name of parentAccount)
		end try
		return {fld, accountId, accountName, my safe_text(name of fld)}
	end tell
	return missing value
end find_folder_info

on note_info(noteRef)
	tell application "Notes"
		set accountId to ""
		set accountName to ""
		set parentFolder to container of noteRef
		set folderId to my safe_text(id of parentFolder)
		set folderName to my safe_text(name of parentFolder)
		try
			set parentAccount to container of parentFolder
			set accountId to my safe_text(id of parentAccount)
			set accountName to my safe_text(name of parentAccount)
		end try
		return {noteRef, accountId, accountName, folderId, folderName}
	end tell
	return missing value
end note_info

on compose_note_body(bodyHtml, tagsCsv)
	set noteBody to bodyHtml
	if tagsCsv is not "" then
		set noteBody to noteBody & "<div><br></div><div>" & my tags_html(tagsCsv) & "</div>"
	end if
	return noteBody
end compose_note_body

on tags_html(tagsCsv)
	set AppleScript's text item delimiters to ","
	set tagItems to text items of tagsCsv
	set AppleScript's text item delimiters to ""
	set htmlTags to {}
	repeat with tagItem in tagItems
		set cleanTag to my safe_text(tagItem)
		if cleanTag is not "" then
			set end of htmlTags to "#" & cleanTag
		end if
	end repeat
	return my join_list(htmlTags, " ")
end tags_html

on note_json(accountId, accountName, folderId, folderName, n)
	set noteId to my safe_text(id of n)
	set titleText to ""
	set bodyHtml to ""
	set plainText to ""
	set sharedValue to false
	set attachmentCount to 0
	try
		set titleText to my safe_text(name of n)
	end try
	try
		set bodyHtml to my safe_text(body of n)
	end try
	try
		set plainText to my safe_text(plaintext of n)
	end try
	try
		set sharedValue to shared of n
	end try
	try
		set attachmentCount to count of attachments of n
	end try
	return "{" & ¬
		quote & "note_id" & quote & ":" & my json_string(noteId) & "," & ¬
		quote & "title" & quote & ":" & my json_string(titleText) & "," & ¬
		quote & "account_id" & quote & ":" & my json_string(accountId) & "," & ¬
		quote & "account_name" & quote & ":" & my json_string(accountName) & "," & ¬
		quote & "folder_id" & quote & ":" & my json_string(folderId) & "," & ¬
		quote & "folder_name" & quote & ":" & my json_string(folderName) & "," & ¬
		quote & "created_epoch" & quote & ":0," & ¬
		quote & "modified_epoch" & quote & ":0," & ¬
		quote & "password_protected" & quote & ":false," & ¬
		quote & "shared" & quote & ":" & my json_boolean(sharedValue) & "," & ¬
		quote & "attachment_count" & quote & ":" & attachmentCount & "," & ¬
		quote & "plaintext" & quote & ":" & my json_string(plainText) & "," & ¬
		quote & "body_html" & quote & ":" & my json_string(bodyHtml) & "," & ¬
		quote & "attachments" & quote & ":[]}"
end note_json

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
