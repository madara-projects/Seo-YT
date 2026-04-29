pipeline {
    agent any

    environment {
        IMAGE_NAME = 'seo-app'
        REGISTRY = 'your-dockerhub-username'
        CONTAINER_NAME = 'seo-container'
    }

    stages {

        stage('Clone Repo') {
            steps {
                deleteDir()
                git branch: 'main',
                    url: 'https://github.com/madara-projects/Seo-YT.git'
            }
        }

        stage('Build Image') {
            steps {
                sh """
                    docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} .
                """
            }
        }

        stage('Login to Docker Registry') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-creds',
                    usernameVariable: 'USER',
                    passwordVariable: 'PASS'
                )]) {
                    sh """
                        echo $PASS | docker login -u $USER --password-stdin
                    """
                }
            }
        }

        stage('Push Image') {
            steps {
                sh """
                    docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}
                    docker push ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}
                """
            }
        }

        stage('Run Container (Local Test)') {
            steps {
                sh """
                    docker rm -f ${CONTAINER_NAME} || true
                    docker run -d -p 8000:8000 --name ${CONTAINER_NAME} ${IMAGE_NAME}:${BUILD_NUMBER}
                """
            }
        }

        stage('Health Check') {
            steps {
                sh """
                    sleep 10
                    curl -f http://localhost:8000 || exit 1
                """
            }
        }
    }

    post {
        success {
            echo "✅ Pipeline successful: Image ${REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} is ready"
        }
        failure {
            echo "❌ Pipeline failed. Check logs."
        }
    }
}