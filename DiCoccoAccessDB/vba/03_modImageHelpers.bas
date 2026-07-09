Attribute VB_Name = "modImageHelpers"
Option Compare Database
Option Explicit

' Shared image helpers used by frmOpereEdit, rptTabella and rptSchede.
' All entry points here are Public Functions so they can be wired directly
' into event properties as expressions, e.g. OnClick = "=BrowseImageField(...)"
' or OnCurrent/OnFormat = "=RefreshFormImages()" -- this means NONE of the
' generated forms/reports need code written into their own class module, so
' nothing here requires "Trust access to the VBA project object model".

' ---- Config: folder where the DiCoccoImmagini_Schede images live ----

Public Function GetImagesFolder() As String
    Dim v As Variant
    On Error Resume Next
    v = DLookup("ImagesFolder", "Config")
    On Error GoTo 0
    If IsNull(v) Then
        GetImagesFolder = ""
    Else
        GetImagesFolder = CStr(v)
    End If
End Function

' Wire this to a button (e.g. "Imposta cartella immagini...") on any form.
Public Function SetImagesFolder() As Variant
    On Error GoTo ErrHandler
    Dim fd As Object
    Set fd = Application.FileDialog(4) ' msoFileDialogFolderPicker
    fd.Title = "Seleziona la cartella DiCoccoImmagini_Schede"
    If fd.Show = -1 Then
        Dim chosen As String
        chosen = fd.SelectedItems(1)
        CurrentDb.Execute "UPDATE Config SET ImagesFolder = " & Quoted(chosen), dbFailOnError
        MsgBox "Cartella immagini impostata:" & vbCrLf & chosen, vbInformation, "SetImagesFolder"
        On Error Resume Next
        RefreshFormImages
    End If
    Exit Function
ErrHandler:
    MsgBox "Errore in SetImagesFolder: " & Err.Description, vbExclamation, "SetImagesFolder"
End Function

Private Function Quoted(s As String) As String
    Quoted = "'" & Replace(s, "'", "''") & "'"
End Function

' Resolves a path stored in the database (which may be a bare file name, a
' path relative to the images folder, or already an absolute path) to a
' full path on disk.
Public Function ResolveImagePath(p As String) As String
    If Len(Trim$(p)) = 0 Then
        ResolveImagePath = ""
        Exit Function
    End If
    If Mid$(p, 2, 1) = ":" Or Left$(p, 2) = "\\" Then
        ResolveImagePath = p
        Exit Function
    End If
    Dim base As String
    base = GetImagesFolder()
    If Len(base) = 0 Then
        ResolveImagePath = p
    Else
        If Right$(base, 1) = "\" Then
            ResolveImagePath = base & p
        Else
            ResolveImagePath = base & "\" & p
        End If
    End If
End Function

' If the chosen file lives inside the configured images folder, store just
' the relative portion so the database stays portable if the folder moves.
Public Function MakeRelativeIfPossible(fullPath As String) As String
    Dim base As String
    base = GetImagesFolder()
    If Len(base) > 0 Then
        If Left$(LCase$(fullPath), Len(base)) = LCase$(base) Then
            Dim rel As String
            rel = Mid$(fullPath, Len(base) + 1)
            Do While Left$(rel, 1) = "\"
                rel = Mid$(rel, 2)
            Loop
            MakeRelativeIfPossible = rel
            Exit Function
        End If
    End If
    MakeRelativeIfPossible = fullPath
End Function

' Attempts to load rawPath into an Image control; clears it (no error) if
' the path is blank or the file cannot be found.
Public Function TrySetPicture(imgCtl As Access.Control, rawPath As String) As Boolean
    On Error GoTo Fail
    Dim p As String
    p = ResolveImagePath(rawPath)
    If Len(p) = 0 Then
        imgCtl.Picture = ""
        TrySetPicture = False
        Exit Function
    End If
    If Len(Dir(p)) = 0 Then
        imgCtl.Picture = ""
        TrySetPicture = False
        Exit Function
    End If
    imgCtl.Picture = p
    TrySetPicture = True
    Exit Function
Fail:
    On Error Resume Next
    imgCtl.Picture = ""
    TrySetPicture = False
End Function

' ---- Data-entry form (frmOpereEdit) ----

' Wired to frmOpereEdit.OnCurrent
Public Function RefreshFormImages() As Variant
    On Error Resume Next
    Dim frm As Access.Form
    Set frm = Screen.ActiveForm
    If frm Is Nothing Then Exit Function

    TrySetPicture frm("imgRecto"), Nz(frm("ImmagineRecto").Value, "")
    TrySetPicture frm("imgVerso"), Nz(frm("ImmagineVerso").Value, "")
    TrySetPicture frm("imgLaterale"), Nz(frm("ImmagineLaterale").Value, "")
    TrySetPicture frm("imgIll1"), Nz(frm("Illustrazione1").Value, "")
    TrySetPicture frm("imgIll2"), Nz(frm("Illustrazione2").Value, "")
    TrySetPicture frm("imgIll3"), Nz(frm("Illustrazione3").Value, "")
End Function

' Wired to each "Sfoglia..." button: =BrowseImageField("ImmagineRecto","imgRecto")
Public Function BrowseImageField(fieldName As String, ctrlName As String) As Variant
    On Error GoTo ErrHandler
    Dim frm As Access.Form
    Set frm = Screen.ActiveForm
    If frm Is Nothing Then Exit Function

    Dim fd As Object
    Set fd = Application.FileDialog(3) ' msoFileDialogFilePicker
    fd.Title = "Seleziona immagine per " & fieldName
    fd.Filters.Clear
    fd.Filters.Add "Immagini", "*.jpg;*.jpeg;*.png;*.bmp;*.gif;*.tif;*.tiff"
    fd.AllowMultiSelect = False

    Dim startFolder As String
    startFolder = GetImagesFolder()
    If Len(startFolder) > 0 Then fd.InitialFileName = startFolder & "\"

    If fd.Show = -1 Then
        Dim chosen As String
        chosen = fd.SelectedItems(1)
        frm(fieldName).Value = MakeRelativeIfPossible(chosen)
        RefreshFormImages
    End If
    Exit Function
ErrHandler:
    MsgBox "Errore nella selezione immagine: " & Err.Description, vbExclamation, "BrowseImageField"
End Function

' ---- Reports (rptTabella, rptSchede) ----

' Wired to rptTabella's Detail section OnFormat.
Public Function FormatDetailTabella() As Variant
    On Error Resume Next
    Dim rpt As Access.Report
    Set rpt = Screen.ActiveReport
    If rpt Is Nothing Then Exit Function
    TrySetPicture rpt("imgThumb"), Nz(rpt("txtImmagineRectoHidden").Value, "")
End Function

' Wired to rptSchede's Detail section OnFormat. Shows recto/verso/laterale
' side by side, collapsing gaps left by any missing image, and hides
' narrative sections (label + memo) whose underlying field is blank.
Public Function FormatDetailScheda() As Variant
    On Error Resume Next
    Dim rpt As Access.Report
    Set rpt = Screen.ActiveReport
    If rpt Is Nothing Then Exit Function

    Const TW As Long = 1440
    Dim slots(2) As String, ctrlNames(2) As String
    slots(0) = Nz(rpt("txtImmagineRectoHidden").Value, "")
    slots(1) = Nz(rpt("txtImmagineVersoHidden").Value, "")
    slots(2) = Nz(rpt("txtImmagineLateraleHidden").Value, "")
    ctrlNames(0) = "imgRecto"
    ctrlNames(1) = "imgVerso"
    ctrlNames(2) = "imgLaterale"

    Dim imgW As Long, gap As Long, leftStart As Long
    imgW = 2 * TW
    gap = 0.2 * TW
    leftStart = 0.25 * TW

    Dim i As Integer, visibleCount As Integer, curLeft As Long
    Dim hasImg(2) As Boolean

    For i = 0 To 2
        hasImg(i) = TrySetPicture(rpt(ctrlNames(i)), slots(i))
    Next i

    visibleCount = 0
    For i = 0 To 2
        If hasImg(i) Then visibleCount = visibleCount + 1
    Next i

    curLeft = leftStart
    If visibleCount > 0 Then
        ' Center the visible images as a group
        Dim totalW As Long
        totalW = visibleCount * imgW + (visibleCount - 1) * gap
        curLeft = (rpt.Width - totalW) \ 2
        If curLeft < 0 Then curLeft = leftStart
    End If

    For i = 0 To 2
        rpt(ctrlNames(i)).Visible = hasImg(i)
        If hasImg(i) Then
            rpt(ctrlNames(i)).Left = curLeft
            curLeft = curLeft + imgW + gap
        End If
    Next i

    ' Hide empty narrative blocks (label + memo pairs)
    HideIfBlank rpt, "lblProvenienza", "txtProvenienza"
    HideIfBlank rpt, "lblEsposizioniPersonali", "txtEsposizioniPersonali"
    HideIfBlank rpt, "lblEsposizioniCollettive", "txtEsposizioniCollettive"
    HideIfBlank rpt, "lblBibliografia", "txtBibliografia"
    HideIfBlank rpt, "lblNote", "txtNote"
End Function

Private Sub HideIfBlank(rpt As Access.Report, lblName As String, txtName As String)
    On Error Resume Next
    Dim blank As Boolean
    blank = (Len(Trim$(Nz(rpt(txtName).Value, ""))) = 0)
    rpt(lblName).Visible = Not blank
    rpt(txtName).Visible = Not blank
End Sub
