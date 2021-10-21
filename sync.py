import requests, json
import datetime
import pickle
import os
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import config as conf

def main():
    # TODO: Create a config file to hide sensitive information
    notion_token = conf.hidden["notion_token"]
    notion_db_ID = conf.hidden["notion_db_ID"]
    notion_headers = {
            "Authorization" : "Bearer " + notion_token,
            "Notion-Version" : "2021-08-16", 
            "Content-Type" : "application/json"
            }
    tasks_scope = ["https://www.googleapis.com/auth/tasks"] 	
    tasks_secret = conf.hidden["tasks_secret"]
    tasks_api_name = "tasks"
    tasks_api_version = "v1"
    tasklist_id = conf.hidden["tasklist_id"]
    
    get_tasks_to_upload(notion_db_ID, notion_headers)
    service = create_tasks_service(tasks_secret, tasks_api_name, tasks_api_version, tasks_scope)
    upload_tasks(get_tasks_to_upload(notion_db_ID, notion_headers), service, tasklist_id, notion_db_ID, notion_headers)


def get_tasks_to_upload(db_ID, headers):
    # Setting up the database retrieval
    readURL = f'https://api.notion.com/v1/databases/{db_ID}/query'
    res = requests.request("POST", readURL, headers=headers)
    data = res.json()

    tasks_to_upload = {}
    for i in range(0, len(data["results"])):
        task_name = data["results"][i]["properties"]["Task Name"]["title"][0]["text"]["content"]
        uploaded = data["results"][i]["properties"]["Uploaded to Gcal?"]["checkbox"]
        page_name = data["results"][i]["id"]
        done_or_not = data["results"][i]["properties"]["Status"]["select"]["name"]

        # If not already uploaded AND there is a do date, then shove into a map that has task name:due date
        if(data["results"][i]["properties"]["Do Date"]['date'] is not None and uploaded == False and done_or_not != "Done"):
            do_date = data["results"][i]["properties"]["Do Date"]['date']['start']
            # Added this random time at the end of the do date in order to convert to accepted datetime format for tasks API
            converted_do_date = str(do_date) + "T15:28:51.818095+00:00"
            tasks_to_upload[task_name] = [converted_do_date, page_name]

    return tasks_to_upload

def upload_tasks(tasks_to_upload, service,tasklist_id, db_ID, headers):
    # This line is more useful for when we actually have to update notion
    # get_task = service.tasks().list(tasklist=tasklist_id).execute()
    # print(get_task["items"][0]["title"])

    # First we upload the tasks from notion into google tasks
    for key, value in tasks_to_upload.items():
        service.tasks().insert(
                tasklist = tasklist_id,
                body = {
                    "kind" : "tasks#task",
                    "title" : key,
                    "due" : value[0]
                    }
                ).execute()
    # Now we update the notion db to set all uploaded items to True
    for key, value in tasks_to_upload.items():
        page = tasks_to_upload[key][1]
        print(page)
        updateURL = f'https://api.notion.com/v1/pages/{page}'
        updateData = {
            "properties" : {
                "Uploaded to Gcal?" : {
                    "checkbox" : True
                    }
                }
        }
        upData = json.dumps(updateData)

        res = requests.patch(updateURL, headers=headers, data=upData)

def create_tasks_service(tasks_secret, tasks_api_name, tasks_api_version, *tasks_scope):
    CLIENT_SECRET_FILE = tasks_secret
    API_SERVICE_NAME = tasks_api_name
    API_VERSION = tasks_api_version
    SCOPES = [scope for scope in tasks_scope[0]]

    cred = None

    pickle_file = f'token_{API_SERVICE_NAME}_{API_VERSION}.pickle'

    if os.path.exists(pickle_file):
        with open(pickle_file, 'rb') as token:
            cred = pickle.load(token)

    if not cred or not cred.valid:
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES)
            cred = flow.run_local_server()

        with open(pickle_file, 'wb') as token:
            pickle.dump(cred, token)

    try:
        service = build(API_SERVICE_NAME, API_VERSION, credentials=cred)
        print(API_SERVICE_NAME, 'service created successfully')
        return service
    except Exception as e:
        print(e)
        print(f'Failed to create service instance for {API_SERVICE_NAME}')
        os.remove(pickle_file)
        return None

if __name__ == "__main__":
    main()
