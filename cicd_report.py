from pcpi import session_loader
import json
import argparse
import csv
from datetime import datetime

session_managers = session_loader.load_config()
session = session_managers[0].create_cspm_session()

def get_repos(session):
    #Get all repositories
    repositories = []
    page_size = 100
    page = 0
    while True:
        res = session.request('GET',f'/code/api/v2/repositories?filter=CICD&page={page}&pageSize={page_size}')

        if len(res.json()['repositories']) < page_size:
            repositories.extend(res.json()['repositories'])
            break
        else:
            repositories.extend(res.json()['repositories'])
            page += 1

    return repositories

def get_runs(session, repositories, look_back_data_string):
    look_back_date_object = datetime.strptime(look_back_data_string, '%Y-%m-%d')
    runs = []
    for repo in repositories:
        #Get runs
        repo_id = repo['id']
        print('Getting RUNS for repo:', repo_id)
        res = session.request('GET', f'/bridgecrew/api/v1/cicd/data/runs?repositoryId={repo_id}&fetchAllBranches=true&fetchErrors=true')

        #Loop over each run to check its create date
        for run in res.json():
            run_create_date = run['creationDate']
            date_format = '%Y-%m-%dT%H:%M:%S.%fZ'

            run_date_obj = datetime.strptime(run_create_date, date_format)

            #Only get runs that happened AFTER our target look back date
            if run_date_obj >= look_back_date_object:
                runs.append(run)

    return runs
    
def get_resources(session, repo, run):
    repo_id = repo['id']
    run_id = run['runId']
    limit = 50
    offset = 0
    counter = 0
    resources = []

    while True:
        payload = {
            "filters": {
                "repositories": [repo_id],
                "runId": run_id,
                "checkStatus": "Error",
                "codeCategories": [] 
            },
            "search": {
                "scopes": [],
                "term": ""
            },
            "offset": offset,
            "limit": limit,
            "sortBy": [
                {
                    "key": "Severity",
                    "direction": "DESC"
                },
                {
                    "key": "Count",
                    "direction": "DESC"
                }
            ]
        }

        res = session.request('POST', '/bridgecrew/api/v2/errors/code_review_scan/resources', json=payload)

        if len(res.json().get('data',[])) < limit:
            resources.extend(res.json().get('data',[]))
            break
        else:
            counter += 1
            offset = counter * limit
            resources.extend(res.json()['data'])

    return resources

def get_errors(repositories, runs, resources):
    errors = []
    count = 0
    for resource in resources:
        count += 1
        print('COUNT', count, '---' 'TOTAL', len(resources))

        for repo in repositories:

            #Skip if resource is not from this repo
            if resource['repository'] != repo['fullRepositoryName']:
                continue

            for run in runs:
                
                #Skip if the run is not from this repo
                if run['fromRepoId'] !=  repo['id']:
                    continue
                
                #Get values for payload
                repo_id = repo['id']
                repo_name = repo['fullRepositoryName']
                run_id = run['runId']
                resource_name = resource['resourceName']

                payload = {
                    "filters": {
                        "repositories": [
                            repo_id
                        ],
                        "runId": run_id
                    },
                    "resourceName": resource_name,
                    "repository": repo_name,
                    "sourceType": "cli" #Only get checkov scan results
                }

                res = session.request('POST', '/bridgecrew/api/v2/resources/code_review_scan/buildtime/errors', json=payload)

                if res:
                    errors.extend(res.json()['errors'])

    return errors

def create_csv_report_runs(repositories, runs):
    with open('runs_report.csv', 'w') as outfile:
        writer = csv.writer(outfile)
        headers = ['Repository Name', 'Run ID', 'Run Time', 'Run Status', 'Run Result']
        writer.writerow(headers)

        for repo in repositories:
            for run in runs:
                #Skip if the run is not from this repo
                if run['fromRepoId'] !=  repo['id']:
                    continue

                row = [repo['fullRepositoryName'], run['runId'], run['creationDate'], run['runStatus'], run['scanStatus']]

                writer.writerow(row)



def create_csv_report_errors(repositories, runs, errors):
    with open('full_report.csv', 'w') as outfile:
        writer = csv.writer(outfile)
        headers = ['Repository Name', 'Run ID', 'Run Time', 'Run Status', 'Run Result', 'Resource Name', 'Policy Name', 'Policy Violation Status', 'Suggested Fix']
        writer.writerow(headers)

        for error in errors:
            for repo in repositories:
                #If the resource in the error does not come from this repo, skip this repo.
                if error['sourceId'] != repo['fullRepositoryName']:
                    continue

                for run in runs:
                    #Skip if the run is not from this repo
                    if run['fromRepoId'] !=  repo['id']:
                        continue
                    
                    row = [repo['fullRepositoryName'], run['runId'], run['creationDate'], run['runStatus'], run['scanStatus'], error['resourceId'], error['title'], error['violationScanStatus'], error['constructiveTitle']]

                    writer.writerow(row)


if __name__ == '__main__':
    #Get look back time from CLI Args
    parser = argparse.ArgumentParser(
        prog='CICD Scan CSV Report',
        description='What the program does',
        epilog=''
    )
    parser.add_argument('-t', '--time', required=True, help='YEAR-MONTH-DAY. EX: 2023-02-31')
    args = parser.parse_args()

    repositories = get_repos(session)
    runs = get_runs(session, repositories, args.time)

    #Create first CSV report with just repos and run results
    create_csv_report_runs(repositories, runs)

    #Gather detailed resource policy scan status data
    resources = []
    for repo in repositories:
        for run in runs:
            if run['fromRepoId'] == repo['id']: #only get resources for runs that were performed on that repo
                resources.extend(get_resources(session, repo, run))

    errors = get_errors(repositories, runs, resources)

    #Create complete CSV with resources and policy names
    create_csv_report_errors(repositories, runs, errors)



    #Once errors have been gathered, we can create the CSV report.