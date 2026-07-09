Attribute VB_Name = "modMain"
Option Compare Database
Option Explicit

' Entry point: run this once (F5 with the cursor in RunAll, or type
' "RunAll" in the Immediate window and press Enter) to build the entire
' application in a freshly created blank .accdb. Each step is also runnable
' on its own if you need to re-run just one piece after a fix.
Public Sub RunAll()
    On Error GoTo ErrHandler

    modSchema.CreateSchema
    modImportData.ImportData
    modBuildForm_Edit.BuildEditForm
    modBuildReport_Tabella.BuildTabellaReport
    modBuildReport_Schede.BuildSchedeReport
    modBuildForm_Search.BuildSearchForm
    BuildSwitchboard

    DoCmd.OpenForm "frmMenu"

    MsgBox "Database completato:" & vbCrLf & _
           "- Tabelle Opere / Config" & vbCrLf & _
           "- Form frmOpereEdit (inserimento/modifica)" & vbCrLf & _
           "- Form frmRicercaAvanzata (ricerca booleana)" & vbCrLf & _
           "- Report rptTabella (tabellare con miniature)" & vbCrLf & _
           "- Report rptSchede (una scheda per pagina)" & vbCrLf & vbCrLf & _
           "Prossimo passo: sul form Menu, premi 'Imposta cartella immagini' e seleziona " & _
           "la cartella DiCoccoImmagini_Schede, poi apri le schede e collega le immagini " & _
           "con i pulsanti 'Sfoglia...'.", vbInformation, "RunAll completato"
    Exit Sub

ErrHandler:
    MsgBox "Errore in RunAll: " & Err.Number & " - " & Err.Description & vbCrLf & _
           "Puoi rilanciare i singoli passaggi (CreateSchema, ImportData, BuildEditForm, " & _
           "BuildTabellaReport, BuildSchedeReport, BuildSearchForm, BuildSwitchboard) uno alla " & _
           "volta dalla finestra Immediata per capire dove si e' fermato.", vbCritical, "RunAll"
End Sub

Public Sub BuildSwitchboard()
    On Error GoTo ErrHandler
    Const TW As Long = 1440

    Dim frm As Access.Form
    Dim frmName As String
    Dim ctl As Access.Control

    On Error Resume Next
    DoCmd.DeleteObject acForm, "frmMenu"
    On Error GoTo ErrHandler

    Set frm = CreateForm()
    frmName = frm.Name
    frm.Caption = "Francesco Di Cocco - Catalogo opere"
    frm.Width = 4.5 * TW
    frm.RecordSelectors = False
    frm.NavigationButtons = False
    frm.ScrollBars = 0

    Dim topPos As Long
    topPos = 0.2 * TW

    Set ctl = CreateControl(frmName, acLabel, acDetail, , , 0.2 * TW, topPos, 4 * TW, 0.35 * TW)
    ctl.Caption = "Francesco Di Cocco - Catalogo opere"
    ctl.FontBold = True
    ctl.FontSize = 14
    topPos = topPos + 0.5 * TW

    Dim buttons As Variant
    buttons = Array( _
        Array("Inserisci / modifica schede", "=OpenEditForm()"), _
        Array("Ricerca avanzata", "=OpenSearchForm()"), _
        Array("Stampa tabella (tutte le schede)", "=OpenTabellaAll()"), _
        Array("Stampa schede (tutte, formato scheda)", "=OpenSchedeAll()"), _
        Array("Imposta cartella immagini...", "=SetImagesFolder()"))

    Dim i As Integer, b As Variant
    For i = 0 To UBound(buttons)
        b = buttons(i)
        Set ctl = CreateControl(frmName, acCommandButton, acDetail, , , 0.2 * TW, topPos, 3.8 * TW, 0.4 * TW)
        ctl.Caption = b(0)
        ctl.OnClick = b(1)
        ctl.FontSize = 11
        topPos = topPos + 0.5 * TW
    Next i

    frm.Section(acDetail).Height = topPos + 0.15 * TW

    DoCmd.Close acForm, frmName, acSaveYes
    DoCmd.Rename "frmMenu", acForm, frmName

    Exit Sub
ErrHandler:
    MsgBox "Errore in BuildSwitchboard: " & Err.Number & " - " & Err.Description, vbCritical, "BuildSwitchboard"
End Sub

Public Function OpenEditForm() As Variant
    On Error Resume Next
    DoCmd.OpenForm "frmOpereEdit"
End Function

Public Function OpenSearchForm() As Variant
    On Error Resume Next
    DoCmd.OpenForm "frmRicercaAvanzata"
End Function

Public Function OpenTabellaAll() As Variant
    On Error Resume Next
    DoCmd.OpenReport "rptTabella", acViewPreview
End Function

Public Function OpenSchedeAll() As Variant
    On Error Resume Next
    DoCmd.OpenReport "rptSchede", acViewPreview
End Function
