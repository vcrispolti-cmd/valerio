Attribute VB_Name = "modBuildReport_Tabella"
Option Compare Database
Option Explicit

' Builds rptTabella: a landscape, grid-style report mirroring the original
' Excel layout, one row per record, with a recto thumbnail per row.
Public Sub BuildTabellaReport()
    On Error GoTo ErrHandler
    Const TW As Long = 1440

    Dim rpt As Access.Report
    Dim rptName As String
    Dim ctl As Access.Control

    On Error Resume Next
    DoCmd.DeleteObject acReport, "rptTabella"
    On Error GoTo ErrHandler

    Set rpt = CreateReport()
    rptName = rpt.Name
    rpt.RecordSource = "qryOpereOrdinate"
    rpt.Caption = "Catalogo opere - Tabella"
    rpt.Width = 10.2 * TW

    On Error Resume Next
    rpt.Printer.Orientation = 2 ' acPRORLandscape
    Err.Clear
    On Error GoTo ErrHandler

    ' --- Column layout shared by Page Header and Detail ---
    ' name, caption, left(in), width(in)
    Dim cols As Variant
    cols = Array( _
        Array("NumeroScheda", "N.", 1.15, 0.4), _
        Array("Intestazione", "Scheda", 1.6, 0.9), _
        Array("Titolo", "Titolo", 2.55, 1.95), _
        Array("Anno", "Anno", 4.55, 0.55), _
        Array("Tecnica", "Tecnica", 5.15, 1.75), _
        Array("Dimensioni", "Dimensioni", 6.95, 0.95), _
        Array("Collocazione", "Collocazione", 7.95, 1.7), _
        Array("PaginePDF", "Pag. PDF", 9.7, 0.45))

    ' --- Report Header ---
    Set ctl = CreateControl(rptName, acLabel, acHeader, , , 0.15 * TW, 0.1 * TW, 6 * TW, 0.3 * TW)
    ctl.Caption = "Francesco Di Cocco - Catalogo delle opere (1913-1934)"
    ctl.FontBold = True
    ctl.FontSize = 14
    rpt.Section(acHeader).Height = 0.5 * TW

    ' --- Page Header: column titles + thumbnail header ---
    Set ctl = CreateControl(rptName, acLabel, acPageHeader, , , 0.15 * TW, 0.05 * TW, 0.9 * TW, 0.2 * TW)
    ctl.Caption = "Miniatura"
    ctl.FontBold = True
    ctl.FontSize = 8

    Dim i As Integer, c As Variant
    For i = 0 To UBound(cols)
        c = cols(i)
        Set ctl = CreateControl(rptName, acLabel, acPageHeader, , , c(2) * TW, 0.05 * TW, c(3) * TW, 0.2 * TW)
        ctl.Caption = c(1)
        ctl.FontBold = True
        ctl.FontSize = 8
    Next i

    Set ctl = CreateControl(rptName, acLine, acPageHeader, , , 0.1 * TW, 0.3 * TW, 10 * TW, 0)
    rpt.Section(acPageHeader).Height = 0.4 * TW

    ' --- Detail section ---
    Dim detailH As Long
    detailH = 0.9 * TW

    Set ctl = CreateControl(rptName, acImage, acDetail, , , 0.15 * TW, 0.05 * TW, 0.9 * TW, 0.8 * TW)
    ctl.Name = "imgThumb"
    ctl.SizeMode = 3 ' acOLESizeZoom
    ctl.BorderStyle = 1

    ' Hidden bound text box supplying the recto path to FormatDetailTabella
    Set ctl = CreateControl(rptName, acTextBox, acDetail, , , 0.15 * TW, 0.85 * TW, 0.9 * TW, 0.05 * TW)
    ctl.Name = "txtImmagineRectoHidden"
    ctl.ControlSource = "ImmagineRecto"
    ctl.Visible = False

    For i = 0 To UBound(cols)
        c = cols(i)
        Set ctl = CreateControl(rptName, acTextBox, acDetail, , , c(2) * TW, 0.05 * TW, c(3) * TW, detailH - 0.1 * TW)
        ctl.Name = "txt" & c(0)
        ctl.ControlSource = c(0)
        ctl.FontSize = 8
        ctl.CanGrow = False
        ctl.CanShrink = False
        ctl.TopMargin = 0
    Next i

    Set ctl = CreateControl(rptName, acLine, acDetail, , , 0.1 * TW, detailH - 0.02 * TW, 10 * TW, 0)

    rpt.Section(acDetail).Height = detailH
    rpt.Section(acDetail).OnFormat = "=FormatDetailTabella()"

    ' --- Page Footer: page numbers ---
    Set ctl = CreateControl(rptName, acTextBox, acPageFooter, , , 8.5 * TW, 0.05 * TW, 1.6 * TW, 0.2 * TW)
    ctl.ControlSource = "=""Pag. "" & [Page] & "" di "" & [Pages]"
    ctl.Name = "txtPagina"
    rpt.Section(acPageFooter).Height = 0.3 * TW

    ' --- Report Footer: total count ---
    Set ctl = CreateControl(rptName, acTextBox, acFooter, , , 0.15 * TW, 0.05 * TW, 3 * TW, 0.22 * TW)
    ctl.ControlSource = "=""Totale schede: "" & Count(*)"
    ctl.Name = "txtTotale"
    rpt.Section(acFooter).Height = 0.35 * TW

    DoCmd.Close acReport, rptName, acSaveYes
    DoCmd.Rename "rptTabella", acReport, rptName

    MsgBox "Report 'rptTabella' creato.", vbInformation, "BuildTabellaReport"
    Exit Sub

ErrHandler:
    MsgBox "Errore in BuildTabellaReport: " & Err.Number & " - " & Err.Description, vbCritical, "BuildTabellaReport"
End Sub
