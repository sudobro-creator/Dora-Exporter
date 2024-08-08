import os
import requests
from prometheus_client import start_http_server, Gauge
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

# Configuration from .env
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_OWNER = os.getenv('GITHUB_OWNER')
GITHUB_REPO = os.getenv('GITHUB_REPO')
PORT = int(os.getenv('PORT', 8090))

# # GitHub repository details
# OWNER = os.getenv('GITHUB_OWNER')
# REPO = os.getenv('GITHUB_REPO')
# TOKEN = os.getenv('GITHUB_TOKEN')  # Your GitHub token here

# Prometheus metrics
deployment_frequency_gauge = Gauge('deployment_frequency', 'Deployment Frequency')
lead_time_changes_gauge = Gauge('lead_time_for_changes', 'Lead Time for Changes')
change_failure_rate_gauge = Gauge('change_failure_rate', 'Change Failure Rate')
mttr_gauge = Gauge('mttr', 'Mean Time to Recovery')

# GitHub API base URL
GITHUB_API_URL = 'https://api.github.com'

def fetch_workflow_runs():
    url = f'{GITHUB_API_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def fetch_commits():
    url = f'{GITHUB_API_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def calculate_metrics(commits, workflow_runs):
    now = datetime.utcnow()
    total_deployments = len(workflow_runs['workflow_runs'])
    start_date = now - timedelta(days=30)  # For the last 30 days
    
    # Calculate Deployment Frequency
    deployments_count = sum(1 for run in workflow_runs['workflow_runs']
                            if datetime.strptime(run['created_at'], '%Y-%m-%dT%H:%M:%SZ') > start_date)
    deployment_frequency = deployments_count / 30.0
    deployment_frequency_gauge.set(deployment_frequency)

    # Calculate Lead Time for Changes
    lead_times = []
    for commit in commits:
        commit_date = datetime.strptime(commit['commit']['committer']['date'], '%Y-%m-%dT%H:%M:%SZ')
        for run in workflow_runs['workflow_runs']:
            run_date = datetime.strptime(run['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            if commit_date < run_date:
                lead_times.append((run_date - commit_date).total_seconds())
                break
    
    average_lead_time = sum(lead_times) / len(lead_times) if lead_times else 0
    lead_time_changes_gauge.set(average_lead_time)

    # Calculate Change Failure Rate
    failed_deployments = sum(1 for run in workflow_runs['workflow_runs'] if run['status'] == 'failure')
    change_failure_rate = (failed_deployments / total_deployments) * 100 if total_deployments else 0
    change_failure_rate_gauge.set(change_failure_rate)

    # Calculate Mean Time to Recovery (MTTR)
    recovery_times = []
    last_failure_time = None
    for run in workflow_runs['workflow_runs']:
        if run['status'] == 'failure':
            last_failure_time = datetime.strptime(run['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        elif last_failure_time:
            recovery_times.append((datetime.strptime(run['created_at'], '%Y-%m-%dT%H:%M:%SZ') - last_failure_time).total_seconds())
            last_failure_time = None
    
    average_mttr = sum(recovery_times) / len(recovery_times) if recovery_times else 0
    mttr_gauge.set(average_mttr)

def main():
    start_http_server(PORT)
    print(f"Starting HTTP server on port {PORT}")
    
    while True:
        try:
            workflow_runs = fetch_workflow_runs()
            commits = fetch_commits()
            calculate_metrics(commits, workflow_runs)
        except Exception as e:
            print(f"Error fetching data: {e}")

if __name__ == "__main__":
    main()
