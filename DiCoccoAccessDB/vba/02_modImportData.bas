Attribute VB_Name = "modImportData"
Option Compare Database
Option Explicit

' Imports data\DiCocco_Data.dat (must sit in a "data" subfolder next to the
' .accdb file) into the Opere table. The file uses Chr(31) as a field
' separator and Chr(30) as a record separator, UTF-8 encoded, so accented
' Italian text survives untouched and no import spec / Schema.ini is needed.
Public Sub ImportData()
    On Error GoTo ErrHandler

    Dim db As DAO.Database
    Dim rs As DAO.Recordset
    Dim stm As Object
    Dim filePath As String
    Dim wholeText As String
    Dim records() As String
    Dim fieldNames() As String
    Dim fields() As String
    Dim i As Long, f As Long
    Dim imported As Long
    Dim fn As String

    filePath = CurrentProject.Path & "\data\DiCocco_Data.dat"

    If Dir(filePath) = "" Then
        MsgBox "Non trovo il file dati nella posizione prevista:" & vbCrLf & filePath & vbCrLf & vbCrLf & _
               "Nella finestra che si apre ora, seleziona tu DiCocco_Data.dat " & _
               "(si trova nella cartella 'data' del pacchetto).", vbInformation, "ImportData"

        Dim fd As Object
        Set fd = Application.FileDialog(3) ' msoFileDialogFilePicker
        fd.Title = "Seleziona DiCocco_Data.dat"
        fd.Filters.Clear
        fd.Filters.Add "File dati", "*.dat"
        fd.Filters.Add "Tutti i file", "*.*"
        fd.AllowMultiSelect = False

        If fd.Show = -1 Then
            filePath = fd.SelectedItems(1)
        Else
            MsgBox "Importazione annullata: nessun file selezionato.", vbExclamation, "ImportData"
            Exit Sub
        End If

        If Dir(filePath) = "" Then
            MsgBox "Il file selezionato non e' raggiungibile:" & vbCrLf & filePath, vbCritical, "ImportData"
            Exit Sub
        End If
    End If

    Set stm = CreateObject("ADODB.Stream")
    stm.Type = 2 ' adTypeText
    stm.Charset = "utf-8"
    stm.Open
    stm.LoadFromFile filePath
    wholeText = stm.ReadText
    stm.Close

    records = Split(wholeText, Chr(30))
    If UBound(records) < 1 Then
        MsgBox "Il file dati sembra vuoto o mal formato.", vbExclamation, "ImportData"
        Exit Sub
    End If

    fieldNames = Split(records(0), Chr(31))

    Set db = CurrentDb
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

    Set rs = db.OpenRecordset("Opere", dbOpenDynaset)

    imported = 0
    For i = 1 To UBound(records)
        If Len(Trim$(records(i))) = 0 Then GoTo ContinueLoop

        fields = Split(records(i), Chr(31))
        rs.AddNew
        For f = 0 To UBound(fieldNames)
            If f <= UBound(fields) Then
                fn = fieldNames(f)
                If Len(fields(f)) > 0 Then
                    If fn = "NumeroScheda" Then
                        rs.Fields(fn).Value = CLng(fields(f))
                    Else
                        rs.Fields(fn).Value = fields(f)
                    End If
                End If
            End If
        Next f
        rs.Update
        imported = imported + 1
ContinueLoop:
    Next i

    rs.Close

    MsgBox "Importazione completata: " & imported & " record importati in Opere.", vbInformation, "ImportData"
    Exit Sub

ErrHandler:
    MsgBox "Errore in ImportData: " & Err.Number & " - " & Err.Description, vbCritical, "ImportData"
    On Error Resume Next
    If Not rs Is Nothing Then rs.Close
End Sub
