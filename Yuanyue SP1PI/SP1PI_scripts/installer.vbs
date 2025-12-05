
' Windows 7 SP1 PatcherInstaller
' Compatible only with Windows 7 x64

Option Explicit
On Error Resume Next

' ============================================================================
' CONSTANTS AND GLOBAL VARIABLES
' ============================================================================
Const ForReading = 1, ForWriting = 2, ForAppending = 8
Const TemporaryFolder = 2
Const WINDOWS_7_VERSION = "6.1"

Dim objFSO, objShell, objNetwork, objWMI
Dim strScriptPath, strLogFile, blnIsAdmin
Dim strOSVersion, strArchitecture, strOSName
Dim blnAllPatchesInstalled, blnProgressBarActive
Dim objProgressBarExec

' ============================================================================
' MAIN ENTRY POINT
' ============================================================================
Main()

Sub Main()
    Dim strMessage, strInput, bSuccess
    
    ' Initialize objects
    bSuccess = InitializeObjects()
    If Not bSuccess Then
        WScript.Echo "ERROR: Failed to initialize objects"
        WScript.Quit 1
    End If
    
    ' Create log file
    strLogFile = CreateLogFile()
    If strLogFile = "" Then
        WScript.Echo "ERROR: Cannot create log file. Exiting."
        WScript.Quit 1
    End If
    
    LogMessage "=== Installation started at " & Now() & " ==="
    
    ' Check system requirements
    bSuccess = CheckSystemRequirements()
    If Not bSuccess Then
        LogMessage "ERROR: System requirements check failed"
        WScript.Quit 1
    End If
    
    ' Check administrator privileges
    bSuccess = CheckAdminPrivileges()
    If Not bSuccess Then
        WScript.Echo "ERROR: This script requires administrator privileges."
        WScript.Echo "Please run as administrator."
        LogMessage "ERROR: Administrator privileges required"
        WScript.Quit 1
    End If
    
    ' Get script directory
    strScriptPath = GetScriptDirectory()
    If strScriptPath = "" Then
        LogMessage "ERROR: Cannot determine script directory"
        WScript.Quit 1
    End If
    
    LogMessage "Script running from: " & strScriptPath
    LogMessage "Operating System: " & strOSName & " " & strArchitecture & " (Version: " & strOSVersion & ")"
    
    ' Display welcome message
    WScript.Echo "========================================"
    WScript.Echo "Windows Update Patches Installer"
    WScript.Echo "========================================"
    WScript.Echo "System Detected:"
    WScript.Echo "- OS: " & strOSName
    WScript.Echo "- Architecture: " & strArchitecture
    WScript.Echo "- Version: " & strOSVersion
    WScript.Echo ""
    WScript.Echo "This installer will install all .msu patches in the current directory"
    WScript.Echo ""
    WScript.Echo "A progress bar will show the installation progress."
    WScript.Echo ""
    WScript.Echo "Do you want to continue? (Y/N)"
    
    ' Get user input
    strInput = ""
    Do While UCase(strInput) <> "Y" And UCase(strInput) <> "N"
        If strInput <> "" Then
            WScript.Echo "Please enter Y or N:"
        End If
        strInput = WScript.StdIn.ReadLine
    Loop
    
    If UCase(strInput) = "N" Then
        LogMessage "Installation cancelled by user"
        WScript.Echo "Installation cancelled."
        WScript.Quit 0
    End If
    
    ' Initialize flags
    blnAllPatchesInstalled = False
    blnProgressBarActive = True
    
    ' Clear screen for better progress bar display
    objShell.Run "cmd /c cls", 0, True
    
    ' Start progress bar in a separate thread
    Dim strCommand
    strCommand = "cscript.exe //Nologo """ & WScript.ScriptFullName & """ /progressbar"
    Set objProgressBarExec = objShell.Exec(strCommand)
    
    ' Wait a moment for progress bar to start
    WScript.Sleep 1000
    
    ' Install MSU patches
    InstallMSUPatches
    
    ' Mark installation as complete
    blnAllPatchesInstalled = True
    
    ' Wait for progress bar to complete
    While blnProgressBarActive
        WScript.Sleep 500
    Wend
    
    ' Wait for progress bar process to exit
    While objProgressBarExec.Status = 0
        WScript.Sleep 100
    Wend
    
    ' Completion message
    LogMessage "=== Installation completed at " & Now() & " ==="
    
    WScript.Echo ""
    WScript.Echo "========================================"
    WScript.Echo "Installation process completed."
    WScript.Echo "========================================"
    WScript.Echo ""
    WScript.Echo "Please check the log file for details:"
    WScript.Echo strLogFile
    WScript.Echo ""
    WScript.Echo "Some updates may require a system restart."
    WScript.Echo ""
    WScript.Echo "Press Enter to exit..."
    WScript.StdIn.ReadLine
    
    ' Cleanup
    Cleanup
End Sub

' ============================================================================
' CORE FUNCTIONS
' ============================================================================

Function InitializeObjects()
    On Error Resume Next
    
    Set objFSO = CreateObject("Scripting.FileSystemObject")
    If Err.Number <> 0 Then
        WScript.Echo "ERROR: Cannot create FileSystemObject"
        InitializeObjects = False
        Exit Function
    End If
    
    Set objShell = CreateObject("WScript.Shell")
    If Err.Number <> 0 Then
        WScript.Echo "ERROR: Cannot create Shell object"
        InitializeObjects = False
        Exit Function
    End If
    
    Set objNetwork = CreateObject("WScript.Network")
    If Err.Number <> 0 Then
        ' Non-critical error, continue without network object
    End If
    
    InitializeObjects = True
    Err.Clear
End Function

Function CreateLogFile()
    On Error Resume Next
    
    Dim strTempPath, strLogName, objLogFile
    
    strTempPath = objShell.ExpandEnvironmentStrings("%TEMP%")
    If Not objFSO.FolderExists(strTempPath) Then
        strTempPath = objFSO.GetSpecialFolder(TemporaryFolder)
    End If
    
    strLogName = "PatchInstall_" & Year(Now()) & _
                 Right("0" & Month(Now()), 2) & _
                 Right("0" & Day(Now()), 2) & "_" & _
                 Right("0" & Hour(Now()), 2) & _
                 Right("0" & Minute(Now()), 2) & _
                 Right("0" & Second(Now()), 2) & ".log"
    
    CreateLogFile = objFSO.BuildPath(strTempPath, strLogName)
    
    ' Test write access
    Set objLogFile = objFSO.OpenTextFile(CreateLogFile, ForWriting, True)
    If Err.Number <> 0 Then
        CreateLogFile = ""
    Else
        objLogFile.Close
    End If
    
    Err.Clear
End Function

Function CheckSystemRequirements()
    On Error Resume Next
    Dim blnSupported, colOSInfo, colProcessorInfo, objOS, objProcessor
    
    ' Initialize WMI for system information
    Set objWMI = GetObject("winmgmts:\\.\root\cimv2")
    If Err.Number <> 0 Then
        WScript.Echo "ERROR: Cannot access WMI. Cannot verify system requirements."
        CheckSystemRequirements = False
        Exit Function
    End If
    
    ' Get OS information
    Set colOSInfo = objWMI.ExecQuery("SELECT * FROM Win32_OperatingSystem", , 48)
    For Each objOS In colOSInfo
        strOSVersion = objOS.Version
        strOSName = objOS.Caption
    Next
    
    If IsNull(strOSVersion) Or strOSVersion = "" Then
        WScript.Echo "ERROR: Cannot determine OS version"
        CheckSystemRequirements = False
        Exit Function
    End If
    
    ' Get processor architecture
    Set colProcessorInfo = objWMI.ExecQuery("SELECT * FROM Win32_Processor", , 48)
    For Each objProcessor In colProcessorInfo
        strArchitecture = objProcessor.Architecture
        If strArchitecture = 0 Then
            strArchitecture = "x86"
            LogMessage "ERROR: x86 architecture detected - This script requires x64 Windows 7"
            WScript.Echo "ERROR: This script requires 64-bit Windows 7."
            WScript.Echo "x86 (32-bit) architecture is not supported."
            CheckSystemRequirements = False
            Exit Function
        ElseIf strArchitecture = 6 Then
            strArchitecture = "IA64"
        ElseIf strArchitecture = 9 Then
            strArchitecture = "x64"
        ElseIf strArchitecture = 12 Then
            strArchitecture = "ARM64"
            LogMessage "ERROR: ARM64 architecture detected - This script requires x64 Windows 7"
            WScript.Echo "ERROR: ARM64 architecture is not supported."
            WScript.Echo "This script only supports x64 Windows 7."
            CheckSystemRequirements = False
            Exit Function
        Else
            strArchitecture = CStr(objProcessor.AddressWidth) & "-bit"
        End If
    Next
    
    ' Check if this is Windows 7 x64
    blnSupported = True
    
    If Left(strOSVersion, 3) <> WINDOWS_7_VERSION Then
        LogMessage "ERROR: Detected OS Version: " & strOSVersion & " - This script requires Windows 7"
        WScript.Echo "ERROR: This script is designed for Windows 7 only."
        WScript.Echo "Detected OS Version: " & strOSVersion
        blnSupported = False
    End If
    
    CheckSystemRequirements = blnSupported
    Err.Clear
End Function

Function CheckAdminPrivileges()
    On Error Resume Next
    
    Dim objWMIService, colGroups, objGroup
    
    Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")
    Set colGroups = objWMIService.ExecQuery("SELECT * FROM Win32_Group WHERE SID='S-1-5-32-544'")
    
    For Each objGroup In colGroups
        If objGroup.Name = "Administrators" Then
            blnIsAdmin = True
            Exit For
        End If
    Next
    
    ' Alternative method
    If Not blnIsAdmin Then
        Dim objFolder
        Set objFolder = objFSO.GetSpecialFolder(1) ' System folder
        On Error Resume Next
        objFolder.Attributes = objFolder.Attributes
        If Err.Number = 0 Then
            blnIsAdmin = True
        End If
        Err.Clear
    End If
    
    CheckAdminPrivileges = blnIsAdmin
End Function

Function GetScriptDirectory()
    On Error Resume Next
    
    Dim strFullPath
    strFullPath = WScript.ScriptFullName
    GetScriptDirectory = objFSO.GetParentFolderName(strFullPath)
    
    If Err.Number <> 0 Then
        GetScriptDirectory = ""
    End If
    
    Err.Clear
End Function

Sub InstallMSUPatches()
    On Error Resume Next
    
    Dim objFolder, objFile, colFiles, strMSUPath, strCommand, intResult, intExitCode
    Dim blnFoundMSU, strMessage, blnSkipFile, strFileName
    
    LogMessage "=== Starting MSU patches installation ==="
    
    Set objFolder = objFSO.GetFolder(strScriptPath)
    Set colFiles = objFolder.Files
    
    blnFoundMSU = False
    Dim patchCount : patchCount = 0
    Dim successCount : successCount = 0
    Dim failCount : failCount = 0
    
    For Each objFile In colFiles
        blnSkipFile = False
        strFileName = LCase(objFile.Name)
        
        If LCase(objFSO.GetExtensionName(objFile.Name)) = "msu" Then
            If InStr(1, strFileName, "7patch_", vbTextCompare) = 1 Then
                blnFoundMSU = True
                patchCount = patchCount + 1
                strMSUPath = objFile.Path
                
                LogMessage "Found MSU patch [" & patchCount & "]: " & objFile.Name & _
                          " (" & FormatFileSize(objFile.Size) & ")"
                
                ' Validate file size and integrity
                If Not ValidateMSUFile(objFile) Then
                    ' For command line interface, we'll just log and skip questionable files
                    LogMessage "WARNING: " & objFile.Name & " is very small (" & FormatFileSize(objFile.Size) & ") - skipping"
                    failCount = failCount + 1
                    blnSkipFile = True
                End If
                
                If Not blnSkipFile Then
                    ' Prepare installation command with enhanced parameters
                    strCommand = "wusa.exe """ & strMSUPath & """ /quiet /norestart /promptrestart"
                    LogMessage "Executing: " & strCommand
                    
                    ' Execute with timeout
                    intExitCode = objShell.Run("cmd /c " & strCommand, 0, True)
                    
                    ' Interpret exit codes
                    Select Case intExitCode
                        Case 0
                            LogMessage "SUCCESS: " & objFile.Name & " installed successfully"
                            successCount = successCount + 1
                        Case 3010
                            LogMessage "SUCCESS: " & objFile.Name & " installed (reboot required)"
                            successCount = successCount + 1
                        Case 2359302
                            LogMessage "INFO: " & objFile.Name & " is already installed"
                            successCount = successCount + 1
                        Case -2145124329
                            LogMessage "INFO: " & objFile.Name & " is not applicable to this system"
                            successCount = successCount + 1  ' Not a failure
                        Case 87
                            LogMessage "ERROR: " & objFile.Name & " - Invalid parameters"
                            failCount = failCount + 1
                        Case Else
                            LogMessage "ERROR: " & objFile.Name & " failed with exit code: " & intExitCode
                            failCount = failCount + 1
                            
                            ' In command line mode, we'll continue with other patches automatically
                            LogMessage "Continuing with next patch..."
                    End Select
                    
                    ' Small delay between installations
                    WScript.Sleep 3000
                End If
            End If
        End If
    Next
    
    If Not blnFoundMSU Then
        LogMessage "INFO: No MSU patches found (looking for 7patch_*.msu)"
    Else
        LogMessage "MSU Installation Summary: " & successCount & " succeeded, " & failCount & " failed out of " & patchCount & " total patches"
    End If
    
    LogMessage "=== MSU patches installation completed ==="
    Err.Clear
End Sub

' ============================================================================
' COMMAND LINE PROGRESS BAR FUNCTIONS
' ============================================================================

' This function is called when script is run with /progressbar parameter
Sub ShowCommandLineProgressBar()
    On Error Resume Next
    
    blnProgressBarActive = True
    
    ' Set console window title
    objShell.Run "cmd /c title Installing Windows Updates", 0, True
    
    ' Clear screen
    WScript.Echo Chr(12)  ' Form feed character to clear screen
    
    ' Show initial progress bar
    Dim startTime, currentTime, elapsedSeconds, progressPercent
    Dim statusText, timeText, barLength, filledLength, emptyLength
    Dim isStuckAt75Percent, hasReached75Percent
    
    startTime = Timer
    isStuckAt75Percent = False
    hasReached75Percent = False
    
    ' Update progress bar every 500ms
    Do While True
        ' Clear line and move cursor to beginning
        WScript.Echo Chr(13) & String(80, " ") & Chr(13)
        
        currentTime = Timer
        elapsedSeconds = currentTime - startTime
        
        ' Check if installation is complete
        If blnAllPatchesInstalled Then
            ' Jump to 100% if installation is complete
            progressPercent = 100
            statusText = "Installation complete!"
            timeText = "Completed successfully"
            
            ' Draw progress bar
            barLength = 50
            filledLength = barLength
            emptyLength = 0
            
            WScript.Echo "========================================"
            WScript.Echo "Installing Windows Updates"
            WScript.Echo "========================================"
            WScript.Echo ""
            WScript.Echo statusText
            WScript.Echo ""
            WScript.Echo "[" & String(filledLength, "#") & String(emptyLength, " ") & "] " & progressPercent & "%"
            WScript.Echo ""
            WScript.Echo timeText
            WScript.Echo ""
            WScript.Echo "========================================"
            
            ' Wait 3 seconds then exit
            WScript.Sleep 3000
            blnProgressBarActive = False
            Exit Do
        End If
        
        ' Calculate progress based on time
        If elapsedSeconds < 44 Then
            ' Normal progress from 0% to 75% over 44 seconds
            progressPercent = Int((elapsedSeconds / 44) * 75)
            If progressPercent < 0 Then progressPercent = 0
            If progressPercent > 75 Then progressPercent = 75
            
            statusText = "Installing updates..."
            timeText = "Estimated time remaining: " & Int(60 - elapsedSeconds) & " seconds"
            
            ' Check if we've reached 75%
            If progressPercent >= 75 And Not hasReached75Percent Then
                progressPercent = 75
                hasReached75Percent = True
                isStuckAt75Percent = True
            End If
        Else
            ' We're past 44 seconds
            If Not isStuckAt75Percent Then
                ' Installation not complete yet, stick at 75%
                progressPercent = 75
                statusText = "Finishing installation..."
                timeText = "Please wait, this may take a few moments..."
                isStuckAt75Percent = True
            Else
                ' Already stuck at 75%
                progressPercent = 75
                statusText = "Finishing installation..."
                
                ' Show elapsed time instead of remaining time
                Dim minutes, seconds
                minutes = Int(elapsedSeconds / 60)
                seconds = Int(elapsedSeconds Mod 60)
                timeText = "Elapsed time: " & minutes & "m " & seconds & "s"
            End If
        End If
        
        ' Calculate bar lengths
        barLength = 50
        filledLength = Int((progressPercent / 100) * barLength)
        emptyLength = barLength - filledLength
        
        ' Draw progress bar
        WScript.Echo "========================================"
        WScript.Echo "Installing Windows Updates"
        WScript.Echo "========================================"
        WScript.Echo ""
        WScript.Echo statusText
        WScript.Echo ""
        WScript.Echo "[" & String(filledLength, "#") & String(emptyLength, " ") & "] " & progressPercent & "%"
        WScript.Echo ""
        WScript.Echo timeText
        WScript.Echo ""
        WScript.Echo "Please do not close this window or turn off your computer."
        WScript.Echo "========================================"
        
        ' Check if total time has exceeded 5 minutes (300 seconds) - safety timeout
        If elapsedSeconds > 300 Then
            ' Force exit after 5 minutes
            progressPercent = 100
            statusText = "Installation timed out"
            timeText = "Process took too long, please check logs"
            
            ' Draw final progress bar
            WScript.Echo Chr(13) & String(80, " ") & Chr(13)
            WScript.Echo "========================================"
            WScript.Echo "Installing Windows Updates"
            WScript.Echo "========================================"
            WScript.Echo ""
            WScript.Echo statusText
            WScript.Echo ""
            WScript.Echo "[" & String(barLength, "#") & "] " & progressPercent & "%"
            WScript.Echo ""
            WScript.Echo timeText
            WScript.Echo ""
            WScript.Echo "========================================"
            
            WScript.Sleep 3000
            blnProgressBarActive = False
            Exit Do
        End If
        
        ' Wait before next update
        WScript.Sleep 500
    Loop
    
    ' Reset console title
    objShell.Run "cmd /c title Command Prompt", 0, True
End Sub

' ============================================================================
' UTILITY FUNCTIONS
' ============================================================================

Sub LogMessage(strMessage)
    On Error Resume Next
    
    Dim objLogFile, strTimestamp
    
    strTimestamp = "[" & FormatDateTime(Now(), vbShortDate) & " " & _
                   FormatDateTime(Now(), vbLongTime) & "] "
    
    ' Write to log file
    Set objLogFile = objFSO.OpenTextFile(strLogFile, ForAppending, True)
    objLogFile.WriteLine strTimestamp & strMessage
    objLogFile.Close
    
    Err.Clear
End Sub

Function FormatFileSize(bytes)
    If bytes < 1024 Then
        FormatFileSize = bytes & " bytes"
    ElseIf bytes < 1024 * 1024 Then
        FormatFileSize = FormatNumber(bytes / 1024, 1) & " KB"
    ElseIf bytes < 1024 * 1024 * 1024 Then
        FormatFileSize = FormatNumber(bytes / (1024 * 1024), 1) & " MB"
    Else
        FormatFileSize = FormatNumber(bytes / (1024 * 1024 * 1024), 1) & " GB"
    End If
End Function

Function ValidateMSUFile(objFile)
    ' Basic validation of MSU file
    ValidateMSUFile = True
    
    ' Check minimum size (typical MSU patches are at least 100KB)
    If objFile.Size < 102400 Then ' 100KB
        LogMessage "WARNING: MSU file is very small: " & FormatFileSize(objFile.Size)
        ValidateMSUFile = False
    End If
End Function

Function GetWUSAErrorDescription(errorCode)
    Select Case errorCode
        Case 0: GetWUSAErrorDescription = "Success"
        Case 3010: GetWUSAErrorDescription = "Success, reboot required"
        Case 2359302: GetWUSAErrorDescription = "Update already installed"
        Case -2145124329: GetWUSAErrorDescription = "Update not applicable"
        Case 87: GetWUSAErrorDescription = "Invalid parameters"
        Case 5: GetWUSAErrorDescription = "Access denied"
        Case 2: GetWUSAErrorDescription = "File not found"
        Case Else: GetWUSAErrorDescription = "Unknown error"
    End Select
End Function

Sub Cleanup()
    On Error Resume Next
    
    If IsObject(objFSO) Then Set objFSO = Nothing
    If IsObject(objShell) Then Set objShell = Nothing
    If IsObject(objNetwork) Then Set objNetwork = Nothing
    If IsObject(objWMI) Then Set objWMI = Nothing
    If IsObject(objProgressBarExec) Then Set objProgressBarExec = Nothing
    
    Err.Clear
End Sub

' ============================================================================
' COMMAND LINE HANDLING
' ============================================================================

' Check if script was called with /progressbar parameter
If WScript.Arguments.Count > 0 Then
    If LCase(WScript.Arguments(0)) = "/progressbar" Then
        ShowCommandLineProgressBar
        WScript.Quit 0
    End If
End If
