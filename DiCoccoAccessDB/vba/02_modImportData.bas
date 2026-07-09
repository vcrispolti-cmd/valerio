Attribute VB_Name = "modImportData"
Option Compare Database
Option Explicit

' Imports directly from your Excel file (e.g. Di_Cocco_Database_Schede_1913-1934.xlsx)
' into the Opere table, using Access's own native Excel importer
' (TransferSpreadsheet) -- no intermediate data file needed. You'll be
' prompted to browse to the .xlsx file when you run this.
'
' It expects two sheets, exactly as in the original file:
'   "Database opere"        -- the main grid (all the columns)
'   "Testo grezzo schede"   -- optional; raw full-text per scheda
' If the second sheet is missing or named differently, the import still
' completes; only the TestoIntegrale field is left blank.
Public Sub ImportData()
    On Error GoTo ErrHandler

    Dim db As DAO.Database
    Set db = CurrentDb

    Dim excelPath As String
    excelPath = PromptForExcelFile()
    If Len(excelPath) = 0 Then
        MsgBox "Importazione annullata: nessun file selezionato.", vbExclamation, "ImportData"
        Exit Sub
    End If

    Dim existingCount As Long
    existingCount = 0
    On Error Resume Next
    existingCount = DCount("*", "Opere")
    On Error GoTo ErrHandler

    If existingCount > 0 Then
        If MsgBox(existingCount & " record gia' presenti nella tabella Opere." & vbCrLf & _
                  "Cancellarli e reimportare tutto da zero?", vbYesNo + vbQuestion, "ImportData") = vbNo Then
            Exit Sub
        End If
        db.Execute "DELETE FROM Opere", dbFailOnError
    End If

    ' Clean up any leftover temp import tables from a previous attempt
    On Error Resume Next
    db.TableDefs.Delete "tmpDatabaseOpere"
    db.TableDefs.Delete "tmpTestoGrezzo"
    db.TableDefs.Refresh
    On Error GoTo ErrHandler

    DoCmd.TransferSpreadsheet acImport, acSpreadsheetTypeExcel12Xml, "tmpDatabaseOpere", excelPath, True, "Database opere!"

    Dim hasRawText As Boolean
    hasRawText = True
    On Error Resume Next
    Err.Clear
    DoCmd.TransferSpreadsheet acImport, acSpreadsheetTypeExcel12Xml, "tmpTestoGrezzo", excelPath, True, "Testo grezzo schede!"
    If Err.Number <> 0 Then hasRawText = False
    Err.Clear
    On Error GoTo ErrHandler

    ' Reference source columns by POSITION rather than by literal name: Access
    ' can silently rename fields on import if the Excel header uses a
    ' character it doesn't allow (a trailing period, for instance), so this
    ' is more robust than assuming the exact sanitized name.
    Dim o0 As String, o1 As String, o2 As String, o3 As String, o4 As String
    Dim o5 As String, o6 As String, o7 As String, o8 As String, o9 As String
    Dim o10 As String, o11 As String, o12 As String, o13 As String, o14 As String
    Dim o15 As String, o16 As String, o17 As String, o18 As String, o19 As String
    Dim o20 As String, o21 As String

    o0 = FN("tmpDatabaseOpere", 0)   ' N.
    o1 = FN("tmpDatabaseOpere", 1)   ' Scheda (intestazione)
    o2 = FN("tmpDatabaseOpere", 2)   ' Immagine recto
    o3 = FN("tmpDatabaseOpere", 3)   ' Immagine verso
    o4 = FN("tmpDatabaseOpere", 4)   ' Immagine laterale
    o5 = FN("tmpDatabaseOpere", 5)   ' Titolo
    o6 = FN("tmpDatabaseOpere", 6)   ' Anno
    o7 = FN("tmpDatabaseOpere", 7)   ' Numero d'archivio
    o8 = FN("tmpDatabaseOpere", 8)   ' Tecnica
    o9 = FN("tmpDatabaseOpere", 9)   ' Dimensioni
    o10 = FN("tmpDatabaseOpere", 10) ' Segni sul recto
    o11 = FN("tmpDatabaseOpere", 11) ' Segni sul verso
    o12 = FN("tmpDatabaseOpere", 12) ' Collocazione
    o13 = FN("tmpDatabaseOpere", 13) ' Provenienza
    o14 = FN("tmpDatabaseOpere", 14) ' Esposizioni personali
    o15 = FN("tmpDatabaseOpere", 15) ' Esposizioni collettive
    o16 = FN("tmpDatabaseOpere", 16) ' Bibliografia
    o17 = FN("tmpDatabaseOpere", 17) ' Note
    o18 = FN("tmpDatabaseOpere", 18) ' Illustrazione 1
    o19 = FN("tmpDatabaseOpere", 19) ' Illustrazione 2
    o20 = FN("tmpDatabaseOpere", 20) ' Illustrazione 3
    o21 = FN("tmpDatabaseOpere", 21) ' Pagine PDF

    Dim t0 As String, t3 As String
    If hasRawText Then
        t0 = FN("tmpTestoGrezzo", 0) ' N. scheda
        t3 = FN("tmpTestoGrezzo", 3) ' Testo integrale della scheda
    End If

    Dim sql As String
    sql = "INSERT INTO Opere (NumeroScheda, Intestazione, Titolo, Anno, NumeroArchivio, "
    sql = sql & "Tecnica, Dimensioni, SegniRecto, SegniVerso, Collocazione, Provenienza, "
    sql = sql & "EsposizioniPersonali, EsposizioniCollettive, Bibliografia, Note, "
    sql = sql & "ImmagineRecto, ImmagineVerso, ImmagineLaterale, Illustrazione1, Illustrazione2, "
    sql = sql & "Illustrazione3, PaginePDF"
    If hasRawText Then sql = sql & ", TestoIntegrale"
    sql = sql & ") SELECT o." & o0 & ", o." & o1 & ", o." & o5 & ", o." & o6 & ", o." & o7 & ", "
    sql = sql & "o." & o8 & ", o." & o9 & ", o." & o10 & ", o." & o11 & ", o." & o12 & ", o." & o13 & ", "
    sql = sql & "o." & o14 & ", o." & o15 & ", o." & o16 & ", o." & o17 & ", "
    sql = sql & "o." & o2 & ", o." & o3 & ", o." & o4 & ", o." & o18 & ", o." & o19 & ", "
    sql = sql & "o." & o20 & ", o." & o21
    If hasRawText Then sql = sql & ", t." & t3
    sql = sql & " FROM tmpDatabaseOpere AS o"
    If hasRawText Then sql = sql & " LEFT JOIN tmpTestoGrezzo AS t ON o." & o0 & " = t." & t0
    sql = sql & " WHERE o." & o0 & " Is Not Null"

    db.Execute sql, dbFailOnError

    Dim imported As Long
    imported = DCount("*", "Opere")

    On Error Resume Next
    db.TableDefs.Delete "tmpDatabaseOpere"
    db.TableDefs.Delete "tmpTestoGrezzo"
    On Error GoTo ErrHandler

    Dim msg As String
    msg = "Importazione completata: " & imported & " record importati in Opere."
    If Not hasRawText Then
        msg = msg & vbCrLf & vbCrLf & "Nota: non ho trovato il foglio 'Testo grezzo schede' " & _
              "(o ha un nome diverso in questo file), quindi il campo TestoIntegrale e' rimasto vuoto. " & _
              "Tutti gli altri campi sono stati importati regolarmente."
    End If
    MsgBox msg, vbInformation, "ImportData"
    Exit Sub

ErrHandler:
    MsgBox "Errore in ImportData: " & Err.Number & " - " & Err.Description & vbCrLf & vbCrLf & _
           "Verifica che il file selezionato abbia un foglio chiamato esattamente 'Database opere' " & _
           "con le stesse colonne dell'originale.", vbCritical, "ImportData"
    On Error Resume Next
    CurrentDb.TableDefs.Delete "tmpDatabaseOpere"
    CurrentDb.TableDefs.Delete "tmpTestoGrezzo"
End Sub

Private Function PromptForExcelFile() As String
    On Error GoTo ErrHandler
    Dim fd As Object
    Set fd = Application.FileDialog(3) ' msoFileDialogFilePicker
    fd.Title = "Seleziona il file Excel (es. Di_Cocco_Database_Schede_1913-1934.xlsx)"
    fd.Filters.Clear
    fd.Filters.Add "File Excel", "*.xlsx;*.xlsm;*.xls"
    fd.AllowMultiSelect = False
    If fd.Show = -1 Then
        PromptForExcelFile = fd.SelectedItems(1)
    Else
        PromptForExcelFile = ""
    End If
    Exit Function
ErrHandler:
    PromptForExcelFile = ""
End Function

' Returns the bracket-quoted actual field name at ordinal position idx
' (0-based) in table tbl.
Private Function FN(tbl As String, idx As Integer) As String
    FN = "[" & CurrentDb.TableDefs(tbl).Fields(idx).Name & "]"
End Function
