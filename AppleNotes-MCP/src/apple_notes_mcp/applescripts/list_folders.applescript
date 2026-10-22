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
				set jsonItems to jsonItems & my account_folders_json(accId, accName, acc)
			end if
		end repeat
	end tell
	return "{" & quote & "items" & quote & ":[" & my join_list(jsonItems, ",") & "]}"
end run

on account_folders_json(accountId, accountName, acc)
	-- Read each property for every folder of the account in one Apple Event,
	-- instead of several events per folder. The id list is read again at the
	-- end; if the folders changed in between, the columns may not line up,
	-- so retry.
	repeat 3 times
		try
			tell application "Notes"
				set folderIds to id of folders of acc
				if (count of folderIds) is 0 then return {}
				set folderNames to name of folders of acc
				set folderSharedValues to shared of folders of acc
				set parentClasses to class of container of folders of acc
				set parentIds to id of container of folders of acc
				set parentNames to name of container of folders of acc
				set folderIdsAfter to id of folders of acc
				-- Compare inside Notes' context, where `folder` is its folder class.
				set parentIsFolderFlags to {}
				repeat with parentClass in parentClasses
					set end of parentIsFolderFlags to ((contents of parentClass) is folder)
				end repeat
			end tell
			set folderCount to count of folderIds
			set columnsMatch to (count of folderNames) is folderCount and (count of folderSharedValues) is folderCount and (count of parentClasses) is folderCount and (count of parentIds) is folderCount and (count of parentNames) is folderCount
			considering case
				set idsStable to folderIdsAfter = folderIds
			end considering
			if columnsMatch and idsStable then
				set folderItems to {}
				repeat with i from 1 to folderCount
					set end of folderItems to my folder_json_from_values(accountId, accountName, item i of folderIds, item i of folderNames, item i of folderSharedValues, item i of parentIsFolderFlags, item i of parentIds, item i of parentNames)
				end repeat
				return folderItems
			end if
		end try
	end repeat
	-- Fall back to reading folder by folder.
	set folderItems to {}
	tell application "Notes"
		repeat with fld in folders of acc
			set folderRecord to my folder_json(accountId, accountName, fld)
			if folderRecord is not "" then
				set end of folderItems to folderRecord
			end if
		end repeat
	end tell
	return folderItems
end account_folders_json

on folder_json_from_values(accountId, accountName, rawFolderId, rawFolderName, rawSharedValue, parentIsFolder, rawParentId, rawParentName)
	set folderId to ""
	set folderName to ""
	set sharedValue to false
	set parentFolderId to ""
	set parentFolderName to ""
	try
		set folderId to my safe_text(rawFolderId)
	end try
	try
		set folderName to my safe_text(rawFolderName)
	end try
	try
		set sharedValue to rawSharedValue
	end try
	try
		if parentIsFolder then
			set parentFolderId to my safe_text(rawParentId)
			set parentFolderName to my safe_text(rawParentName)
		end if
	end try
	return my folder_record_json(accountId, accountName, folderId, folderName, sharedValue, parentFolderId, parentFolderName)
end folder_json_from_values

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
		tell application "Notes"
			set parentIsFolder to (class of container of fld is folder)
			if parentIsFolder then
				set rawParentId to id of container of fld
				set rawParentName to name of container of fld
			end if
		end tell
		if parentIsFolder then
			set parentFolderId to my safe_text(rawParentId)
			set parentFolderName to my safe_text(rawParentName)
		end if
	end try
	return my folder_record_json(accountId, accountName, folderId, folderName, sharedValue, parentFolderId, parentFolderName)
end folder_json

on folder_record_json(accountId, accountName, folderId, folderName, sharedValue, parentFolderId, parentFolderName)
	return "{" & ¬
		quote & "folder_id" & quote & ":" & my json_string(folderId) & "," & ¬
		quote & "name" & quote & ":" & my json_string(folderName) & "," & ¬
		quote & "account_id" & quote & ":" & my json_string(accountId) & "," & ¬
		quote & "account_name" & quote & ":" & my json_string(accountName) & "," & ¬
		quote & "parent_folder_id" & quote & ":" & my nullable_json_string(parentFolderId) & "," & ¬
		quote & "parent_folder_name" & quote & ":" & my nullable_json_string(parentFolderName) & "," & ¬
		quote & "shared" & quote & ":" & my json_boolean(sharedValue) & "}"
end folder_record_json

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
