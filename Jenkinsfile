pipeline {
  agent any

  environment {
    APP_NAME       = 'seo-app'
    IMAGE_TAG      = "${env.BUILD_NUMBER}"
    IMAGE_LOCAL    = "${APP_NAME}:${IMAGE_TAG}"
    HELM_CHART_DIR = 'helm/seo-app'
    REPO_URL       = 'https://github.com/madara-projects/Seo-YT.git'
    REPO_BRANCH    = 'main'
    GIT_USER_NAME  = 'jenkins-bot'
    GIT_USER_EMAIL = 'jenkins@local'
  }

  options {
    timestamps()
    timeout(time: 30, unit: 'MINUTES')
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

    stage('Load Image into Minikube') {
      steps {
        sh '''
          set -eu
          # Push the freshly built image into Minikube's containerd runtime
          # without going through any registry.
          docker save ${IMAGE_LOCAL} | docker exec -i minikube ctr -n=k8s.io images import -
          docker save ${APP_NAME}:latest | docker exec -i minikube ctr -n=k8s.io images import -
        '''
      }
    }

    stage('Bump Helm chart image tag') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'github-pat',
                                          usernameVariable: 'GH_USER',
                                          passwordVariable: 'GH_TOKEN')]) {
          sh '''
            set -eu
            git config user.name  "${GIT_USER_NAME}"
            git config user.email "${GIT_USER_EMAIL}"
            sed -i "s/^  tag:.*/  tag: \\"${IMAGE_TAG}\\"/" ${HELM_CHART_DIR}/values.yaml
            git add ${HELM_CHART_DIR}/values.yaml
            git commit -m "ci: bump ${APP_NAME} to ${IMAGE_TAG}" || echo "nothing to commit"
            git push https://${GH_USER}:${GH_TOKEN}@github.com/madara-projects/Seo-YT.git HEAD:${REPO_BRANCH}
          '''
        }
      }
    }

    stage('Trigger Argo CD sync') {
      steps {
        sh '''
          set -eu
          # Soft trigger so the new commit is picked up immediately.
          kubectl -n argocd annotate app ${APP_NAME} \
              argocd.argoproj.io/refresh=hard --overwrite || true
        '''
      }
    }

    stage('Smoke (rollout status)') {
      steps {
        sh '''
          set -eu
          kubectl -n ${APP_NAME} rollout status deployment/${APP_NAME} --timeout=180s
          kubectl -n ${APP_NAME} get pods -l app=${APP_NAME}
        '''
      }
    }
  }

  post {
    always {
      sh '''
        # Hygiene — keep the Jenkins host's Docker disk under control.
        docker image prune -f --filter "until=24h" || true
        docker builder prune -f --filter "until=24h" || true
      '''
    }
    success { echo "Built ${IMAGE_LOCAL}, bumped chart, Argo CD will deploy." }
    failure { sh 'docker logs $(docker ps -lq) || true' }
  }
}
