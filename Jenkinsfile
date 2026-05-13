pipeline {
  agent any

  environment {
    APP_NAME    = 'seo-app'
    IMAGE_TAG   = "${env.BUILD_NUMBER}"
    IMAGE_LOCAL = "${APP_NAME}:${IMAGE_TAG}"
    REPO_URL    = 'https://github.com/madara-projects/Seo-YT.git'
    REPO_BRANCH = 'main'
  }

  options {
    timestamps()
    timeout(time: 20, unit: 'MINUTES')
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '15'))
  }

  stages {

    stage('Checkout') {
      steps {
        git branch: "${REPO_BRANCH}", url: "${REPO_URL}"
      }
    }

    stage('Build Image') {
      steps {
        sh '''
          set -eu
          docker build -t ${IMAGE_LOCAL} -t ${APP_NAME}:latest .
        '''
      }
    }

    stage('Smoke Test') {
      steps {
        sh '''
          set -eu
          # Boot the freshly built image, hit /health, tear down.
          CID=$(docker run -d -p 18000:8000 ${IMAGE_LOCAL})
          trap "docker rm -f $CID >/dev/null 2>&1 || true" EXIT
          for i in $(seq 1 20); do
            if curl -fsS http://localhost:18000/health >/dev/null; then
              echo "health OK"; exit 0
            fi
            sleep 1
          done
          echo "health check failed"; docker logs $CID || true; exit 1
        '''
      }
    }
  }

  post {
    always {
      sh '''
        docker image prune -f --filter "until=24h" || true
        docker builder prune -f --filter "until=24h" || true
      '''
    }
    success { echo "Built and smoke-tested ${IMAGE_LOCAL}." }
    failure { sh 'docker logs $(docker ps -lq) || true' }
  }
}
