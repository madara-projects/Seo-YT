pipeline {
agent any

`
environment {
    IMAGE_NAME = 'seo-app'
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
            sh "docker build -t  ."
        }
    }

    stage('Run Container') {
        steps {
            sh '''
                docker rm -f seo-container || true
                docker run -d -p 8000:8000 --name seo-container 
            '''
        }
    }
}
`

}
