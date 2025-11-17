## Running under multipass, Ubuntu 24.04 LTS

1.  Install some Ubuntu packages 

    ```bash
    sudo apt update
    sudo apt install python3.12-venv
    sudo apt install build-essential gcc make
    sudo apt install python3 python3-pip
    sudo apt install libgl-dev
    ```
## Running the application

1.  **Create a virtual environment:**

    ```bash
    python3 -m venv venv
    ```

2.  **Activate the virtual environment:**

    ```bash
    source venv/bin/activate
    ```

3.  **Install the dependencies:**

    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the django server:**

    ```bash
    cd automarker_api
    python manage.py migrate
    python manage.py runserver

    ```
    The API will now be accessible at   
            http://127.0.0.1:8000/


    And the endpoints are:

        ```
        POST /api/grade/single/
        POST /api/grade/batch/
        ```