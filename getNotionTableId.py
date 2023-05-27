import os
from notion_client import Client

notion = Client(auth=os.environ["NOTION_API_KEY"])


def get_database_id(database_name):
    databases = notion.search(filter={"property": "object", "value": "database"}).get("results")
    for database in databases:
        if database['title'][0]['text']['content'] == database_name:
            return database['id']
    return None


if __name__ == "__main__":
    database_name = input("Enter the name of the Notion table: ")
    database_id = get_database_id(database_name)
    if database_id:
        print(f"The database ID for '{database_name}' is: {database_id}")
    else:
        print(f"No database found with the name '{database_name}'.")
