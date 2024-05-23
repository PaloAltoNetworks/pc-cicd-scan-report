from pcpi import session_loader
import json
import argparse
import csv
from datetime import datetime
import csv

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

def get_runs(session, repositories, look_back_data_string=None):

    look_back_date_object = object
    if look_back_data_string:
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
            if look_back_data_string:
                if run_date_obj >= look_back_date_object:
                    runs.append(run)
            else:
                runs.append(run)

    return runs

def get_resource_data(repo, run):
    repo_id = repo['id']
    run_id = run['runId']
    resource_data = []

    limit = 1000
    offset = 0

    while True:
        payload ={
            "filters": {
                "checkStatus": "Error",
                "enforcementLevel": [
                    "HARD_FAIL",
                    "SOFT_FAIL"
                ],
                "repositories": [
                    repo_id
                ],
                "runId": run_id,
                },
            "search": {
                "scopes": [],
                "term": ""
            },
            "limit": limit,
            "offset": offset
        }
        print('Scan Results for run:', run_id)
        res = session.request('POST','/code/api/v2/code-issues/code_review_scan', json=payload)

        if res.json():
            if res.json()['data']:
                resource_data.extend(res.json()['data'])

                offset += limit

                if len(res.json()['data']) < limit:
                    break
            else:
                break
        else:
            break

    return resource_data
    
# def get_resources(session, repo, run):
#     repo_id = repo['id']
#     run_id = run['runId']
#     limit = 50
#     offset = 0
#     counter = 0
#     resources = []

#     while True:
#         payload = {
#             "filters": {
#                 "repositories": [repo_id],
#                 "runId": run_id,
#                 "checkStatus": "Error",
#                 "codeCategories": [] 
#             },
#             "search": {
#                 "scopes": [],
#                 "term": ""
#             },
#             "offset": offset,
#             "limit": limit,
#             "sortBy": [
#                 {
#                     "key": "Severity",
#                     "direction": "DESC"
#                 },
#                 {
#                     "key": "Count",
#                     "direction": "DESC"
#                 }
#             ]
#         }

#         res = session.request('POST', '/bridgecrew/api/v2/errors/code_review_scan/resources', json=payload)

#         if len(res.json().get('data',[])) < limit:
#             resources.extend(res.json().get('data',[]))
#             break
#         else:
#             counter += 1
#             offset = counter * limit
#             resources.extend(res.json()['data'])

#     return resources

# def get_errors(repositories, runs, resources, target_policy_list = []):
#     errors = []
#     count = 0
#     for resource in resources:
#         count += 1
#         print('COUNT', count, '---' 'TOTAL', len(resources))

#         for repo in repositories:

#             #Skip if resource is not from this repo
#             if resource['repository'] != repo['fullRepositoryName']:
#                 continue

#             for run in runs:
                
#                 #Skip if the run is not from this repo
#                 if run['fromRepoId'] !=  repo['id']:
#                     continue
                
#                 #Get values for payload
#                 repo_id = repo['id']
#                 repo_name = repo['fullRepositoryName']
#                 run_id = run['runId']
#                 resource_name = resource['resourceName']

#                 payload = {
#                     "filters": {
#                         "repositories": [
#                             repo_id
#                         ],
#                         "runId": run_id
#                     },
#                     "resourceName": resource_name,
#                     "repository": repo_name,
#                     "sourceType": "cli" #Only get checkov scan results
#                 }

#                 res = session.request('POST', '/bridgecrew/api/v2/resources/code_review_scan/buildtime/errors', json=payload)

#                 if res:
#                     if target_policy_list:
#                         for error in res.json()['errors']:
#                             if error['title'] in target_policy_list:
#                                 errors.append(error)
#                     else:
#                         errors.extend(res.json()['errors'])

#     return errors

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


def create_csv_report_errors(repositories, runs, resources_data, target_policies=None):
    print('Creating CSV export...')
    with open('full_report.csv', 'w') as outfile:
        writer = csv.writer(outfile)
        headers = ['Repository Name', 'Run ID', 'Run Time', 'Run Status', 'Run Result', 'Resource Name', 'Policy Name', 'Category', 'Severity']
        writer.writerow(headers)

        for repo in repositories:
            for run in runs:
                #Skip if the run is not from this repo
                if run['fromRepoId'] !=  repo['id']:
                    continue

                resources = resources_data.get(run['runId'],[])

                for res in resources:
                    if target_policies:
                        if res['policy'] not in target_policies:
                            continue

                    row = [repo['fullRepositoryName'], run['runId'], run['creationDate'], run['runStatus'], run['scanStatus'], res.get('resourceId','N/A'), res['policy'], res['codeCategory'], res['severity']]
                    writer.writerow(row)
    print('Done.')


if __name__ == '__main__':
    #Get look back time from CLI Args
    parser = argparse.ArgumentParser(
        prog='CICD Scan CSV Report',
        description='What the program does',
        epilog=''
    )
    parser.add_argument('-t', '--time', help='YEAR-MONTH-DAY. EX: "2023-02-31"', default=None)
    parser.add_argument('-p', '--policy', help='Full Policy Name. Supply multiple comma separated. EX: "Storage Account name does not follow naming rules"', default=[])
    args = parser.parse_args()

    polices_list = []

    polices_list = args.policy.split(',')

    if polices_list:
        print()
        print('Target Policies List:', polices_list)
        print()

    if args.time:
        print()
        print('Time Range look back:', args.time)
        print()

    repositories = get_repos(session)
    runs = get_runs(session, repositories, args.time)

    #Create first CSV report with just repos and run results
    create_csv_report_runs(repositories, runs)

    #Gather detailed resource policy scan status data
    # resources = []
    resource_data_index = {}
    for repo in repositories:
        for run in runs:
            if run['fromRepoId'] == repo['id']: #only get resources for runs that were performed on that repo
                if run['runId'] in resource_data_index:
                    resource_data_index[run['runId']].extend(get_resource_data(repo, run))
                else:
                    resource_data_index.update(
                        {
                            run['runId'] : get_resource_data(repo, run)
                        }
                    )

    #Create complete CSV with resources and policy names
    create_csv_report_errors(repositories, runs, resource_data_index, polices_list)


