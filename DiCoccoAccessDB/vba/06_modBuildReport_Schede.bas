Attribute VB_Name = "modBuildReport_Schede"
Option Compare Database
Option Explicit

' Builds rptSchede: a "word-like" catalog report, one record per page,
' medium-size images up top and neatly formatted narrative sections below --
' modeled after a museum catalog "scheda" (similar in spirit to the
' Schede vol.1 PDF). Growing/shrinking text boxes let each page take
' exactly the space its own text needs; FormatDetailScheda (in
' modImageHelpers) hides empty sections and centers whichever images exist.
Public Sub BuildSchedeReport()
    On Error GoTo ErrHandler
    Const TW As Long = 1440

    Dim rpt As Access.Report
    Dim rptName As String
    Dim ctl As Access.Control

    On Error Resume Next
    DoCmd.DeleteObject acReport, "rptSchede"
    On Error GoTo ErrHandler

    Set rpt = CreateReport()
    rptName = rpt.Name
    rpt.RecordSource = "qryOpereOrdinate"
    rpt.Caption = "Catalogo opere - Schede"
    rpt.Width = 7.3 * TW

    On Error Resume Next
    rpt.Printer.Orientation = 1 ' acPRORPortrait
    Err.Clear
    On Error GoTo ErrHandler

    Dim topPos As Long
    topPos = 0.2 * TW

    ' --- Title: Titolo (Anno) ---
    Set ctl = CreateControl(rptName, acTextBox, acDetail, , , 0.15 * TW, topPos, 7 * TW, 0.4 * TW)
    ctl.Name = "txtTitoloAnno"
    ctl.ControlSource = "=[Titolo] & "" ("" & [Anno] & "")"""
    ctl.FontBold = True
    ctl.FontSize = 18
    ctl.CanGrow = True
    ctl.CanShrink = True
    topPos = topPos + 0.45 * TW

    ' --- Subtitle: Intestazione / Numero d'archivio ---
    Set ctl = CreateControl(rptName, acTextBox, acDetail, , , 0.15 * TW, topPos, 7 * TW, 0.25 * TW)
    ctl.Name = "txtSottotitolo"
    ctl.ControlSource = "=""Scheda "" & [Intestazione] & ""  -  n. archivio "" & [NumeroArchivio]"
    ctl.FontItalic = True
    ctl.FontSize = 11
    ctl.ForeColor = RGB(90, 90, 90)
    ctl.CanGrow = True
    ctl.CanShrink = True
    topPos = topPos + 0.3 * TW

    Set ctl = CreateControl(rptName, acLine, acDetail, , , 0.15 * TW, topPos, 7 * TW, 0)
    topPos = topPos + 0.15 * TW

    ' --- Images row (Recto / Verso / Laterale) ---
    ' Positions are recalculated live by FormatDetailScheda; these are just
    ' the design-time defaults.
    Dim imgTop As Long, imgH As Long
    imgTop = topPos
    imgH = 2 * TW

    Set ctl = CreateControl(rptName, acImage, acDetail, , , 0.25 * TW, imgTop, 2 * TW, imgH)
    ctl.Name = "imgRecto": ctl.SizeMode = 3: ctl.BorderStyle = 1

    Set ctl = CreateControl(rptName, acImage, acDetail, , , 2.65 * TW, imgTop, 2 * TW, imgH)
    ctl.Name = "imgVerso": ctl.SizeMode = 3: ctl.BorderStyle = 1

    Set ctl = CreateControl(rptName, acImage, acDetail, , , 5.05 * TW, imgTop, 2 * TW, imgH)
    ctl.Name = "imgLaterale": ctl.SizeMode = 3: ctl.BorderStyle = 1

    ' Hidden bound text boxes feeding the image paths to FormatDetailScheda
    Dim hiddenNames As Variant, hiddenSources As Variant
    hiddenNames = Array("txtImmagineRectoHidden", "txtImmagineVersoHidden", "txtImmagineLateraleHidden")
    hiddenSources = Array("ImmagineRecto", "ImmagineVerso", "ImmagineLaterale")
    Dim k As Integer
    For k = 0 To 2
        Set ctl = CreateControl(rptName, acTextBox, acDetail, , , 0.25 * TW, imgTop + imgH + 0.02 * TW, 2 * TW, 0.05 * TW)
        ctl.Name = hiddenNames(k)
        ctl.ControlSource = hiddenSources(k)
        ctl.Visible = False
    Next k

    topPos = imgTop + imgH + 0.15 * TW

    ' --- Two-column metadata block ---
    Dim leftCol As Variant, rightCol As Variant
    leftCol = Array( _
        Array("Tecnica", "Tecnica"), _
        Array("Dimensioni", "Dimensioni"), _
        Array("Collocazione", "Collocazione"))
    rightCol = Array( _
        Array("SegniRecto", "Segni sul recto"), _
        Array("SegniVerso", "Segni sul verso"), _
        Array("PaginePDF", "Pagine PDF (Schede vol.1)"))

    Dim leftTop As Long, rightTop As Long
    leftTop = topPos
    rightTop = topPos
    leftTop = AddLabeledStack(rptName, leftCol, 0.15 * TW, 3.45 * TW, leftTop)
    rightTop = AddLabeledStack(rptName, rightCol, 3.75 * TW, 3.4 * TW, rightTop)

    topPos = leftTop
    If rightTop > topPos Then topPos = rightTop
    topPos = topPos + 0.1 * TW

    Set ctl = CreateControl(rptName, acLine, acDetail, , , 0.15 * TW, topPos, 7 * TW, 0)
    topPos = topPos + 0.15 * TW

    ' --- Narrative sections (full width, hidden when blank) ---
    Dim narrative As Variant
    narrative = Array( _
        Array("Provenienza", "Provenienza"), _
        Array("EsposizioniPersonali", "Esposizioni personali"), _
        Array("EsposizioniCollettive", "Esposizioni collettive"), _
        Array("Bibliografia", "Bibliografia"), _
        Array("Note", "Note"))

    Dim i As Integer, item As Variant

    For i = 0 To UBound(narrative)
        item = narrative(i)

        Set ctl = CreateControl(rptName, acLabel, acDetail, , , 0.15 * TW, topPos, 7 * TW, 0.22 * TW)
        ctl.Name = "lbl" & item(0)
        ctl.Caption = item(1)
        ctl.FontBold = True
        ctl.FontSize = 10
        ctl.CanShrink = True
        topPos = topPos + 0.24 * TW

        Set ctl = CreateControl(rptName, acTextBox, acDetail, , , 0.15 * TW, topPos, 7 * TW, 0.3 * TW)
        ctl.Name = "txt" & item(0)
        ctl.ControlSource = item(0)
        ctl.FontSize = 10
        ctl.CanGrow = True
        ctl.CanShrink = True
        topPos = topPos + 0.35 * TW + 0.1 * TW
    Next i

    rpt.Section(acDetail).Height = topPos + 0.15 * TW
    rpt.Section(acDetail).OnFormat = "=FormatDetailScheda()"
    rpt.Section(acDetail).ForceNewPage = 1 ' acPageBefore -- one record per page

    DoCmd.Close acReport, rptName, acSaveYes
    DoCmd.Rename "rptSchede", acReport, rptName

    MsgBox "Report 'rptSchede' creato.", vbInformation, "BuildSchedeReport"
    Exit Sub

ErrHandler:
    MsgBox "Errore in BuildSchedeReport: " & Err.Number & " - " & Err.Description, vbCritical, "BuildSchedeReport"
End Sub

' Creates a vertical stack of Label+TextBox pairs in the given horizontal
' band, returning the Y position immediately after the last pair.
Private Function AddLabeledStack(rptName As String, items As Variant, leftX As Long, colW As Long, startTop As Long) As Long
    Const TW As Long = 1440
    Dim ctl As Access.Control
    Dim i As Integer, item As Variant, top As Long
    top = startTop

    For i = 0 To UBound(items)
        item = items(i)

        Set ctl = CreateControl(rptName, acLabel, acDetail, , , leftX, top, colW, 0.2 * TW)
        ctl.Caption = item(1) & ":"
        ctl.FontBold = True
        ctl.FontSize = 9
        top = top + 0.2 * TW

        Set ctl = CreateControl(rptName, acTextBox, acDetail, , , leftX, top, colW, 0.24 * TW)
        ctl.Name = "txt" & item(0) & "Meta"
        ctl.ControlSource = item(0)
        ctl.FontSize = 9
        ctl.CanGrow = True
        ctl.CanShrink = True
        top = top + 0.28 * TW + 0.08 * TW
    Next i

    AddLabeledStack = top
End Function
