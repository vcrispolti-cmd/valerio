Attribute VB_Name = "modBuildForm_Edit"
Option Compare Database
Option Explicit

' Programmatically builds frmOpereEdit: a single-form data-entry view bound
' to Opere, exposing every field (including the six image slots with
' Browse buttons). Safe to re-run.
Public Sub BuildEditForm()
    On Error GoTo ErrHandler
    Const TW As Long = 1440

    Dim frm As Access.Form
    Dim frmName As String
    Dim ctl As Access.Control

    On Error Resume Next
    DoCmd.DeleteObject acForm, "frmOpereEdit"
    On Error GoTo ErrHandler

    Set frm = CreateForm()
    frmName = frm.Name
    frm.RecordSource = "Opere"
    frm.Caption = "Schede opere - Francesco Di Cocco"
    frm.DefaultView = 0        ' Single Form
    frm.NavigationButtons = True
    frm.RecordSelectors = True
    frm.ScrollBars = 2         ' Vertical only
    frm.Width = 7 * TW

    Dim topPos As Long
    topPos = 0.15 * TW

    ' --- Toolbar-ish buttons at the very top ---
    Set ctl = CreateControl(frmName, acCommandButton, acDetail, , , 0.15 * TW, topPos, 2.2 * TW, 0.28 * TW)
    ctl.Caption = "Imposta cartella immagini..."
    ctl.OnClick = "=SetImagesFolder()"

    Set ctl = CreateControl(frmName, acCommandButton, acDetail, , , 2.5 * TW, topPos, 1.6 * TW, 0.28 * TW)
    ctl.Caption = "Aggiorna immagini"
    ctl.OnClick = "=RefreshFormImages()"

    topPos = topPos + 0.28 * TW + 0.2 * TW

    ' --- Image blocks: 6 slots, 3 per row ---
    Dim imgFields As Variant
    imgFields = Array( _
        Array("ImmagineRecto", "imgRecto", "Recto"), _
        Array("ImmagineVerso", "imgVerso", "Verso"), _
        Array("ImmagineLaterale", "imgLaterale", "Laterale"), _
        Array("Illustrazione1", "imgIll1", "Illustrazione 1"), _
        Array("Illustrazione2", "imgIll2", "Illustrazione 2"), _
        Array("Illustrazione3", "imgIll3", "Illustrazione 3"))

    Dim blockW As Long, blockGap As Long, imgH As Long
    blockW = 1.95 * TW
    blockGap = 0.15 * TW
    imgH = 1.3 * TW

    Dim i As Integer, col As Integer, rowIdx As Integer
    Dim leftPos As Long, rowTop As Long
    Dim fld As Variant

    For i = 0 To UBound(imgFields)
        fld = imgFields(i)
        col = i Mod 3
        rowIdx = i \ 3
        leftPos = 0.15 * TW + col * (blockW + blockGap)
        rowTop = topPos + rowIdx * (imgH + 0.75 * TW)

        Set ctl = CreateControl(frmName, acLabel, acDetail, , , leftPos, rowTop, blockW, 0.2 * TW)
        ctl.Caption = fld(2)
        ctl.FontBold = True

        Set ctl = CreateControl(frmName, acImage, acDetail, , , leftPos, rowTop + 0.22 * TW, blockW, imgH)
        ctl.Name = fld(1)
        ctl.SizeMode = 3 ' acOLESizeZoom
        ctl.BorderStyle = 1

        Set ctl = CreateControl(frmName, acTextBox, acDetail, , , leftPos, rowTop + 0.22 * TW + imgH + 0.03 * TW, blockW, 0.2 * TW)
        ctl.Name = "txt" & fld(0)
        ctl.ControlSource = fld(0)
        ctl.FontSize = 7

        Set ctl = CreateControl(frmName, acCommandButton, acDetail, , , leftPos, rowTop + 0.22 * TW + imgH + 0.25 * TW, blockW, 0.22 * TW)
        ctl.Caption = "Sfoglia..."
        ctl.OnClick = "=BrowseImageField(""" & fld(0) & """,""" & fld(1) & """)"
    Next i

    topPos = topPos + 2 * (imgH + 0.75 * TW) + 0.15 * TW

    ' --- Data field grid ---
    ' Kind: 0 = single line, 1 = small memo, 2 = tall memo
    Dim flds As Variant
    flds = Array( _
        Array("NumeroScheda", "N. scheda", 0), _
        Array("Intestazione", "Scheda (intestazione)", 0), _
        Array("Titolo", "Titolo", 0), _
        Array("Anno", "Anno", 0), _
        Array("NumeroArchivio", "Numero d'archivio", 0), _
        Array("Tecnica", "Tecnica", 0), _
        Array("Dimensioni", "Dimensioni", 0), _
        Array("SegniRecto", "Segni sul recto", 1), _
        Array("SegniVerso", "Segni sul verso", 1), _
        Array("Collocazione", "Collocazione", 0), _
        Array("Provenienza", "Provenienza", 1), _
        Array("EsposizioniPersonali", "Esposizioni personali", 2), _
        Array("EsposizioniCollettive", "Esposizioni collettive", 2), _
        Array("Bibliografia", "Bibliografia", 2), _
        Array("Note", "Note", 2), _
        Array("PaginePDF", "Pagine PDF", 0), _
        Array("TestoIntegrale", "Testo integrale scheda (originale)", 2))

    Dim labelW As Long, boxLeft As Long, boxW As Long, h As Long
    labelW = 1.9 * TW
    boxLeft = 0.15 * TW + labelW + 0.1 * TW
    boxW = 4.6 * TW

    Dim rec As Variant
    For i = 0 To UBound(flds)
        rec = flds(i)
        Select Case rec(2)
            Case 0: h = 0.26 * TW
            Case 1: h = 0.6 * TW
            Case 2: h = 1.3 * TW
        End Select

        Set ctl = CreateControl(frmName, acLabel, acDetail, , , 0.15 * TW, topPos, labelW, 0.22 * TW)
        ctl.Caption = rec(1)

        Set ctl = CreateControl(frmName, acTextBox, acDetail, , , boxLeft, topPos, boxW, h)
        ctl.Name = "txt" & rec(0)
        ctl.ControlSource = rec(0)
        If rec(2) > 0 Then ctl.ScrollBars = 2 ' vertical
        If rec(0) = "NumeroScheda" Then
            ctl.Locked = True
            ctl.Enabled = False
        End If

        topPos = topPos + h + 0.12 * TW
    Next i

    frm.OnCurrent = "=RefreshFormImages()"
    frm.Section(acDetail).Height = topPos + 0.2 * TW

    DoCmd.Close acForm, frmName, acSaveYes
    DoCmd.Rename "frmOpereEdit", acForm, frmName

    MsgBox "Form 'frmOpereEdit' creato.", vbInformation, "BuildEditForm"
    Exit Sub

ErrHandler:
    MsgBox "Errore in BuildEditForm: " & Err.Number & " - " & Err.Description, vbCritical, "BuildEditForm"
End Sub
