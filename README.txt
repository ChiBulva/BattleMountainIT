Live:
	cp extras/live-docker-compose.yml docker-compose.yml
	cp extras/GlobalDockerfile Dockerfile
Dev:
	cp extras/devops-docker-compose.yml docker-compose.yml
	cp extras/GlobalDockerfile Dockerfile


	Change line in App for Dev server

Docker Compose Application Setup
1. Prerequisites
   Before running this application, ensure that you have the following software installed on your system:
   - Docker: [Download Docker](https://docs.docker.com/get-docker/)
   - Docker Compose: [Install Docker Compose](https://docs.docker.com/compose/install/)

2. Running the Application
   1. Clone this repository to your local machine:
      git clone [repository-url]
   2. Navigate to the project directory:
      cd ~/BattleMountainIT/Live/
   3. Start the Docker Compose application:
      sudo systemctl start my-docker-compose-app
   4. Verify that the application is running:
      sudo systemctl status my-docker-compose-app
   The application should now be up and running.

3. Accessing the Application
   You can access the application by opening a web browser and navigating to [URL or IP address where your app is hosted].

4. Stopping the Application
   To stop the application, use the following command:
   sudo systemctl stop my-docker-compose-app

5. Removing the Application
   To remove the application and associated containers, use the following command:
   sudo systemctl stop my-docker-compose-app
   sudo systemctl disable my-docker-compose-app

6. Troubleshooting
   If you encounter any issues or need further assistance, please [provide a contact email or link to a support resource].

