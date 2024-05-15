# Setup

Install PCPI dependency for Python3.8 or greater.

```bash
python3 -m pip install pcpi
```

# Running the script

The script will prompt you for Prisma Cloud credentials when run for the first time.

These credentials will be stored in your "HOME/.prismacloud" directory in a file called "credentials.json".

This script takes 1 command line argument, the look back date time. This value sets the cutoff datetime of CICD Scans to be included in the report. All scans with a launch date between now and the specified date will be included.

```bash
python3 cicd_report.py -t "2024-01-31"
```

# Interpreting the results

This script will create 2 CSV files:
runs_report.csv
full_report.csv

The runs only report, runs_report.csv, only includes a summary of reach CICD scan for each repository. This report takes less data to complete and will created early on in the scripts execution.

Headers for this report:
"Repository Name,Run ID,Run Time,Run Status,Run Result"

The full report,  full_report.csv, contains not only the CICD scan results but it includes the resources that have been scanned and the policies those resources were scanned against. This report takes much longer to complete.

Headers for this report:
"Repository Name, Run ID, Run Time, Run Status, Run Result, Resource Name, Policy Name, Policy Violation Status, Suggested Fix"