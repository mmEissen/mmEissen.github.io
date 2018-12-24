from os import path
import requests

PROJECTS = [
    "https://raw.githubusercontent.com/mmEissen/airpixel/master/README.rst",
    "https://raw.githubusercontent.com/mmEissen/importgraph/master/README.rst",
]

def main():
    project_dir = path.dirname(__file__)
    for i, project in enumerate(PROJECTS):
        result = requests.get(project)
        if result.status_code != 200:
            continue
        with open(path.join(project_dir, f"{i:0>2}.rst"), "w") as f:
            f.write(result.text)

if __name__ == "__main__":
    main()
