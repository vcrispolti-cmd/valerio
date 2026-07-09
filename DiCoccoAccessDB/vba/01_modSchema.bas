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

    db.Execute "CREATE TABLE Opere (" & _
        "ID COUNTER PRIMARY KEY, " & _
        "NumeroScheda LONG, " & _
        "Intestazione TEXT(50), " & _
        "Titolo TEXT(255), " & _
        "Anno TEXT(30), " & _
        "NumeroArchivio TEXT(50), " & _
        "Tecnica TEXT(255), " & _
        "Dimensioni TEXT(100), " & _
        "SegniRecto MEMO, " & _
        "SegniVerso MEMO, " & _
        "Collocazione TEXT(255), " & _
        "Provenienza MEMO, " & _
        "EsposizioniPersonali MEMO, " & _
        "EsposizioniCollettive MEMO, " & _
        "Bibliografia MEMO, " & _
        "Note MEMO, " & _
        "ImmagineRecto TEXT(260), " & _
        "ImmagineVerso TEXT(260), " & _
        "ImmagineLaterale TEXT(260), " & _
        "Illustrazione1 TEXT(260), " & _
        "Illustrazione2 TEXT(260), " & _
        "Illustrazione3 TEXT(260), " & _
        "PaginePDF TEXT(20), " & _
        "TestoIntegrale MEMO" & _
        ")", dbFailOnError

    On Error Resume Next
    db.TableDefs.Delete "Config"
    db.TableDefs.Refresh
    On Error GoTo ErrHandler

    db.Execute "CREATE TABLE Config (" & _
        "ID COUNTER PRIMARY KEY, " & _
        "ImagesFolder TEXT(260)" & _
        ")", dbFailOnError

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
