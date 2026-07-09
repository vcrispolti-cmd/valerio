Attribute VB_Name = "modSchema"
Option Compare Database
Option Explicit

' Creates the two tables (Opere, Config) and the base sorted query used by
' the tabular report. Safe to re-run: existing objects with the same name
' are dropped and recreated (data is NOT preserved by this step -- run
' ImportData afterwards to (re)populate Opere).
Public Sub CreateSchema()
    On Error GoTo ErrHandler
    Dim db As DAO.Database
    Set db = CurrentDb

    On Error Resume Next
    db.TableDefs.Delete "Opere"
    db.TableDefs.Refresh
    On Error GoTo ErrHandler

    Dim sql As String
    sql = "CREATE TABLE Opere ("
    sql = sql & "ID COUNTER PRIMARY KEY, "
    sql = sql & "NumeroScheda LONG, "
    sql = sql & "Intestazione TEXT(50), "
    sql = sql & "Titolo TEXT(255), "
    sql = sql & "Anno TEXT(30), "
    sql = sql & "NumeroArchivio TEXT(50), "
    sql = sql & "Tecnica TEXT(255), "
    sql = sql & "Dimensioni TEXT(100), "
    sql = sql & "SegniRecto MEMO, "
    sql = sql & "SegniVerso MEMO, "
    sql = sql & "Collocazione TEXT(255), "
    sql = sql & "Provenienza MEMO, "
    sql = sql & "EsposizioniPersonali MEMO, "
    sql = sql & "EsposizioniCollettive MEMO, "
    sql = sql & "Bibliografia MEMO, "
    sql = sql & "Note MEMO, "
    sql = sql & "ImmagineRecto TEXT(260), "
    sql = sql & "ImmagineVerso TEXT(260), "
    sql = sql & "ImmagineLaterale TEXT(260), "
    sql = sql & "Illustrazione1 TEXT(260), "
    sql = sql & "Illustrazione2 TEXT(260), "
    sql = sql & "Illustrazione3 TEXT(260), "
    sql = sql & "PaginePDF TEXT(20), "
    sql = sql & "TestoIntegrale MEMO"
    sql = sql & ")"
    db.Execute sql, dbFailOnError

    On Error Resume Next
    db.TableDefs.Delete "Config"
    db.TableDefs.Refresh
    On Error GoTo ErrHandler

    sql = "CREATE TABLE Config ("
    sql = sql & "ID COUNTER PRIMARY KEY, "
    sql = sql & "ImagesFolder TEXT(260)"
    sql = sql & ")"
    db.Execute sql, dbFailOnError

    db.Execute "INSERT INTO Config (ImagesFolder) VALUES ('')", dbFailOnError

    On Error Resume Next
    db.QueryDefs.Delete "qryOpereOrdinate"
    On Error GoTo ErrHandler
    db.CreateQueryDef "qryOpereOrdinate", "SELECT * FROM Opere ORDER BY NumeroScheda"

    MsgBox "Schema creato: tabelle Opere e Config, query qryOpereOrdinate." & vbCrLf & _
           "Ora esegui modImportData.ImportData per caricare i dati.", vbInformation, "CreateSchema"
    Exit Sub

ErrHandler:
    MsgBox "Errore in CreateSchema: " & Err.Number & " - " & Err.Description, vbCritical, "CreateSchema"
End Sub
