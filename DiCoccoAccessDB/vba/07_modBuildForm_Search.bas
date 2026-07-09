Attribute VB_Name = "modBuildForm_Search"
Option Compare Database
Option Explicit

' Builds frmRicercaAvanzata: up to 5 criteria rows (Field / Operator / Value),
' each combined with the running result via an E (AND) / O (OR) selector,
' a results list, and buttons to open a record or print either report
' limited to the current search. Also contains the runtime query-building
' logic the form's buttons call into (as "=Function()" expressions).

Private Function FieldListRowSource() As String
    Dim pairs As Variant
    pairs = Array( _
        "N. scheda", "NumeroScheda", _
        "Scheda (intestazione)", "Intestazione", _
        "Titolo", "Titolo", _
        "Anno", "Anno", _
        "Numero d'archivio", "NumeroArchivio", _
        "Tecnica", "Tecnica", _
        "Dimensioni", "Dimensioni", _
        "Segni sul recto", "SegniRecto", _
        "Segni sul verso", "SegniVerso", _
        "Collocazione", "Collocazione", _
        "Provenienza", "Provenienza", _
        "Esposizioni personali", "EsposizioniPersonali", _
        "Esposizioni collettive", "EsposizioniCollettive", _
        "Bibliografia", "Bibliografia", _
        "Note", "Note", _
        "Pagine PDF", "PaginePDF", _
        "Testo integrale scheda", "TestoIntegrale")
    FieldListRowSource = Join(pairs, ";")
End Function

Public Sub BuildSearchForm()
    On Error GoTo ErrHandler
    Const TW As Long = 1440

    Dim frm As Access.Form
    Dim frmName As String
    Dim ctl As Access.Control

    On Error Resume Next
    DoCmd.DeleteObject acForm, "frmRicercaAvanzata"
    On Error GoTo ErrHandler

    Set frm = CreateForm()
    frmName = frm.Name
    frm.Caption = "Ricerca avanzata - Opere Di Cocco"
    frm.Width = 7.6 * TW
    frm.RecordSelectors = False
    frm.NavigationButtons = False
    frm.ScrollBars = 2

    Dim topPos As Long
    topPos = 0.15 * TW

    Set ctl = CreateControl(frmName, acLabel, acDetail, , , 0.15 * TW, topPos, 6 * TW, 0.3 * TW)
    ctl.Caption = "Ricerca avanzata (booleana) su tutti i campi"
    ctl.FontBold = True
    ctl.FontSize = 13
    topPos = topPos + 0.4 * TW

    Dim fieldRS As String, operRS As String, logicRS As String
    fieldRS = FieldListRowSource()
    operRS = "Contiene;Uguale a;Inizia con;Vuoto;Non vuoto"
    logicRS = "E;O"

    Dim logicX As Long, fieldX As Long, operX As Long, valX As Long
    Dim logicW As Long, fieldW As Long, operW As Long, valW As Long
    logicX = 0.15 * TW: logicW = 0.55 * TW
    fieldX = logicX + logicW + 0.1 * TW: fieldW = 1.9 * TW
    operX = fieldX + fieldW + 0.1 * TW: operW = 1.2 * TW
    valX = operX + operW + 0.1 * TW: valW = 2.2 * TW

    Dim i As Integer
    For i = 1 To 5
        If i > 1 Then
            Set ctl = CreateControl(frmName, acComboBox, acDetail, , , logicX, topPos, logicW, 0.24 * TW)
            ctl.Name = "cboLogic" & i
            ctl.RowSourceType = "Value List"
            ctl.RowSource = logicRS
            ctl.ColumnCount = 1
            ctl.Value = "E"
        End If

        Set ctl = CreateControl(frmName, acComboBox, acDetail, , , fieldX, topPos, fieldW, 0.24 * TW)
        ctl.Name = "cboField" & i
        ctl.RowSourceType = "Value List"
        ctl.RowSource = fieldRS
        ctl.ColumnCount = 2
        ctl.ColumnWidths = "1.8in;0in"
        ctl.BoundColumn = 2
        ctl.LimitToList = True

        Set ctl = CreateControl(frmName, acComboBox, acDetail, , , operX, topPos, operW, 0.24 * TW)
        ctl.Name = "cboOper" & i
        ctl.RowSourceType = "Value List"
        ctl.RowSource = operRS
        ctl.ColumnCount = 1
        ctl.LimitToList = True

        Set ctl = CreateControl(frmName, acTextBox, acDetail, , , valX, topPos, valW, 0.24 * TW)
        ctl.Name = "txtVal" & i

        topPos = topPos + 0.32 * TW
    Next i

    topPos = topPos + 0.1 * TW

    ' --- Action buttons ---
    Set ctl = CreateControl(frmName, acCommandButton, acDetail, , , 0.15 * TW, topPos, 1.1 * TW, 0.3 * TW)
    ctl.Caption = "Cerca"
    ctl.OnClick = "=RunSearch()"

    Set ctl = CreateControl(frmName, acCommandButton, acDetail, , , 1.35 * TW, topPos, 1.1 * TW, 0.3 * TW)
    ctl.Caption = "Pulisci"
    ctl.OnClick = "=ClearSearch()"

    Set ctl = CreateControl(frmName, acCommandButton, acDetail, , , 2.55 * TW, topPos, 1.7 * TW, 0.3 * TW)
    ctl.Caption = "Apri scheda selezionata"
    ctl.OnClick = "=OpenSelectedRecord()"

    Set ctl = CreateControl(frmName, acCommandButton, acDetail, , , 4.35 * TW, topPos, 1.5 * TW, 0.3 * TW)
    ctl.Caption = "Stampa tabella"
    ctl.OnClick = "=PrintTabellaResults()"

    Set ctl = CreateControl(frmName, acCommandButton, acDetail, , , 5.95 * TW, topPos, 1.5 * TW, 0.3 * TW)
    ctl.Caption = "Stampa schede"
    ctl.OnClick = "=PrintSchedeResults()"

    topPos = topPos + 0.4 * TW

    Set ctl = CreateControl(frmName, acLabel, acDetail, , , 0.15 * TW, topPos, 2 * TW, 0.22 * TW)
    ctl.Name = "lblConteggio"
    ctl.Caption = "Risultati: -"
    ctl.FontBold = True
    topPos = topPos + 0.28 * TW

    ' --- Results list ---
    Set ctl = CreateControl(frmName, acListBox, acDetail, , , 0.15 * TW, topPos, 7.3 * TW, 2.6 * TW)
    ctl.Name = "lstRisultati"
    ctl.RowSourceType = "Table/Query"
    ctl.RowSource = "SELECT NumeroScheda, Intestazione, Titolo, Anno, Tecnica, Collocazione FROM Opere ORDER BY NumeroScheda"
    ctl.ColumnCount = 6
    ctl.ColumnHeads = True
    ctl.ColumnWidths = "0.5in;1.1in;2in;0.6in;1.4in;1.5in"
    ctl.BoundColumn = 1

    topPos = topPos + 2.7 * TW

    frm.Section(acDetail).Height = topPos + 0.15 * TW

    DoCmd.Close acForm, frmName, acSaveYes
    DoCmd.Rename "frmRicercaAvanzata", acForm, frmName

    MsgBox "Form 'frmRicercaAvanzata' creato.", vbInformation, "BuildSearchForm"
    Exit Sub

ErrHandler:
    MsgBox "Errore in BuildSearchForm: " & Err.Number & " - " & Err.Description, vbCritical, "BuildSearchForm"
End Sub

' ---------------- Runtime search logic ----------------

Private Function BuildSingleCondition(fieldName As String, oper As String, val As String) As String
    Dim v As String
    v = Replace(val, "'", "''")
    Select Case oper
        Case "Contiene"
            BuildSingleCondition = "[" & fieldName & "] Like '*" & v & "*'"
        Case "Uguale a"
            If fieldName = "NumeroScheda" Then
                BuildSingleCondition = "[" & fieldName & "] = " & CLng(Val(val))
            Else
                BuildSingleCondition = "[" & fieldName & "] = '" & v & "'"
            End If
        Case "Inizia con"
            BuildSingleCondition = "[" & fieldName & "] Like '" & v & "*'"
        Case "Vuoto"
            BuildSingleCondition = "([" & fieldName & "] Is Null Or [" & fieldName & "] = '')"
        Case "Non vuoto"
            BuildSingleCondition = "([" & fieldName & "] Is Not Null And [" & fieldName & "] <> '')"
        Case Else
            BuildSingleCondition = ""
    End Select
End Function

Private Function BuildWhereClause() As String
    On Error Resume Next
    Dim frm As Access.Form
    Set frm = Screen.ActiveForm
    If frm Is Nothing Then Exit Function

    Dim i As Integer
    Dim result As String, cond As String
    Dim fieldName As String, oper As String, val As String, logic As String

    result = ""
    For i = 1 To 5
        fieldName = Nz(frm("cboField" & i).Value, "")
        oper = Nz(frm("cboOper" & i).Value, "")
        val = Nz(frm("txtVal" & i).Value, "")

        If Len(fieldName) = 0 Or Len(oper) = 0 Then GoTo ContinueLoop
        If oper <> "Vuoto" And oper <> "Non vuoto" And Len(Trim$(val)) = 0 Then GoTo ContinueLoop

        cond = BuildSingleCondition(fieldName, oper, val)
        If Len(cond) = 0 Then GoTo ContinueLoop

        If Len(result) = 0 Then
            result = "(" & cond & ")"
        Else
            logic = Nz(frm("cboLogic" & i).Value, "E")
            If logic = "O" Then
                result = result & " OR (" & cond & ")"
            Else
                result = result & " AND (" & cond & ")"
            End If
        End If
ContinueLoop:
    Next i

    BuildWhereClause = result
End Function

' Wired to the "Cerca" button
Public Function RunSearch() As Variant
    On Error GoTo ErrHandler
    Dim frm As Access.Form
    Set frm = Screen.ActiveForm

    Dim whereClause As String
    whereClause = BuildWhereClause()

    Dim sql As String
    sql = "SELECT NumeroScheda, Intestazione, Titolo, Anno, Tecnica, Collocazione FROM Opere"
    If Len(whereClause) > 0 Then sql = sql & " WHERE " & whereClause
    sql = sql & " ORDER BY NumeroScheda"

    frm("lstRisultati").RowSource = sql
    frm("lstRisultati").Requery

    frm("lblConteggio").Caption = "Risultati: " & DCount("*", "Opere", whereClause)
    Exit Function
ErrHandler:
    MsgBox "Errore nella ricerca: " & Err.Description, vbExclamation, "RunSearch"
End Function

' Wired to the "Pulisci" button
Public Function ClearSearch() As Variant
    On Error Resume Next
    Dim frm As Access.Form
    Set frm = Screen.ActiveForm
    Dim i As Integer
    For i = 1 To 5
        frm("cboField" & i).Value = Null
        frm("cboOper" & i).Value = Null
        frm("txtVal" & i).Value = ""
        If i > 1 Then frm("cboLogic" & i).Value = "E"
    Next i
    frm("lstRisultati").RowSource = "SELECT NumeroScheda, Intestazione, Titolo, Anno, Tecnica, Collocazione FROM Opere ORDER BY NumeroScheda"
    frm("lstRisultati").Requery
    frm("lblConteggio").Caption = "Risultati: " & DCount("*", "Opere")
End Function

' Wired to the "Apri scheda selezionata" button
Public Function OpenSelectedRecord() As Variant
    On Error GoTo ErrHandler
    Dim frm As Access.Form
    Set frm = Screen.ActiveForm
    Dim lst As Access.Control
    Set lst = frm("lstRisultati")
    If IsNull(lst.Value) Then
        MsgBox "Seleziona prima una scheda dall'elenco risultati.", vbInformation, "OpenSelectedRecord"
        Exit Function
    End If
    DoCmd.OpenForm "frmOpereEdit", , , "NumeroScheda = " & lst.Value
    Exit Function
ErrHandler:
    MsgBox "Errore: " & Err.Description, vbExclamation, "OpenSelectedRecord"
End Function

' Wired to the "Stampa tabella" button
Public Function PrintTabellaResults() As Variant
    On Error GoTo ErrHandler
    Dim whereClause As String
    whereClause = BuildWhereClause()
    DoCmd.OpenReport "rptTabella", acViewPreview, , whereClause
    Exit Function
ErrHandler:
    MsgBox "Errore: " & Err.Description, vbExclamation, "PrintTabellaResults"
End Function

' Wired to the "Stampa schede" button
Public Function PrintSchedeResults() As Variant
    On Error GoTo ErrHandler
    Dim whereClause As String
    whereClause = BuildWhereClause()
    DoCmd.OpenReport "rptSchede", acViewPreview, , whereClause
    Exit Function
ErrHandler:
    MsgBox "Errore: " & Err.Description, vbExclamation, "PrintSchedeResults"
End Function
