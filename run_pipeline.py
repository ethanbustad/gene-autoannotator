
import time
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = "path.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SPREADSHEET_ID = "sheet_id"
RANGE_NAME = "Sheet1A:E"

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)

service = build("sheets", "v4", credentials=credentials)
sheet = service.spreadsheets()

from autoannotation.__main__ import main as annotate
from compareannotations.__main__ import main as compare

"""
GENES = [
    "Rv2007c",
    "Rv2612c",
    "Rv2070c",
    "Rv3221A",
    "Rv3459c",
    "Rv2057c",
    "Rv0001",
    "Rv2418c",
    "Rv0002",
    "Rv0003"
]
"""

GENES = [
    "Rv0969",
    ]

def record_result(gene, comparison_result, duration, num_papers_used, num_total_papers):
    #print("\n=== RESULT ===\n")
    #print(f"Gene:\t {gene}")
    #print(f"Score:\t {comparison_result:.2f}")
    #print(f"Duration:\t {duration:.2f} sec")
    #print(f"Total Papers:\t {num_total_papers}")
    #print(f"Papers used:\t {num_papers_used}")
    #print(f"\n=== END ===\n")

    values = [[gene, comparison_result, duration, num_papers_used, num_total_papers]]

    row = next_empty_row(sheet, col='D', start_row=7)

    range_name = f"D{row}:H{row}"

    body = {"Values": values}

    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueInputOptions="RAW",
        body=body
    ).execute()

    print(f"Row appended: {result}")

def next_empty_row(sheet, col='D', start_row=7):
    col_index = ord(col.upper()) -64
    values = sheet.col_values(col_index)

    return max(start_row, len(values)+1)


def mark_complete(gene):
    print(f"Completed {gene}")

def log_error(gene, error):
    print(f"Error processing {gene}")
    print(error)


for gene in GENES:
    try:
        print(f"\nStarting {gene}")

        start = time.time()

        annotation_result = annotate(gene)

        if annotation_result is None:
            print(f"Skipping {gene}: annotation failed")
            continue

        papers_used = annotation_result["papers_used"]

        total_papers = annotation_result["all_papers"]

        generated_json = annotation_result["output_path"]

        trusted_json = os.path.join("trust_json", f"trust_{gene}.json")
        
        duration = time.time() - start

        comparison_result = compare(trusted_json, generated_json)

        record_result(gene, comparison_result, duration, len(papers_used), len(total_papers))

        mark_complete(gene)

    except Exception as e:
        log_error(gene, e)
        continue