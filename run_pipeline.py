
"""
run with:

python -m run_pipeline 2>&1 | tee log.txt

"""

# This is a manual evaluation harness, not the normal app entry point. It runs a
# fixed benchmark gene list, compares generated JSON against trusted fixtures,
# and logs scores to one Google Sheet configured below.
import time
import os
from datetime import datetime
import traceback

from google.oauth2 import service_account
from googleapiclient.discovery import build

COMPLETE_LOG = "completed_genes.txt"
ERROR_LOG = "error_log.txt"

SERVICE_ACCOUNT_FILE = "creds/gene-annotation-logger-ab193a2da8c6.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1qiLSngYGAUQkTPGC8rLzhcQzU4Lrke7S678pSGXHICs/edit?gid=243893338#gid=243893338"
SPREADSHEET_ID = "1qiLSngYGAUQkTPGC8rLzhcQzU4Lrke7S678pSGXHICs"

SHEET_NAME = "V2Scores"

# Google Sheets is initialized at import time, so this script requires the
# service-account credentials file even before the first gene starts.
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)

service = build("sheets", "v4", credentials=credentials)
sheet = service.spreadsheets()

from autoannotation.__main__ import main as annotate
from compareannotations.__main__ import main as compare

def record_result(gene, comparison_result, duration, num_papers_used, num_total_papers, cumulative_relevance=0.0):
    values = [[gene, comparison_result, duration, num_papers_used, num_total_papers, cumulative_relevance]]

    #row = next_empty_row(sheet, col='D', start_row=7)

    #range_name = f"BaselineScores!D{row}:H{row}"

    body = {"values": values}

    result = sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!D:I",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()

    print(f"Row appended: {result}")

def mark_complete(gene):
    with open(COMPLETE_LOG, "a") as f:
        f.write(gene + "\n")

    print(f"Completed {gene}")

def log_error(gene, error):
    timestamp = datetime.now().isoformat()

    error_message = (
        f"\n[{timestamp}] ERROR processing {gene}\n"
        f"{str(error)}\n"
        f"{traceback.format_exc()}\n"
        f"{'='*60}\n"
    )

    with open(ERROR_LOG, "a") as f:
        f.write(error_message)

    print(f"Error processing {gene}")
    print(error)

def load_completed_genes():
    if not os.path.exists(COMPLETE_LOG):
        return set()

    with open(COMPLETE_LOG, "r") as f:
        return set(line.strip() for line in f)

"""
Rv0001:     1133  | 12
Rv0002:     518   | 15
Rv0003:     375   | 17
Rv2007c:    177   | 11
Rv2057c:    38    | 17
Rv2070c:    25    | 15
Rv2418c:    8     | 2
Rv2612c:    34    | 16
Rv3221A:    145   | 15
Rv3459c:    95    | 19
"""

GENES = [
    "Rv0001",
    "Rv0002",
    "Rv0003",
    "Rv2007c",
    "Rv2057c",
    "Rv2070c",
    "Rv2418c",
    "Rv2612c",
    "Rv3221A",
    "Rv3459c"

]

completed_genes = load_completed_genes()

# completed_genes.txt makes long benchmark runs resumable after model/API
# failures; deleting it intentionally reruns the full fixed list.
for gene in GENES:

    if gene in completed_genes:
        print(f"Skipping {gene}: already completed")
        continue

    try:
        print(f"\nStarting {gene}")

        start = time.time()

        annotation_result = annotate(gene)

        if annotation_result is None:
            print(f"Skipping {gene}: annotation failed")
            record_result(gene, "N/A", "N/A", 0, "N/A")
            continue

        papers_used = annotation_result["papers_used"]

        total_papers = annotation_result["all_papers"]

        generated_json = annotation_result["output_path"]

        cumulative_relevance = annotation_result["cumulative_relevance"]

        trusted_json = os.path.join("trust_json", f"trust_{gene}.json")

        duration = time.time() - start

        print(f"\nComparing {gene}: {trusted_json} vs {generated_json}")
        comparison_result = compare(trusted_json, generated_json)

        record_result(gene, comparison_result, duration, len(papers_used), len(total_papers), cumulative_relevance)

        mark_complete(gene)

    except Exception as e:
        log_error(gene, e)
        continue